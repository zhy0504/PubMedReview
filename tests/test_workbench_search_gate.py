import io
import json
from types import SimpleNamespace

import pytest

from intelligent_literature_system import IntelligentLiteratureSystem
from workbench.validation import validate_options
from workbench.worker import EventChannel


def test_explicit_gate_overrides_noninteractive_default():
    calls = []
    system = SimpleNamespace(interactive_mode=False, review_confirmation=lambda: calls.append('asked') or False)
    assert IntelligentLiteratureSystem._ask_user_continue(system) is False
    assert calls == ['asked']
    system.review_confirmation = lambda: True
    assert IntelligentLiteratureSystem._ask_user_continue(system) is True


def test_review_prompt_has_typed_purpose(monkeypatch):
    monkeypatch.setattr('workbench.worker.uuid.uuid4', lambda: SimpleNamespace(hex='test-prompt'))
    output = io.StringIO()
    channel = EventChannel(output, io.StringIO(json.dumps({'prompt_id': 'test-prompt', 'value': 'start_review'}) + '\n'))
    assert channel.ask('Confirm', purpose='start_review') == 'start_review'
    assert json.loads(output.getvalue())['payload']['purpose'] == 'start_review'


@pytest.mark.parametrize('field,value', [('year_start', -1), ('year_end', True), ('jcr', 5), ('cas', None), ('cas', True), ('min_if', float('nan'))])
def test_filters_reject_invalid_values(field, value):
    filters = {'year_start': None, 'year_end': None, 'min_if': None, 'jcr': 0, 'cas': 0, 'new_rui_2026': 0}
    filters[field] = value
    with pytest.raises(ValueError):
        validate_options({'query': 'test', 'search_filters': filters})


def test_structured_conditions_survive_validation():
    filters = {'year_start': 2020, 'year_end': None, 'min_if': 3, 'jcr': 2, 'cas': 1, 'new_rui_2026': 0}
    result = validate_options({'query': 'test', 'search_filters': filters})
    assert result['search_filters'] == filters
    assert result['max_results'] == 500
    assert result['target'] == 50

