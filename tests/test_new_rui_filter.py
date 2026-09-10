import pytest

from intent_analyzer import SearchCriteria
from intelligent_literature_system import IntelligentLiteratureSystem
from literature_filter import LiteratureFilter


@pytest.mark.parametrize('limit', range(5))
def test_new_rui_threshold_in_both_filter_paths(limit):
    criteria = SearchCriteria(query='test', new_rui_2026=list(range(1, limit + 1)))
    records = [{'pmid': str(zone), 'journal_info': {'new_rui_zone': zone, 'new_rui_2026': zone is not None}}
               for zone in (1, 2, 3, 4, None)]
    expected = [str(zone) for zone in (1, 2, 3, 4, None) if not limit or zone is not None and zone <= limit]
    assert IntelligentLiteratureSystem._filter_by_user_criteria(None, records, criteria) == expected
    engine = LiteratureFilter.__new__(LiteratureFilter)
    for record in records:
        engine.get_journal_info_optimized = lambda *args: record['journal_info']
        assert engine._meets_criteria(record, criteria) == (record['pmid'] in expected)


def test_new_rui_combines_with_jcr_and_cas():
    criteria = SearchCriteria(query='test', cas_zones=[1, 2, 3], jcr_quartiles=['Q1', 'Q2', 'Q3'], new_rui_2026=[1, 2])
    records = [{'pmid': str(zone), 'journal_info': {'new_rui_zone': zone, 'cas_zone': 2, 'jcr_quartile': 'Q2'}} for zone in (1, 2, 3, 4, None)]
    assert IntelligentLiteratureSystem._filter_by_user_criteria(None, records, criteria) == ['1', '2']
