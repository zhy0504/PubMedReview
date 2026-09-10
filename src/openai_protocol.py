"""Stateless OpenAI text requests with protocol-specific wire formats."""

import json
from urllib.parse import urlsplit

import requests

from ai_providers import is_versioned_path, resolve_provider


def is_deepseek_url(base_url):
    """Return whether a base URL belongs to the official DeepSeek API."""
    try:
        hostname = (urlsplit(str(base_url or '')).hostname or '').lower()
    except ValueError:
        return False
    return hostname == 'api.deepseek.com' or hostname.endswith('.deepseek.com')


def is_zhipu_url(base_url):
    """Return whether a base URL belongs to Zhipu's OpenAI-compatible API."""
    try:
        hostname = (urlsplit(str(base_url or '')).hostname or '').lower()
    except ValueError:
        return False
    return hostname == 'open.bigmodel.cn' or hostname.endswith('.bigmodel.cn')


def provider_profile(base_url=None, provider=None):
    """Resolve the provider profile without requiring callers to know its host."""
    return resolve_provider(provider, base_url)


def endpoint(base_url, path, provider=None):
    """Build a protocol endpoint without duplicating provider API prefixes."""
    base = str(base_url or '').rstrip('/')
    provider_name = str(provider or '').strip().lower()
    deepseek_host = is_deepseek_url(base)
    zhipu_host = is_zhipu_url(base)
    if deepseek_host:
        if base.lower().endswith('/v1'):
            base = base[:-3].rstrip('/')
    elif provider_name in {'deepseek', 'zhipu'} or zhipu_host:
        return base + '/' + str(path).lstrip('/')
    elif not is_versioned_path(urlsplit(base).path):
        base += '/v1'
    return base + '/' + str(path).lstrip('/')


def is_model_compatible(base_url, model, provider=None):
    """Reject stale non-DeepSeek model IDs when using the direct API."""
    # A legacy configuration may keep ``OPENAI`` as its service name while
    # pointing at a DeepSeek or Zhipu URL.  For those official hosts the URL
    # is authoritative, otherwise an old OpenAI model can leak into the call.
    if is_deepseek_url(base_url):
        profile = resolve_provider('deepseek', base_url)
    elif is_zhipu_url(base_url):
        profile = resolve_provider('zhipu', base_url)
    else:
        profile = provider_profile(base_url, provider)
    model_name = str(model or '').strip().lower()
    if not profile or not profile.model_prefixes:
        return True
    return model_name.startswith(tuple(prefix.lower() for prefix in profile.model_prefixes))


def _deepseek_chat_effort(value):
    value = str(value or '').strip().lower()
    return {'minimal': 'low', 'medium': 'high', 'xhigh': 'high'}.get(value, value)


