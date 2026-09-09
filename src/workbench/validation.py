"""Explicit request contract shared by HTTP and task execution."""


DEFAULTS = {
    'max_results': 500, 'target': 50, 'ai_config': '',
    'interactive_ai': False, 'confirm_steps': True, 'cache': True,
    'temperature': None, 'max_tokens': None, 'review_format': '', 'model': '',
    'intent_model': '', 'outline_model': '', 'review_model': '',
    'intent_reasoning': 'low', 'outline_reasoning': 'low', 'review_reasoning': 'medium',
    'ai_protocol': 'openai',
    'topic_details': '', 'topic_outcomes': '',
    'search_filters': None,
}


def validate_options(data, require_query=True):
    if not isinstance(data, dict):
        raise ValueError('请提交 JSON 对象')
    allowed = set(DEFAULTS) | ({'query'} if require_query else set())
    if set(data) - allowed:
        raise ValueError('包含不支持的参数')
    result = {**DEFAULTS, **data}
    if require_query:
        query = result.get('query')
        if not isinstance(query, str) or not query.strip() or len(query) > 5000:
            raise ValueError('请输入 1–5000 字的检索需求')
        result['query'] = query.strip()
    for key in ('max_results', 'target'):
        if type(result[key]) is not int or not 1 <= result[key] <= 10000:
            raise ValueError(f'{key} 必须是 1–10000 的整数')
    for key in ('interactive_ai', 'confirm_steps', 'cache'):
        if type(result[key]) is not bool:
            raise ValueError(f'{key} 必须是布尔值')
    if result['temperature'] is not None and (type(result['temperature']) not in (int, float) or not 0 <= float(result['temperature']) <= 2):
        raise ValueError('temperature 必须在 0–2 之间')
    if result['max_tokens'] is not None and (type(result['max_tokens']) is not int or not 1 <= result['max_tokens'] <= 100000):
        raise ValueError('max_tokens 必须为空或为 1–100000 的整数')
    if not isinstance(result['review_format'], str) or result['review_format'] not in {'', 'md', 'docx', 'both'}:
        raise ValueError('review_format 必须是 md、docx 或 both')
    if not isinstance(result['ai_config'], str) or len(result['ai_config']) > 100:
        raise ValueError('AI 配置名称无效')
    result['ai_config'] = result['ai_config'].strip()
    if result['ai_protocol'] not in {'openai', 'openai_responses'}:
        raise ValueError('仅支持 OpenAI Chat Completions 或 OpenAI Responses')
    if not isinstance(result['model'], str) or len(result['model']) > 150:
        raise ValueError('模型名称无效')
    result['model'] = result['model'].strip()
    for key in ('intent_model', 'outline_model', 'review_model'):
        if not isinstance(result[key], str) or len(result[key]) > 150:
            raise ValueError(f'{key} 无效')
        result[key] = result[key].strip()
    for key in ('intent_reasoning', 'outline_reasoning', 'review_reasoning'):
        if result[key] not in {'none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'}:
            raise ValueError(f'{key} 无效')
    for key in ('topic_details', 'topic_outcomes'):
        if not isinstance(result[key], str) or len(result[key]) > 1000:
            raise ValueError('主题补充最多 1000 字')
    filters = result['search_filters']
    if filters is not None:
        from datetime import date
        current_year = date.today().year
        if isinstance(filters, dict) and set(filters) == {'years', 'min_if', 'jcr', 'cas'}:
            years = filters['years']
            if type(years) is not int or not 0 <= years <= 100:
                raise ValueError('年份范围无效')
            filters = {key: value for key, value in filters.items() if key != 'years'}
            filters.update(year_start=current_year - years + 1 if years else None, year_end=current_year if years else None)
            result['search_filters'] = filters
        if not isinstance(filters, dict) or set(filters) != {'year_start', 'year_end', 'min_if', 'jcr', 'cas', 'new_rui_2026'}:
            raise ValueError('检索条件格式无效')
        for key, minimum, maximum in (('year_start', 1900, current_year), ('year_end', 1900, current_year), ('jcr', 0, 4), ('cas', 0, 4), ('new_rui_2026', 0, 4)):
            if filters[key] is None and key.startswith('year_'):
                continue
            if type(filters[key]) is not int or not minimum <= filters[key] <= maximum:
                raise ValueError(f'{key} 范围无效')
        if filters['year_start'] and filters['year_end'] and filters['year_end'] < filters['year_start']:
            raise ValueError('终止年份不能早于起始年份')
        if filters['min_if'] is not None and (type(filters['min_if']) not in (int, float) or not 0 <= filters['min_if'] <= 100):
            raise ValueError('最低影响因子范围无效')
    return result

