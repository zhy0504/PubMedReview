from types import SimpleNamespace

from ai_client import AIConfig, AnthropicAdapter, ChatMessage, GeminiAdapter
from ai_providers import provider_for_url, provider_options
from openai_protocol import build_request, endpoint
from workbench import configuration
from workbench.validation import validate_options
from ai_config import get_ai_config, reset_ai_config_cache


def test_common_provider_url_detection_and_versioned_endpoints():
    assert provider_for_url('https://dashscope.aliyuncs.com/compatible-mode/v1') == 'qwen'
    assert provider_for_url('https://ark.cn-beijing.volces.com/api/v3') == 'volcengine_ark'
    assert provider_for_url('https://api.groq.com/openai/v1') == 'groq'
    assert endpoint('https://ark.cn-beijing.volces.com/api/v3', 'models', provider='volcengine_ark') == 'https://ark.cn-beijing.volces.com/api/v3/models'
    assert endpoint('https://dashscope.aliyuncs.com/compatible-mode/v1', 'chat/completions', provider='qwen') == 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'


def test_legacy_openai_compatible_request_uses_max_tokens_without_store():
    messages = [SimpleNamespace(role='user', content='test')]
    result = build_request(messages, 'qwen-plus', {'max_tokens': 300, 'temperature': 0.2}, 'openai',
                           'https://dashscope.aliyuncs.com/compatible-mode/v1', provider='qwen')
    assert result['max_tokens'] == 300
    assert 'max_completion_tokens' not in result
    assert 'store' not in result
    assert result['temperature'] == 0.2


def test_provider_options_are_safe_for_the_web_ui():
    providers = provider_options()
    ids = {item['id'] for item in providers}
    assert {'openai', 'deepseek', 'zhipu', 'qwen', 'volcengine_ark', 'gemini', 'anthropic', 'ollama', 'lmstudio'} <= ids
    assert all('env_prefix' not in item for item in providers)


def test_web_configuration_saves_selected_provider_and_discovers_models(tmp_path, monkeypatch):
    result = configuration.save_configuration(tmp_path, {
        'service': 'qwen',
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'api_key': 'dashscope-test-key',
        'model': 'qwen-plus',
        'api_type': 'openai',
    })
    assert result['provider'] == 'qwen'
    assert result['model'] == 'qwen-plus'
    assert result['api_key_configured'] is True

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {'data': [{'id': 'qwen-plus'}, {'id': 'qwen-turbo'}]}

    calls = []
    monkeypatch.setattr(configuration, '_get_models_response', lambda url, headers: (calls.append((url, headers)) or Response()))
    assert configuration.discover_models(tmp_path) == ['qwen-plus', 'qwen-turbo']
    assert calls[0][0].endswith('/models')
    assert calls[0][1]['Authorization'] == 'Bearer dashscope-test-key'


def test_gemini_model_discovery_filters_generation_models(tmp_path, monkeypatch):
    configuration.save_configuration(tmp_path, {
        'service': 'gemini',
        'base_url': 'https://generativelanguage.googleapis.com/',
        'api_key': 'AIzaSy-test-key-123456789012345',
        'model': 'gemini-1.5-pro',
        'api_type': 'gemini',
    })

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {'models': [
                {'name': 'models/gemini-2.5-pro', 'supportedGenerationMethods': ['generateContent']},
                {'name': 'models/embedding-001', 'supportedGenerationMethods': ['embedContent']},
            ]}

    calls = []
    monkeypatch.setattr(configuration, '_get_models_response', lambda url, headers: (calls.append(url) or Response()))
    assert configuration.discover_models(tmp_path) == ['models/gemini-2.5-pro']
    assert calls[0].startswith('https://generativelanguage.googleapis.com/v1beta/models?key=')


def test_anthropic_messages_are_normalized_to_project_response_shape():
    body = AnthropicAdapter._request_body([
        ChatMessage('system', 'You are concise.'), ChatMessage('user', 'Hello')
    ], 'claude-sonnet-5', {'max_tokens': 200, 'temperature': 0.2, 'stream': False})
    assert body['system'] == 'You are concise.'
    assert body['messages'] == [{'role': 'user', 'content': 'Hello'}]
    assert body['max_tokens'] == 200
    assert body['stream'] is False

    config = AIConfig('anthropic', 'anthropic', 'https://api.anthropic.com', 'test-key', 'claude-sonnet-5')
    adapter = AnthropicAdapter(config, enable_cache=False, enable_retry=False)
    try:
        assert adapter.test_connection()['status'] == 'success'
        assert adapter.get_available_models() == []
    finally:
        adapter.close()


def test_gemini_three_reasoning_levels_are_normalized():
    messages = [ChatMessage('user', 'Hello')]
    config = AIConfig('gemini', 'gemini', 'https://generativelanguage.googleapis.com/', 'test-key', 'gemini-3-pro')
    adapter = GeminiAdapter(config, enable_cache=False, enable_retry=False)
    captured = []

    def fake_send(request_data, model_id):
        captured.append(request_data)
        return {'candidates': [{'content': {'parts': [{'text': 'ok'}]}}]}

    adapter._send_regular_message = fake_send
    try:
        adapter.send_message(messages, 'gemini-3-pro', {'reasoning_effort': 'none'})
        adapter.send_message(messages, 'gemini-3-pro', {'reasoning_effort': 'max'})
        assert captured[0]['generationConfig']['thinkingConfig'] == {'thinkingLevel': 'low'}
        assert captured[1]['generationConfig']['thinkingConfig'] == {'thinkingLevel': 'high'}
        assert 'temperature' not in captured[0]['generationConfig']
    finally:
        adapter.close()


def test_known_protocol_capabilities_are_validated():
    assert validate_options({'query': 'q', 'ai_provider': 'volcengine_ark', 'ai_protocol': 'openai_responses'})['ai_protocol'] == 'openai_responses'
    assert validate_options({'query': 'q', 'ai_provider': 'gemini', 'ai_protocol': 'openai'})['ai_protocol'] == 'gemini'
    try:
        validate_options({'query': 'q', 'ai_provider': 'zhipu', 'ai_protocol': 'openai_responses'})
    except ValueError as error:
        assert 'Responses' in str(error)
    else:
        raise AssertionError('zhipu Responses should be rejected')


def test_local_provider_can_use_defaults_without_an_api_key(monkeypatch):
    monkeypatch.setenv('DEFAULT_AI_SERVICE', 'ollama')
    monkeypatch.delenv('OLLAMA_API_KEY', raising=False)
    monkeypatch.delenv('OLLAMA_BASE_URL', raising=False)
    reset_ai_config_cache()
    config = get_ai_config(force_reload=True)
    try:
        service = config.get_service('ollama')
        assert service.is_valid()
        assert service.base_url == 'http://localhost:11434/v1'
    finally:
        reset_ai_config_cache()
