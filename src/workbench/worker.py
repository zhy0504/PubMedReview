"""Isolated adapter for the unchanged interactive workflow and JSONL events."""

import asyncio
import builtins
import io
import json
import os
import re
import sys
import threading
import uuid
from pathlib import Path


class EventChannel:
    def __init__(self, output, input_stream, secrets=()):
        self.output = output
        self.input = input_stream
        self.lock = threading.RLock()
        self.secrets = sorted({value for value in secrets if value and len(value) >= 6}, key=len, reverse=True)

    def redact(self, text):
        text = str(text)
        for value in self.secrets:
            text = text.replace(value, '[REDACTED]')
        text = re.sub(r'(?i)(bearer\s+)[^\s\"\']+', r'\1[REDACTED]', text)
        text = re.sub(r'(?i)((?:api[_ -]?key|token|password)\s*[=:]\s*)[^\s,;]+', r'\1[REDACTED]', text)
        return re.sub(r'\b(?:sk-[\w-]{8,}|AIza[\w-]{20,})\b', '[REDACTED]', text)

    def emit(self, kind, payload):
        def sanitize(value):
            if isinstance(value, str):
                return self.redact(value)
            if isinstance(value, dict):
                return {key: sanitize(item) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return [sanitize(item) for item in value]
            return value
        serialized = json.dumps({'kind': kind, 'payload': sanitize(payload)}, ensure_ascii=False, default=str)
        with self.lock:
            self.output.write(serialized + '\n')
            self.output.flush()

    def ask(self, prompt='', purpose=None):
        sys.stdout.flush()
        prompt_id = uuid.uuid4().hex
        self.emit('prompt', {'id': prompt_id, 'purpose': purpose, 'text': str(prompt) or '请根据运行日志回答', 'sensitive': bool(re.search(r'(?i)key|密钥|password|密码|token', str(prompt)))})
        line = self.input.readline()
        if not line:
            raise EOFError('工作台输入通道已关闭')
        response = json.loads(line)
        if response.get('prompt_id') != prompt_id:
            raise ValueError('交互响应与当前提示不匹配')
        value = str(response.get('value', ''))
        if re.search(r'(?i)key|密钥|password|密码|token', str(prompt)) and len(value) >= 6:
            self.secrets.append(value)
        return value


class EventOutput(io.TextIOBase):
    def __init__(self, channel):
        self.channel = channel
        self.pending = ''
        self.lock = threading.RLock()

    @property
    def encoding(self):
        return 'utf-8'

    def writable(self):
        return True

    def write(self, text):
        with self.lock:
            self.pending += text
            while '\n' in self.pending or len(self.pending) > 2000:
                if '\n' in self.pending:
                    line, self.pending = self.pending.split('\n', 1)
                else:
                    line, self.pending = self.pending[:2000], self.pending[2000:]
                if line.strip():
                    self.channel.emit('log', {'text': line[:4000]})
        return len(text)

    def flush(self):
        with self.lock:
            if self.pending:
                self.channel.emit('log', {'text': self.pending[:4000]})
                self.pending = ''


def apply_model_options(system, options):
    for component, model_key, reasoning_key in ((system.intent_analyzer, 'intent_model', 'intent_reasoning'), (system.outline_generator, 'outline_model', 'outline_reasoning'), (system.review_generator, 'review_model', 'review_reasoning')):
        if component is None:
            continue
        model = options.get(model_key) or options.get('model')
        if model and hasattr(component, 'model_id'): component.model_id = model
        if hasattr(component, 'adapter') and component.adapter:
            component.adapter.config.api_type = options.get('ai_protocol', 'openai')
        if hasattr(component, 'model_parameters'):
            component.model_parameters.pop('temperature', None)
            component.model_parameters.pop('max_tokens', None)
            component.model_parameters['reasoning_effort'] = options[reasoning_key]
            if options['temperature'] is not None:
                component.model_parameters['temperature'] = options['temperature']
            if options['max_tokens'] is not None:
                component.model_parameters['max_tokens'] = options['max_tokens']


async def execute(options, channel):
    os.environ['DEFAULT_AI_SERVICE'] = 'openai'
    os.environ['OPENAI_API_TYPE'] = options.get('ai_protocol', 'openai')
    if options['model']:
        os.environ['OPENAI_MODEL'] = options['model']
    from shared_config import system_config
    if options['review_format']:
        system_config._config_data.setdefault('export', {})['review_format'] = options['review_format']
    from intelligent_literature_system import IntelligentLiteratureSystem
    channel.emit('stage', {'stage': 'initializing'})
    system = IntelligentLiteratureSystem(
        ai_config_name='openai',
        interactive_mode=False, enable_cache=True,
        enable_state=False, event_sink=channel.emit,
    )
    if not await system.initialize_components():
        return {'success': False, 'error': '系统初始化失败'}
    apply_model_options(system, options)
    system.interactive_mode = False
    system.review_confirmation = lambda: channel.ask('请确认检索结果后开始综述', purpose='start_review') == 'start_review'
    filters = options.get('search_filters')
    if filters is not None:
        from datetime import date
        year = date.today().year
        system.criteria_overrides = {
            'year_start': filters['year_start'], 'year_end': filters['year_end'] or (year if filters['year_start'] else None),
            'min_if': filters['min_if'] or None, 'max_if': None,
            'jcr_quartiles': [f'Q{value}' for value in range(1, filters['jcr'] + 1)],
            'cas_zones': list(range(1, filters['cas'] + 1)),
            'new_rui_2026': list(range(1, filters['new_rui_2026'] + 1)),
        }
    query = '；'.join(value for value in (options['query'], options.get('topic_details'), options.get('topic_outcomes')) if value)
    result = await system.run_complete_workflow(
        user_query=query, max_results=min(max(options['target'] * 8, 100), 2000),
        target_articles=options['target'], enable_resume=False,
    )
    return result


def main():
    from dotenv import load_dotenv
    from workbench.validation import validate_options
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)
    load_dotenv(root / '.env')
    options = validate_options(json.loads(sys.stdin.readline()))
    channel = EventChannel(sys.stdout, sys.stdin, [value for key, value in os.environ.items() if any(word in key.upper() for word in ('KEY', 'TOKEN', 'PASSWORD', 'SECRET'))])
    sys.stdout = EventOutput(channel)
    sys.stderr = sys.stdout
    builtins.input = channel.ask
    try:
        result = asyncio.run(execute(options, channel))
        channel.emit('result', result)
    except Exception as error:
        channel.emit('result', {'success': False, 'error': str(error)})
    finally:
        sys.stdout.flush()


if __name__ == '__main__':
    main()

