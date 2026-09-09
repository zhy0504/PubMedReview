import io
import json
import sys
import time

import pytest

from workbench.jobs import JobManager
from workbench.store import HistoryStore
from workbench.worker import EventChannel


def wait_for(predicate):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError('worker did not reach expected state')


@pytest.mark.parametrize('success', [True, False])
def test_worker_terminal_result_and_artifacts(tmp_path, success):
    script = "import sys,json,pathlib; json.loads(sys.stdin.readline()); pathlib.Path('output').mkdir(); pathlib.Path('output/result.md').write_text('offline result'); print(json.dumps({'kind':'result','payload':{'success':" + repr(success) + "}}),flush=True)"
    store = HistoryStore(tmp_path / 'history' / 'history.sqlite3')
    manager = JobManager(store, tmp_path, command=[sys.executable, '-u', '-c', script])
    try:
        job = manager.start({'query': 'offline'})
        wait_for(lambda: manager.active_id is None)
        assert store.get_job(job['id'])['status'] == ('completed' if success else 'failed')
        assert store.artifacts(job['id'])[0]['name'] == 'result.md'
    finally:
        manager.close()


def test_prompt_response_and_duplicate_rejection(tmp_path):
    script = "import sys,json; sys.stdin.readline(); print(json.dumps({'kind':'prompt','payload':{'id':'p1','text':'continue?'}}),flush=True); answer=json.loads(sys.stdin.readline()); print(json.dumps({'kind':'result','payload':{'success':answer['value']=='yes'}}),flush=True)"
    store = HistoryStore(tmp_path / 'history.sqlite3')
    manager = JobManager(store, tmp_path, command=[sys.executable, '-u', '-c', script])
    try:
        job = manager.start({'query': 'offline'})
        wait_for(lambda: store.get_job(job['id'])['status'] == 'waiting')
        with pytest.raises(RuntimeError):
            manager.start({'query': 'another'})
        manager.respond(job['id'], 'p1', 'yes')
        with pytest.raises(RuntimeError):
            manager.respond(job['id'], 'p1', 'yes')
        wait_for(lambda: manager.active_id is None)
        assert store.get_job(job['id'])['status'] == 'completed'
    finally:
        manager.close()


def test_cancel_preserves_terminal_status_and_releases_lease(tmp_path):
    store = HistoryStore(tmp_path / 'history.sqlite3')
    manager = JobManager(store, tmp_path, command=[sys.executable, '-u', '-c', 'import time; time.sleep(30)'])
    try:
        job = manager.start({'query': 'offline'})
        wait_for(lambda: store.get_job(job['id'])['status'] == 'running')
        manager.cancel(job['id'])
        wait_for(lambda: manager.active_id is None)
        assert store.get_job(job['id'])['status'] == 'cancelled'
        manager._handle(job['id'], {'kind': 'literature', 'payload': {'articles': [{'pmid': '123'}]}})
        assert store.articles(job['id'])['total'] == 0
    finally:
        manager.close()
    reopened = JobManager(store, tmp_path)
    reopened.close()


def test_event_redaction_keeps_json_valid():
    output = io.StringIO()
    channel = EventChannel(output, io.StringIO(), secrets=['secret-value'])
    channel.emit('log', {'text': 'API_KEY=secret-value and token=othersecret'})
    parsed = json.loads(output.getvalue())
    assert 'secret-value' not in parsed['payload']['text']
    assert 'othersecret' not in parsed['payload']['text']


def test_crashed_worker_is_failed_and_can_restart(tmp_path):
    store = HistoryStore(tmp_path / 'history.sqlite3')
    manager = JobManager(store, tmp_path, command=[sys.executable, '-c', 'raise SystemExit(3)'])
    try:
        for query in ['first', 'second']:
            job = manager.start({'query': query})
            wait_for(lambda: manager.active_id is None)
            assert store.get_job(job['id'])['status'] == 'failed'
    finally:
        manager.close()


def test_lease_blocks_second_manager(tmp_path):
    store = HistoryStore(tmp_path / 'history.sqlite3')
    manager = JobManager(store, tmp_path)
    try:
        with pytest.raises(RuntimeError, match='另一个工作台'):
            JobManager(store, tmp_path)
    finally:
        manager.close()
        manager.close()
