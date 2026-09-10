"""SQLite repository for local, single-user research history."""

import json
import math
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


TERMINAL = frozenset({"completed", "failed", "cancelled", "interrupted", "stopped"})


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    def normalize(item):
        if isinstance(item, float) and not math.isfinite(item):
            return None
        if isinstance(item, dict):
            return {key: normalize(content) for key, content in item.items()}
        if isinstance(item, (list, tuple)):
            return [normalize(content) for content in item]
        return item
    return json.dumps(normalize(value), ensure_ascii=False, default=str, allow_nan=False)


def like_pattern(value):
    return "%" + value.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"


class HistoryStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise RuntimeError("数据库版本高于当前程序，请勿降级打开")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, query TEXT NOT NULL, options TEXT NOT NULL,
                    status TEXT NOT NULL, stage TEXT NOT NULL DEFAULT 'queued',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    result TEXT, error TEXT, prompt TEXT
                );
                CREATE INDEX IF NOT EXISTS jobs_created ON jobs(created_at DESC);
                CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status);
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS events_job ON events(job_id, id);
                CREATE TABLE IF NOT EXISTS articles (
                    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    ordinal INTEGER NOT NULL, pmid TEXT NOT NULL, title TEXT NOT NULL,
                    journal TEXT NOT NULL, data TEXT NOT NULL,
                    PRIMARY KEY(job_id, ordinal)
                );
                CREATE INDEX IF NOT EXISTS articles_pmid ON articles(pmid);
                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    path TEXT NOT NULL, name TEXT NOT NULL, size INTEGER NOT NULL,
                    UNIQUE(job_id, path)
                );
                CREATE TABLE IF NOT EXISTS preferences (
                    id INTEGER PRIMARY KEY CHECK(id = 1), data TEXT NOT NULL
                );
                PRAGMA user_version=1;
            """)

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(str(self.path), timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create_job(self, job_id, options):
        timestamp = now()
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO jobs(id,query,options,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                (job_id, options["query"], encode(options), "queued", timestamp, timestamp),
            )
        return self.get_job(job_id)

    @staticmethod
    def decode_job(row):
        if row is None:
            return None
        job = dict(row)
        for field in ("options", "result", "prompt"):
            job[field] = json.loads(job[field]) if job[field] else None
        return job

    def get_job(self, job_id):
        with self.connection() as connection:
            return self.decode_job(connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def delete_job(self, job_id):
        with self.connection() as connection:
            connection.execute("DELETE FROM jobs WHERE id=?", (job_id,))

    def list_jobs(self, search="", status="", offset=0, limit=30):
        clauses, parameters = [], []
        if search:
            clauses.append("(query LIKE ? ESCAPE '!' OR EXISTS (SELECT 1 FROM articles a WHERE a.job_id=jobs.id AND (a.title LIKE ? ESCAPE '!' OR a.pmid=?)))")
            parameters.extend((like_pattern(search), like_pattern(search), search))
        if status:
            clauses.append("status=?")
            parameters.append(status)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connection() as connection:
            total = connection.execute("SELECT COUNT(*) FROM jobs" + where, parameters).fetchone()[0]
            rows = connection.execute(
                "SELECT * FROM jobs" + where + " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                parameters + [limit, offset],
            ).fetchall()
        return {"items": [self.decode_job(row) for row in rows], "total": total}

    def update_job(self, job_id, **fields):
        allowed = {"status", "stage", "result", "error", "prompt"}
        if not fields or not set(fields).issubset(allowed):
            raise ValueError("Invalid job fields")
        values = {key: encode(value) if key in {"result", "prompt"} and value is not None else value for key, value in fields.items()}
        values["updated_at"] = now()
        with self.connection() as connection:
            connection.execute(
                "UPDATE jobs SET " + ",".join(key + "=?" for key in values) + " WHERE id=?",
                list(values.values()) + [job_id],
            )

    def interrupt_stale_jobs(self):
        with self.connection() as connection:
            connection.execute(
                "UPDATE jobs SET status='interrupted', prompt=NULL, error=?, updated_at=? WHERE status IN ('queued','running','waiting')",
                ("服务已重启；已有结果保留。可查看历史或重新运行。", now()),
            )

    def append_event(self, job_id, kind, payload):
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO events(job_id,kind,payload,created_at) VALUES(?,?,?,?)",
                (job_id, kind, encode(payload), now()),
            )
            event_id = cursor.lastrowid
            if kind == "log" and event_id % 100 == 0:
                connection.execute(
                    "DELETE FROM events WHERE job_id=? AND kind='log' AND id < COALESCE((SELECT id FROM events WHERE job_id=? AND kind='log' ORDER BY id DESC LIMIT 1 OFFSET 1999),0)",
                    (job_id, job_id),
                )
        return event_id

    def events(self, job_id, after=0, limit=300):
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM events WHERE job_id=? AND id>? ORDER BY id LIMIT ?", (job_id, after, limit)
            ).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]

    def replace_articles(self, job_id, articles):
        with self.connection() as connection:
            connection.execute("DELETE FROM articles WHERE job_id=?", (job_id,))
            connection.executemany(
                "INSERT INTO articles(job_id,ordinal,pmid,title,journal,data) VALUES(?,?,?,?,?,?)",
                [(job_id, index, str(article.get("pmid", "")), str(article.get("title", "")),
                  str(article.get("journal", "")), encode(article)) for index, article in enumerate(articles)],
            )

    def articles(self, job_id, search="", offset=0, limit=50):
        parameters = [job_id]
        where = " WHERE job_id=?"
        if search:
            where += " AND (title LIKE ? ESCAPE '!' OR journal LIKE ? ESCAPE '!' OR pmid=?)"
            parameters.extend([like_pattern(search), like_pattern(search), search])
        with self.connection() as connection:
            total = connection.execute("SELECT COUNT(*) FROM articles" + where, parameters).fetchone()[0]
            rows = connection.execute("SELECT data FROM articles" + where + " ORDER BY ordinal LIMIT ? OFFSET ?", parameters + [limit, offset]).fetchall()
        return {"items": [json.loads(row[0]) for row in rows], "total": total}

    def add_artifact(self, job_id, path, name, size):
        with self.connection() as connection:
            connection.execute("INSERT OR REPLACE INTO artifacts(job_id,path,name,size) VALUES(?,?,?,?)", (job_id, str(path), name, size))

    def artifacts(self, job_id):
        with self.connection() as connection:
            return [dict(row) for row in connection.execute("SELECT id,name,size FROM artifacts WHERE job_id=? ORDER BY id", (job_id,))]

    def latest_payload(self, job_id, kind):
        with self.connection() as connection:
            row = connection.execute("SELECT payload FROM events WHERE job_id=? AND kind=? ORDER BY id DESC LIMIT 1", (job_id, kind)).fetchone()
            return json.loads(row[0]) if row else None

    def artifact(self, artifact_id):
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
            return dict(row) if row else None

    def preferences(self, data=None):
        with self.connection() as connection:
            if data is not None:
                connection.execute("INSERT OR REPLACE INTO preferences(id,data) VALUES(1,?)", (encode(data),))
            row = connection.execute("SELECT data FROM preferences WHERE id=1").fetchone()
            return json.loads(row[0]) if row else {}

    def stats(self):
        with self.connection() as connection:
            counts = {row[0]: row[1] for row in connection.execute("SELECT status,COUNT(*) FROM jobs GROUP BY status")}
            articles = connection.execute("SELECT COUNT(DISTINCT pmid) FROM articles WHERE pmid<>''").fetchone()[0]
        return {"tasks": sum(counts.values()), "completed": counts.get("completed", 0), "articles": articles}
