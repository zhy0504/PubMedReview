"""Local credentials stay outside the history database."""

from dotenv import dotenv_values, set_key
import os
from urllib.parse import urlsplit
from urllib.parse import quote
import requests

from ai_providers import PROVIDER_PROFILES, get_provider, provider_for_url, provider_options
from openai_protocol import endpoint


def _load_values(root):
    env_file = root / '.env'
    values = dict(dotenv_values(env_file))
    if env_file.exists():
        return values
    return {key: value for key, value in os.environ.items()
            if key == 'DEFAULT_AI_SERVICE' or key.endswith(('_API_KEY', '_BASE_URL', '_MODEL', '_API_TYPE'))}


def _service_values(values, service):
    profile = get_provider(service) or get_provider('openai_proxy')
    prefix = profile.env_prefix
    return {
        'service': profile.id,
        'base_url': values.get(f'{prefix}_BASE_URL') or profile.base_url,
        'api_key': values.get(f'{prefix}_API_KEY') or '',
        'model': values.get(f'{prefix}_MODEL') or profile.default_model,
        'api_type': values.get(f'{prefix}_API_TYPE') or profile.api_type,
    }


def _effective_ai_values(values):
    """Resolve the selected service while preserving old OpenAI-only .env files."""
    explicit = str(values.get('DEFAULT_AI_SERVICE') or '').strip().lower()
    if explicit in PROVIDER_PROFILES:
        selected = _service_values(values, explicit)
        profile = get_provider(explicit)
        if selected['api_key'] or not profile.requires_api_key:
            return selected
    for service in PROVIDER_PROFILES:
        if service == 'openai_proxy':
            continue
        profile = get_provider(service)
        if not profile:
            continue
        key = values.get(f'{profile.env_prefix}_API_KEY')
        if key:
            base_url = values.get(f'{profile.env_prefix}_BASE_URL') or profile.base_url
            if service == 'openai':
                detected = provider_for_url(base_url)
                if detected != 'openai_proxy':
                    return {**_service_values(values, 'openai'), 'service': detected}
            return _service_values(values, service)
    return _service_values(values, 'openai')


def _get_models_response(url, headers):
    """Fetch models with a bounded direct-connection fallback for TLS failures."""
    try:
        return requests.get(url, headers=headers, timeout=30, allow_redirects=False)
    except (requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        session = requests.Session()
        session.trust_env = False
        try:
            return session.get(url, headers=headers, timeout=30, allow_redirects=False)
        finally:
            session.close()


def read_configuration(root):
    values = _load_values(root)
    ai = _effective_ai_values(values)
    profile = get_provider(ai['service']) or get_provider('openai_proxy')
    return {'service': ai['service'], 'provider': ai['service'], 'api_type': ai['api_type'],
            'base_url': ai['base_url'], 'model': ai['model'],
            'api_key_configured': bool(ai['api_key']),
            'pubmed_key_configured': bool(values.get('PUBMED_API_KEY')),
            'pubmed_requests_per_second': 10 if values.get('PUBMED_API_KEY') else 3,
            'requires_api_key': profile.requires_api_key,
            'supports_responses': profile.supports_responses,
            'providers': provider_options()}


def save_configuration(root, data):
    allowed = {'service', 'provider', 'ai_provider', 'api_type', 'base_url', 'api_key', 'model', 'pubmed_api_key'}
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValueError('配置字段无效')
    if any(not isinstance(value, str) or len(value) > 4096 or '\n' in value or '\r' in value for value in data.values()):
        raise ValueError('配置值无效')
    service = str(data.get('service') or data.get('provider') or data.get('ai_provider') or 'openai').strip().lower()
    profile = get_provider(service)
    if profile is None:
        raise ValueError('不支持的 AI 服务')
    base = str(data.get('base_url', '') or '').strip() or profile.base_url
    if not base:
        raise ValueError('请填写 API 基础地址')
    if base:
        parsed = urlsplit(base)
        if parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('请输入有效 API 基础地址')
        if parsed.scheme == 'http' and parsed.hostname not in {'localhost', '127.0.0.1', '::1'}:
            raise ValueError('远程接口必须使用 HTTPS')
    protocol = str(data.get('api_type') or profile.api_type).strip().lower()
    if profile.api_type in {'gemini', 'anthropic'}:
        protocol = profile.api_type
    elif protocol not in {'openai', 'openai_responses'}:
        raise ValueError('该服务仅支持 OpenAI Chat Completions 或 OpenAI Responses')
    if protocol == 'openai_responses' and not profile.supports_responses:
        raise ValueError(f'{profile.label} 未声明支持 OpenAI Responses')
    prefix = profile.env_prefix
    set_key(root / '.env', 'DEFAULT_AI_SERVICE', profile.id)
    set_key(root / '.env', f'{prefix}_BASE_URL', base)
    set_key(root / '.env', f'{prefix}_API_TYPE', protocol)
    for field, env in {'api_key': f'{prefix}_API_KEY', 'model': f'{prefix}_MODEL', 'pubmed_api_key': 'PUBMED_API_KEY'}.items():
        value = str(data.get(field, '') or '').strip()
        if value:
            set_key(root / '.env', env, value)
    return read_configuration(root)


def discover_models(root):
    values = _load_values(root)
    ai = _effective_ai_values(values)
    if not ai['api_key']:
        profile = get_provider(ai['service'])
        if profile and profile.requires_api_key:
            raise ValueError('请先保存当前 AI 服务的 API Key')
    profile = get_provider(ai['service']) or get_provider('openai_proxy')
    if profile.api_type == 'anthropic' or not profile.supports_model_discovery:
        raise ValueError(f'{profile.label} 不提供模型列表接口，请手动填写模型名称')
    try:
        if profile.api_type == 'gemini':
            url = ai['base_url'].rstrip('/') + '/v1beta/models?key=' + quote(ai['api_key'])
            response = _get_models_response(url, headers={'Accept': 'application/json'})
        else:
            headers = {'Accept': 'application/json'}
            if ai['api_key']:
                headers['Authorization'] = 'Bearer ' + ai['api_key']
            response = _get_models_response(endpoint(ai['base_url'], 'models', provider=ai['service']),
                headers=headers)
        response.raise_for_status()
        data = response.json()
        if profile.api_type == 'gemini':
            models = []
            for item in data.get('models', []) if isinstance(data, dict) else []:
                if 'generateContent' in item.get('supportedGenerationMethods', []):
                    name = item.get('name')
                    if isinstance(name, str) and name:
                        models.append(name)
            return sorted(set(models))
        if not isinstance(data, dict) or not isinstance(data.get('data'), list):
            raise ValueError('模型接口未返回 data 列表')
        return sorted({item['id'] for item in data['data'] if isinstance(item, dict) and isinstance(item.get('id'), str) and item['id']})
    except requests.HTTPError as error:
        response = getattr(error, 'response', None)
        code = getattr(response, 'status_code', None)
        detail = ''
        try:
            payload = response.json() if response is not None else {}
            api_error = payload.get('error') if isinstance(payload, dict) else None
            message = api_error.get('message') if isinstance(api_error, dict) else None
            if message:
                detail = f'：{message}'
        except (ValueError, AttributeError):
            pass
        if code in {404, 405}:
            raise ValueError('当前 AI 服务不提供模型列表接口，请手动填写模型名称') from None
        raise ValueError(f'模型获取失败，HTTP {code or "连接失败"}{detail}') from None
    except requests.RequestException as error:
        code = getattr(getattr(error, 'response', None), 'status_code', None)
        raise ValueError(f'模型获取失败，HTTP {code or "连接失败"}') from None
