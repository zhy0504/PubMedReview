from types import SimpleNamespace

from intent_analyzer import IntentAnalyzer


def test_error_response_falls_back_without_polluting_query():
    analyzer = IntentAnalyzer.__new__(IntentAnalyzer)
    analyzer.enable_cache = False
    analyzer.analysis_cache = None
    analyzer.model_id = 'deepseek-v4-flash'
    analyzer.model_parameters = {'stream': True}
    analyzer.performance_stats = {
        'total_analyses': 0,
        'cache_hits': 0,
        'ai_calls': 0,
        'total_latency': 0.0,
        'errors': 0,
    }
    analyzer._build_analysis_prompt = lambda _: 'prompt'
    analyzer.adapter = SimpleNamespace(
        config=SimpleNamespace(api_type='openai_responses'),
        send_message=lambda *_args: {'error': 'AI 请求失败 (SSLError, HTTP N/A)'},
    )

    criteria = analyzer.analyze_intent('原始检索主题')

    assert criteria.query == '原始检索主题'
    assert analyzer.performance_stats['errors'] == 1
