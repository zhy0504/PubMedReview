"""Stateless OpenAI text requests with protocol-specific wire formats."""

import json

import requests


def endpoint(base_url, path):
    base = base_url.rstrip('/')
    if not base.endswith('/v1'):
        base += '/v1'
    return base + '/' + path


def build_request(messages, model, parameters, protocol):
    params = {key: value for key, value in (parameters or {}).items() if value is not None}
    limit = params.pop('max_tokens', None)
    effort = params.pop('reasoning_effort', None)
    params.setdefault('stream', True)
    params['store'] = False
    if model.startswith(('o1', 'o3', 'o4', 'gpt-5', 'gpt-6')):
        for key in ('temperature', 'top_p', 'frequency_penalty', 'presence_penalty', 'logprobs', 'top_logprobs'):
            params.pop(key, None)
    items = [{'role': item.role, 'content': item.content} for item in messages]
    if protocol == 'openai_responses':
        if limit is not None:
            params['max_output_tokens'] = limit
        if effort:
            params['reasoning'] = {'effort': effort}
        return {'model': model, 'input': items, **params}
    if limit is not None:
        params['max_completion_tokens'] = limit
    if effort:
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
    body = build_request(messages, model, parameters, protocol)
    path = 'responses' if protocol == 'openai_responses' else 'chat/completions'
    try:
        with session.post(endpoint(config.base_url, path), json=body,
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
