import json
from pathlib import Path
from types import SimpleNamespace

from medical_review_generator import MedicalReviewGenerator


def _build_generator(responses):
    generator = MedicalReviewGenerator.__new__(MedicalReviewGenerator)
    generator.model_id = 'deepseek-v4-flash'
    generator.model_parameters = {'stream': True, 'max_tokens': None}
    generator.prompts_manager = SimpleNamespace(
        get_review_generation_prompt=lambda **_kwargs: 'review prompt'
    )
    calls = []

    def send_message(_messages, _model, parameters):
        calls.append(dict(parameters))
        return responses.pop(0)

    generator.adapter = SimpleNamespace(
        config=SimpleNamespace(api_type='openai_responses'),
        send_message=send_message,
    )

    def format_response(response, _api_type):
        if response.get('error'):
            return f"错误: {response['error']}"
        return response['choices'][0]['message']['content']

    generator.ai_client = SimpleNamespace(format_response=format_response)
    generator._save_raw_output = lambda *_args, **_kwargs: None
    return generator, calls


def _input_files(tmp_path: Path):
    outline = tmp_path / 'outline.md'
    outline.write_text(
        '# 综述标题\n\n## 1. 引言\n\n围绕研究问题展开综述，说明研究背景、证据范围、关键影响因素和干预策略。',
        encoding='utf-8',
    )
    literature = tmp_path / 'literature.json'
    literature.write_text(json.dumps([
        {
            'id': 1,
            'title': '第一篇研究',
            'authors': '作者甲',
            'journal': '期刊甲',
            'publication_date': '2024-01-01',
            'doi': '',
            'abstract': '摘要',
            'url': 'https://pubmed.ncbi.nlm.nih.gov/1',
        }
    ], ensure_ascii=False), encoding='utf-8')
    return outline, literature


def test_complete_article_retries_unbounded_output_limit(tmp_path):
    generator, calls = _build_generator([
        {
            'error': 'Responses 生成未完成：max_output_tokens',
            'incomplete_reason': 'max_output_tokens',
        },
        {'choices': [{'message': {'content': '# 综述标题\n\n正文引用[1]。'}}]},
    ])
    outline, literature = _input_files(tmp_path)

    result = generator.generate_complete_review_article(str(outline), str(literature), '综述标题')

    assert result.startswith('# 综述标题')
    assert 'Responses 生成未完成' not in result
    assert calls == [
        {'stream': True, 'max_tokens': None},
        {'stream': True, 'max_tokens': 20000},
    ]


def test_complete_article_stops_on_bounded_output_error(tmp_path):
    generator, calls = _build_generator([
        {
            'error': 'Responses 生成未完成：max_output_tokens',
            'incomplete_reason': 'max_output_tokens',
        }
    ])
    generator.model_parameters['max_tokens'] = 500
    outline, literature = _input_files(tmp_path)

    result = generator.generate_complete_review_article(str(outline), str(literature), '综述标题')

    assert result == ''
    assert calls == [{'stream': True, 'max_tokens': 500}]
