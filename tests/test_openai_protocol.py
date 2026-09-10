from types import SimpleNamespace

from openai_protocol import build_request, endpoint, is_model_compatible, normalize_response, send_text
from pubmed_search import SearchConfig, PubMedSearcher


def test_protocol_request_mapping():
    messages = [SimpleNamespace(role='user', content='test')]
    for protocol, key in [('openai', 'max_completion_tokens'), ('openai_responses', 'max_output_tokens')]:
        result = build_request(messages, 'gpt-5.4-mini', {'max_tokens': 500, 'temperature': 0.2}, protocol, 'https://example.org/v1')
        assert result[key] == 500
        assert 'temperature' not in result
        assert 'max_tokens' not in result
        assert result['store'] is False
    assert endpoint('https://example.org/v1/', 'models') == 'https://example.org/v1/models'
    assert endpoint('https://example.org', 'responses') == 'https://example.org/v1/responses'
    assert endpoint('https://api.deepseek.com', 'models') == 'https://api.deepseek.com/models'
    assert endpoint('https://api.deepseek.com/v1', 'chat/completions') == 'https://api.deepseek.com/chat/completions'
    assert endpoint('https://proxy.example.com/v1', 'models', provider='deepseek') == 'https://proxy.example.com/v1/models'
    assert endpoint('https://open.bigmodel.cn/api/paas/v4', 'models') == 'https://open.bigmodel.cn/api/paas/v4/models'
    assert endpoint('https://open.bigmodel.cn/api/paas/v4/', 'chat/completions') == 'https://open.bigmodel.cn/api/paas/v4/chat/completions'
    assert is_model_compatible('https://open.bigmodel.cn/api/paas/v4', 'glm-5.3')
    assert not is_model_compatible('https://open.bigmodel.cn/api/paas/v4', 'gemini-3-pro')


def test_deepseek_request_uses_current_chat_wire_format():
    messages = [SimpleNamespace(role='user', content='test')]
    result = build_request(messages, 'deepseek-v4-flash', {
        'max_tokens': 500, 'temperature': 0.2, 'top_p': 0.8,
        'reasoning_effort': 'medium', 'store': False,
    }, 'openai', 'https://api.deepseek.com')
    assert result['max_tokens'] == 500
    assert 'max_completion_tokens' not in result
    assert 'store' not in result
    assert result['thinking'] == {'type': 'enabled'}
    assert result['reasoning_effort'] == 'high'
    assert 'temperature' not in result
    assert 'top_p' not in result

    disabled = build_request(messages, 'deepseek-v4-flash', {
        'temperature': 0.2, 'reasoning_effort': 'none',
    }, 'openai', 'https://api.deepseek.com')
    assert disabled['thinking'] == {'type': 'disabled'}
    assert disabled['temperature'] == 0.2


def test_deepseek_stream_request_uses_unprefixed_endpoint():
    calls = []

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def raise_for_status(self): pass
        def iter_lines(self):
            return iter([
                b'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":null}]}',
                b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
                b'data: [DONE]',
            ])

    class Session:
        def post(self, url, **kwargs):
            calls.append((url, kwargs))
            return Response()

    config = SimpleNamespace(api_type='openai', base_url='https://api.deepseek.com', timeout=10)
    result = send_text(Session(), config, [], 'deepseek-v4-flash', {'reasoning_effort': 'low'})
    assert calls[0][0] == 'https://api.deepseek.com/chat/completions'
    assert result['choices'][0]['message']['content'] == 'ok'


def test_zhipu_request_uses_full_base_and_chat_wire_format():
    messages = [SimpleNamespace(role='user', content='test')]
    result = build_request(messages, 'glm-5.3', {
        'max_tokens': 500, 'temperature': 0.2,
        'reasoning_effort': 'medium', 'store': False,
    }, 'openai', 'https://open.bigmodel.cn/api/paas/v4')
    assert result['max_tokens'] == 500
    assert 'max_completion_tokens' not in result
    assert 'store' not in result
    assert result['thinking'] == {'type': 'enabled'}
    assert result['reasoning_effort'] == 'medium'
    assert result['temperature'] == 0.2


def test_discover_models_supports_direct_deepseek_env(monkeypatch, tmp_path):
    from workbench import configuration

    (tmp_path / '.env').write_text(
        'DEEPSEEK_API_KEY=sk-test-deepseek-key\nDEEPSEEK_BASE_URL=https://api.deepseek.com/v1\n',
        encoding='utf-8',
    )

    class Response:
        def raise_for_status(self): pass
        def json(self): return {'data': [{'id': 'deepseek-v4-pro'}, {'id': 'deepseek-v4-flash'}]}

    calls = []
    monkeypatch.setattr(configuration.requests, 'get', lambda url, **kwargs: (calls.append((url, kwargs)) or Response()))
    assert configuration.discover_models(tmp_path) == ['deepseek-v4-flash', 'deepseek-v4-pro']
    assert calls[0][0] == 'https://api.deepseek.com/models'


def test_discover_models_supports_zhipu_env(monkeypatch, tmp_path):
    from workbench import configuration

    (tmp_path / '.env').write_text(
        'ZHIPU_API_KEY=test-zhipu-key\nZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4\n',
        encoding='utf-8',
    )

    class Response:
        def raise_for_status(self): pass
        def json(self): return {'data': [{'id': 'glm-5.3'}, {'id': 'glm-4.5-air'}]}

    calls = []
    monkeypatch.setattr(configuration.requests, 'get', lambda url, **kwargs: (calls.append((url, kwargs)) or Response()))
    assert configuration.discover_models(tmp_path) == ['glm-4.5-air', 'glm-5.3']
    assert calls[0][0] == 'https://open.bigmodel.cn/api/paas/v4/models'


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
