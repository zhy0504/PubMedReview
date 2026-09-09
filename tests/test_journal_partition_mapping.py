from types import SimpleNamespace

import pandas as pd

from literature_filter import LiteratureFilter, FilterConfig
from intelligent_literature_system import IntelligentLiteratureSystem


def test_real_csv_column_mapping_merges_print_and_electronic_identifiers():
    engine = LiteratureFilter.__new__(LiteratureFilter)
    engine.config = FilterConfig()
    engine.config.enable_parallel = False
    engine.zky_data = engine._clean_journal_data(pd.DataFrame([{
        'Journal': 'Example Journal', 'ISSN/EISSN': '1234-567X/2345-6789',
        '大类分区': '3 [125/300]',
    }]))
    engine.jcr_data = engine._clean_journal_data(pd.DataFrame([{
        'Journal': 'Example Journal', 'ISSN': '1234-567X', 'EISSN': '2345-6789',
        'IF(2025)': '2.5', 'IF Quartile(2025)_1': 'Q3',
    }]))
    mapping = engine._build_journal_mapping_optimized()
    for identifier in ('1234567X', '23456789'):
        assert mapping[identifier] == {'cas_zone': 3, 'impact_factor': 2.5, 'jcr_quartile': 'Q3'}
    assert engine._build_journal_name_mapping()['EXAMPLE JOURNAL']['cas_zone'] == 3
    criteria = SimpleNamespace(min_if=None, cas_zones=[1, 2, 3], jcr_quartiles=['Q1', 'Q2', 'Q3'])
    articles = [{'pmid': '123', 'journal_info': mapping['23456789']}]
    assert IntelligentLiteratureSystem._filter_by_user_criteria(None, articles, criteria) == ['123']
    criteria.cas_zones = [1, 2]
    assert IntelligentLiteratureSystem._filter_by_user_criteria(None, articles, criteria) == []
