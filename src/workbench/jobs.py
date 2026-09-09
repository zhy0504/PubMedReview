"""Supervised subprocess execution; one workflow at a time, durable history."""

import json
import os
import shutil
import subprocess
import sys
import threading
import uuid
from pathlib import Path

from workbench.store import TERMINAL
from workbench.validation import validate_options


class WorkspaceLease:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = path.open('a+b')
        try:
            if path.stat().st_size == 0:
                self.stream.write(b'0')
                self.stream.flush()
            self.stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise RuntimeError('另一个工作台正在使用该历史数据库，请先关闭它')

    def close(self):
        self.stream.close()


class JobManager:
    def __init__(self, store, root, command=None):
        self.store = store
        self.root = Path(root).resolve()
        self.directory = store.path.parent.resolve()
        self.command = command or [sys.executable, '-u', '-m', 'workbench.worker']
        self.lock = threading.RLock()
        self.process = None
        self.active_id = None
        self.thread = None
        self.closed = False
        self.lease = WorkspaceLease(self.directory / 'workbench.lock')
        self.store.interrupt_stale_jobs()

    def start(self, options):
        options = validate_options(options)
        with self.lock:
            if self.closed or self.active_id is not None:
                raise RuntimeError('已有任务运行中，请完成或取消后再启动')
            job_id = uuid.uuid4().hex
            self.store.create_job(job_id, options)
            self.active_id = job_id
            self.thread = threading.Thread(target=self._run, args=(job_id, options), daemon=True)
            self.thread.start()
        return self.store.get_job(job_id)

    def _snapshot(self):
        output = self.root / 'output'
        return {path: (path.stat().st_mtime_ns, path.stat().st_size) for path in output.rglob('*') if path.is_file() and not path.is_symlink()} if output.exists() else {}

    def _collect_artifacts(self, job_id, before):
        destination = self.directory / 'artifacts' / job_id
        output = (self.root / 'output').resolve()
        for path, signature in self._snapshot().items():
            if before.get(path) == signature:
                continue
            resolved = path.resolve()
            if output not in resolved.parents or resolved.suffix.lower() not in {'.md', '.docx', '.csv', '.json', '.txt', '.ris'}:
                continue
            relative = resolved.relative_to(output)
            saved = destination / relative
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(resolved, saved)
            self.store.add_artifact(job_id, saved.relative_to(self.directory), str(relative), saved.stat().st_size)

    def _handle(self, job_id, event):
        kind, payload = event['kind'], event['payload']
        with self.lock:
            current = self.store.get_job(job_id)
            if current['status'] in TERMINAL:
                return
            if kind == 'literature':
                self.store.replace_articles(job_id, payload['articles'])
                payload = {'count': len(payload['articles'])}
            if kind == 'stage':
                self.store.update_job(job_id, stage=payload['stage'], status='running')
            elif kind == 'prompt':
                self.store.update_job(job_id, prompt=payload, status='waiting')
            elif kind == 'result':
                self.store.update_job(job_id, result=payload)
            self.store.append_event(job_id, kind, payload)

    def _run(self, job_id, options):
        before = {}
        try:
            before = self._snapshot()
            environment = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUNBUFFERED': '1', 'PYTHONPATH': str(self.root / 'src')}
            with self.lock:
                if self.store.get_job(job_id)['status'] == 'cancelled':
                    return
                self.process = subprocess.Popen(self.command, cwd=self.root, env=environment,
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding='utf-8', errors='replace', bufsize=1,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                process = self.process
                self.store.update_job(job_id, status='running')
                process.stdin.write(json.dumps(options, ensure_ascii=False) + '\n')
                process.stdin.flush()
            for line in process.stdout:
                try:
                    event = json.loads(line)
                    if isinstance(event, dict) and 'kind' in event and 'payload' in event:
                        self._handle(job_id, event)
                except json.JSONDecodeError:
                    self.store.append_event(job_id, 'log', {'text': '工作进程产生非结构化输出；请检查本地环境和依赖。'})
            exit_code = process.wait()
            self._collect_artifacts(job_id, before)
            with self.lock:
                job = self.store.get_job(job_id)
                if job['status'] not in TERMINAL:
                    result = job['result'] or {}
                    status = 'completed' if exit_code == 0 and result.get('success') else 'stopped' if result.get('restart') else 'failed'
                    self.store.update_job(job_id, status=status, prompt=None,
                        error=None if status in {'completed', 'stopped'} else result.get('error') or f'工作进程异常退出 ({exit_code})')
        except Exception as error:
            with self.lock:
                if self.store.get_job(job_id)['status'] not in TERMINAL:
                    self.store.update_job(job_id, status='failed', prompt=None, error=f'任务执行失败: {type(error).__name__}')
        finally:
            with self.lock:
                if self.process:
                    if self.process.poll() is None:
                        self.process.terminate()
                        try:
                            self.process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            self.process.kill()
                            self.process.wait()
                    self.process.stdin.close()
                    self.process.stdout.close()
                self.process = None
                self.active_id = None

    def respond(self, job_id, prompt_id, value):
        if not isinstance(value, str) or len(value) > 5000:
            raise ValueError('交互回答过长或格式错误')
        with self.lock:
            job = self.store.get_job(job_id)
            if job_id != self.active_id or not job or job['status'] != 'waiting' or job['prompt']['id'] != prompt_id:
                raise RuntimeError('该提示已失效，请刷新任务状态')
            self.process.stdin.write(json.dumps({'prompt_id': prompt_id, 'value': value}) + '\n')
            self.process.stdin.flush()
            self.store.update_job(job_id, status='running', prompt=None)

    def cancel(self, job_id):
        with self.lock:
            job = self.store.get_job(job_id)
            if not job or job_id != self.active_id or job['status'] in TERMINAL:
                raise RuntimeError('任务当前不可取消')
            self.store.update_job(job_id, status='cancelled', prompt=None)
            if self.process and self.process.poll() is None:
                self.process.terminate()

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            if self.active_id and self.store.get_job(self.active_id)['status'] not in TERMINAL:
                self.cancel(self.active_id)
        if self.thread:
            self.thread.join(timeout=15)
        self.lease.close()
