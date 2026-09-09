"""Local credentials stay outside the history database."""

from dotenv import dotenv_values, set_key
from urllib.parse import urlsplit
import requests

from openai_protocol import endpoint


def read_configuration(root):
    values = dotenv_values(root / '.env')
    return {'base_url': values.get('OPENAI_BASE_URL') or 'https://api.openai.com',
            'api_key_configured': bool(values.get('OPENAI_API_KEY')),
            'pubmed_key_configured': bool(values.get('PUBMED_API_KEY')),
            'pubmed_requests_per_second': 10 if values.get('PUBMED_API_KEY') else 3}


def save_configuration(root, data):
    if not isinstance(data, dict) or set(data) - {'base_url', 'api_key', 'pubmed_api_key'}:
        raise ValueError('配置字段无效')
    if any(not isinstance(value, str) or len(value) > 4096 or '\n' in value or '\r' in value for value in data.values()):
        raise ValueError('配置值无效')
    base = data.get('base_url', '').strip()
    if base:
        parsed = urlsplit(base)
        if parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('请输入有效 API 基础地址')
        if parsed.scheme == 'http' and parsed.hostname not in {'localhost', '127.0.0.1', '::1'}:
            raise ValueError('远程接口必须使用 HTTPS')
    for field, env in {'base_url': 'OPENAI_BASE_URL', 'api_key': 'OPENAI_API_KEY', 'pubmed_api_key': 'PUBMED_API_KEY'}.items():
        value = data.get(field, '').strip()
        if value:
            set_key(root / '.env', env, value)
    return read_configuration(root)


def discover_models(root):
    values = dotenv_values(root / '.env')
    if not values.get('OPENAI_API_KEY'):
        raise ValueError('请先保存 AI API Key')
    try:
        response = requests.get(endpoint(values.get('OPENAI_BASE_URL') or 'https://api.openai.com', 'models'),
            headers={'Authorization': 'Bearer ' + values['OPENAI_API_KEY']}, timeout=30, allow_redirects=False)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data.get('data'), list):
            raise ValueError('模型接口未返回 data 列表')
        return sorted({item['id'] for item in data['data'] if isinstance(item, dict) and isinstance(item.get('id'), str) and item['id']})
    except requests.RequestException as error:
        code = getattr(getattr(error, 'response', None), 'status_code', None)
        raise ValueError(f'模型获取失败，HTTP {code or "连接失败"}') from None