def build_request(messages, model, parameters, protocol, base_url=None, provider=None):
    protocol = str(protocol or 'openai').lower()
    params = {key: value for key, value in (parameters or {}).items() if value is not None}
    limit = params.pop('max_tokens', None)
    effort = params.pop('reasoning_effort', None)
    params.setdefault('stream', True)
    provider_name = str(provider or '').strip().lower()
    profile = provider_profile(base_url, provider_name)
    deepseek = is_deepseek_url(base_url) or provider_name == 'deepseek'
    zhipu = is_zhipu_url(base_url) or provider_name == 'zhipu'
    request_style = profile.request_style if profile else 'legacy'
    compatible_chat = request_style != 'openai' or deepseek or zhipu
    if compatible_chat:
        params.pop('store', None)
        params.pop('max_completion_tokens', None)
    else:
        params['store'] = False
    if not deepseek and model.startswith(('o1', 'o3', 'o4', 'gpt-5', 'gpt-6')):
        for key in ('temperature', 'top_p', 'frequency_penalty', 'presence_penalty', 'logprobs', 'top_logprobs'):
            params.pop(key, None)
    items = [{'role': item.role, 'content': item.content} for item in messages]
    if protocol == 'openai_responses':
        if limit is not None:
            params['max_output_tokens'] = limit
        if effort and (profile is None or profile.supports_responses):
            params['reasoning'] = {'effort': effort}
        return {'model': model, 'input': items, **params}
    if limit is not None:
        params['max_tokens' if compatible_chat else 'max_completion_tokens'] = limit
    if effort and deepseek:
        if str(effort).strip().lower() == 'none':
            params['thinking'] = {'type': 'disabled'}
        else:
            params['thinking'] = {'type': 'enabled'}
            params['reasoning_effort'] = _deepseek_chat_effort(effort)
            for key in ('temperature', 'top_p', 'frequency_penalty', 'presence_penalty', 'logprobs', 'top_logprobs'):
                params.pop(key, None)
    elif effort and zhipu:
        params['reasoning_effort'] = effort
        params['thinking'] = {'type': 'disabled' if str(effort).strip().lower() == 'none' else 'enabled'}
    elif effort and provider_name in {'openai', 'openai_proxy', 'moonshot', 'groq'}:
        params['reasoning_effort'] = effort
    return {'model': model, 'messages': items, **params}


def normalize_response(data, protocol):
    if data.get('error'):
        return {'error': 'AI 接口返回错误'}
    if protocol == 'openai_responses':
        if data.get('status') != 'completed':
            return {'error': 'Responses 未完整完成生成：' + str(data.get('status', 'unknown'))}
        content = ''.join(part.get('text', '') for item in data.get('output', [])
                          if item.get('type') == 'message' for part in item.get('content', [])
                          if part.get('type') == 'output_text')
        usage = data.get('usage') or {}
        return {'choices': [{'message': {'role': 'assistant', 'content': content}}], 'usage': usage}
    choices = data.get('choices', [])
    if not choices or choices[0].get('finish_reason') not in ('stop', None):
        return {'error': 'Chat Completions 未完整完成生成'}
    return data


def send_text(session, config, messages, model, parameters):
    protocol = config.api_type.lower()
    provider = getattr(config, 'service_name', None) or getattr(config, 'name', None)
    body = build_request(messages, model, parameters, protocol, config.base_url, provider)
    path = 'responses' if protocol == 'openai_responses' else 'chat/completions'
    try:
        with session.post(endpoint(config.base_url, path, provider=provider), json=body,
                          stream=body['stream'], timeout=config.timeout) as response:
            response.raise_for_status()
            if not body['stream']:
                return normalize_response(response.json(), protocol)
            parts = []
            usage = {}
            finished = False
            for line in response.iter_lines():
                if not line or not line.startswith(b'data:'):
                    continue
                value = line[5:].strip()
                if value == b'[DONE]':
                    break
                event = json.loads(value)
                if event.get('error') or event.get('type') in ('error', 'response.failed', 'response.incomplete'):
                    return {'error': 'AI 流式生成失败或不完整'}
                if protocol == 'openai_responses':
                    if event.get('type') == 'response.completed':
                        return normalize_response(event['response'], protocol)
                else:
                    usage = event.get('usage') or usage
                    for choice in event.get('choices', []):
                        parts.append(choice.get('delta', {}).get('content') or '')
                        reason = choice.get('finish_reason')
                        if reason and reason != 'stop':
                            return {'error': 'AI 输出截断或被拒绝：' + reason}
                        finished = finished or reason == 'stop'
            if not finished:
                return {'error': 'AI 连接中断，未收到完整结束事件'}
            return {'choices': [{'message': {'role': 'assistant', 'content': ''.join(parts)}}], 'usage': usage}
    except (requests.RequestException, ValueError, KeyError) as error:
        status = getattr(getattr(error, 'response', None), 'status_code', None)
        return {'error': f'AI 请求失败 ({type(error).__name__}, HTTP {status or "N/A"})'}
