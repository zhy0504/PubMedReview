import pytest

from workbench.store import HistoryStore
from workbench.validation import validate_options


def test_history_store_roundtrip_search_and_articles(tmp_path):
    store = HistoryStore(tmp_path / 'history.sqlite3')
    options = validate_options({'query': '结核病患者管理'})
    store.create_job('job-1', options)
    store.update_job('job-1', status='completed', result={'success': True})
    store.replace_articles('job-1', [{'pmid': '123', 'title': 'Digital TB care', 'journal': 'Lancet'}])
    store.add_artifact('job-1', 'artifacts/job-1/result.md', 'result.md', 12)
    assert store.get_job('job-1')['result']['success'] is True
    assert store.list_jobs('患者')['total'] == 1
    assert store.list_jobs('Digital')['total'] == 1
    assert store.articles('job-1', '123')['items'][0]['pmid'] == '123'
    assert store.artifacts('job-1')[0]['name'] == 'result.md'


def test_stale_jobs_are_interrupted_and_preferences_persist(tmp_path):
    store = HistoryStore(tmp_path / 'history.sqlite3')
    store.create_job('job-1', validate_options({'query': 'q'}))
    store.update_job('job-1', status='running')
    store.preferences({'target': 8})
    store.interrupt_stale_jobs()
    assert store.get_job('job-1')['status'] == 'interrupted'
    assert store.preferences()['target'] == 8


def test_validation_rejects_unknown_and_oversized_values():
    try:
        validate_options({'query': 'q', 'unknown': 1})
    except ValueError:
        pass
    else:
        raise AssertionError('unknown parameter accepted')
    try:
        validate_options({'query': 'x' * 5001})
    except ValueError:
        pass
    else:
        raise AssertionError('oversized query accepted')


@pytest.mark.parametrize('search', ['%', '_', '!', "' OR 1=1 --"])
def test_literal_search_does_not_expand_wildcards(tmp_path, search):
    store = HistoryStore(tmp_path / 'history.sqlite3')
    store.create_job('one', validate_options({'query': 'plain text'}))
    store.create_job('two', validate_options({'query': 'contains ' + search}))
    assert store.list_jobs(search)['total'] == 1


def test_history_survives_repository_reopen(tmp_path):
    path = tmp_path / 'history.sqlite3'
    store = HistoryStore(path)
    store.create_job('one', validate_options({'query': 'durable'}))
    store.append_event('one', 'outline', {'content': 'saved'})
    reopened = HistoryStore(path)
    assert reopened.get_job('one')['query'] == 'durable'
    assert reopened.latest_payload('one', 'outline')['content'] == 'saved'


def test_nonfinite_metadata_is_valid_json(tmp_path):
    store = HistoryStore(tmp_path / 'history.sqlite3')
    store.create_job('one', validate_options({'query': 'finite'}))
    store.replace_articles('one', [{'pmid': '1', 'impact_factor': float('nan'), 'score': float('inf')}])
    article = store.articles('one')['items'][0]
    assert article['impact_factor'] is None
    assert article['score'] is None
