from types import SimpleNamespace

import pytest

from medical_review_generator import MedicalReviewGenerator


def render(text):
    literature = [SimpleNamespace(url=f'https://example.org/{number}') for number in range(1, 20)]
    return MedicalReviewGenerator._add_citation_hyperlinks(None, text, literature)


@pytest.mark.parametrize('text', ['[17, 18, 19]', '[17,18,19]', '[17 - 19]', '[17-19]'])
def test_group_citations_have_individual_links(text):
    expected = ', '.join(rf'[\[{number}\]](https://example.org/{number})' for number in (17, 18, 19)) if ',' in text else '–'.join(rf'[\[{number}\]](https://example.org/{number})' for number in (17, 18, 19))
    assert render(text) == expected
    assert render(expected) == expected


@pytest.mark.parametrize('text', ['[[1]](https://example.org/1)', '[1](https://example.org/1)', r'[\[1\]](https://example.org/1)'])
def test_existing_numeric_links_are_normalized(text):
    assert render(text) == r'[\[1\]](https://example.org/1)'


def test_non_numeric_reference_links_are_unchanged():
    assert render('[1][reference]') == '[1][reference]'


def test_adjacent_citations_are_both_linked():
    assert render('[1][2]') == r'[\[1\]](https://example.org/1)[\[2\]](https://example.org/2)'


def test_missing_url_and_invalid_range_preserved():
    assert render('[20]') == '[20]'
    assert render('[3-1]') == '[3-1]'
    assert render('[1-999999]') == '[1-999999]'
    assert render('[1]') == r'[\[1\]](https://example.org/1)'


def test_references_hide_url_in_visible_text():
    references = MedicalReviewGenerator.generate_references(None, _literature_items())

    assert 'Available from' not in references
    assert r'[\[1\]](https://pubmed.ncbi.nlm.nih.gov/1)' in references


def _literature_items():
    from medical_review_generator import Literature

    return [
        Literature(
            id=1,
            title='第一篇',
            authors='作者甲',
            journal='期刊甲',
            year=2024,
            doi='',
            abstract='',
            url='https://pubmed.ncbi.nlm.nih.gov/1',
        ),
        Literature(
            id=2,
            title='第二篇',
            authors='作者乙',
            journal='期刊乙',
            year=2023,
            doi='',
            abstract='',
            url='https://pubmed.ncbi.nlm.nih.gov/2',
        ),
    ]


def test_reorder_without_citations_keeps_article_and_all_references():
    literature = _literature_items()
    content = '# 综述\n\n正文没有引用。\n\n## 参考文献\n\n1. 第一篇'

    article, reordered = MedicalReviewGenerator._reorder_citations_and_references(
        None, content, literature
    )

    assert article == content
    assert reordered == literature


def test_reorder_with_invalid_citations_keeps_article_and_all_references():
    literature = _literature_items()
    content = '# 综述\n\n正文引用了[99]。'

    article, reordered = MedicalReviewGenerator._reorder_citations_and_references(
        None, content, literature
    )

    assert article == content
    assert reordered == literature


def test_reorder_expands_range_citations_before_linking():
    literature = _literature_items()
    generator = MedicalReviewGenerator.__new__(MedicalReviewGenerator)
    content = '# 综述\n\n正文引用了[1-2]。'

    article, reordered = generator._reorder_citations_and_references(content, literature)

    assert '正文引用了[1, 2]。' in article
    assert reordered == literature
