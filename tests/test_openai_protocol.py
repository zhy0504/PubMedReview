from types import SimpleNamespace

from openai_protocol import build_request, endpoint, normalize_response, send_text
from pubmed_search import SearchConfig, PubMedSearcher


def test_protocol_request_mapping():
    messages = [SimpleNamespace(role='user', content='test')]
    for protocol, key in [('openai', 'max_completion_tokens'), ('openai_responses', 'max_output_tokens')]:
        result = build_request(messages, 'gpt-5.4-mini', {'max_tokens': 500, 'temperature': 0.2}, protocol)
        assert result[key] == 500
        assert 'temperature' not in result
        assert 'max_tokens' not in result
        assert result['store'] is False
    assert endpoint('https://example.org/v1/', 'models') == 'https://example.org/v1/models'
    assert endpoint('https://example.org', 'responses') == 'https://example.org/v1/responses'


def test_response_normalization_rejects_partial():
    assert 'error' in normalize_response({'status': 'incomplete'}, 'openai_responses')
    result = normalize_response({'status': 'completed', 'output': [
        {'type': 'reasoning', 'content': [{'type': 'output_text', 'text': 'private'}]},
        {'type': 'message', 'content': [{'type': 'output_text', 'text': 'OK'}]}]}, 'openai_responses')
    assert result['choices'][0]['message']['content'] == 'OK'


def test_stream_disconnect_is_error():
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def raise_for_status(self): pass
        def iter_lines(self): return iter([b'data: {"type":"response.output_text.delta","delta":"partial"}'])
    session = SimpleNamespace(post=lambda *args, **kwargs: Response())
    config = SimpleNamespace(api_type='openai_responses', base_url='https://example.org', timeout=10)
    assert 'error' in send_text(session, config, [], 'test', {})


def test_pubmed_key_and_reservation(monkeypatch):
    monkeypatch.delenv('PUBMED_API_KEY', raising=False)
    assert SearchConfig().request_delay == 0.35
    monkeypatch.setenv('PUBMED_API_KEY', 'test-secret')
    searcher = PubMedSearcher(SearchConfig(enable_cache=False, enable_async=False))
    monkeypatch.setattr('pubmed_search.time.sleep', lambda delay: None)
    params = {}
    searcher._prepare_request(params)
    assert params['api_key'] == 'test-secret'
    assert searcher.config.request_delay == 0.11
    assert searcher._reserve_request() > 0
    searcher.session.close()
