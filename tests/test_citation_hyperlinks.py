from types import SimpleNamespace

import pytest

from medical_review_generator import MedicalReviewGenerator


def render(text):
    literature = [SimpleNamespace(url=f'https://example.org/{number}') for number in range(1, 20)]
    return MedicalReviewGenerator._add_citation_hyperlinks(None, text, literature)


@pytest.mark.parametrize('text', ['[17, 18, 19]', '[17,18,19]', '[17 - 19]', '[17-19]'])
def test_group_citations_have_individual_links(text):
    expected = ''.join(f'[[{number}]](https://example.org/{number})' for number in (17, 18, 19))
    assert render(text) == expected
    assert render(expected) == expected


@pytest.mark.parametrize('text', ['[[1]](https://example.org/1)', '[1](https://example.org/1)', r'[\[1\]](https://example.org/1)', '[1][reference]'])
def test_existing_links_unchanged(text):
    assert render(text) == text


def test_missing_url_and_invalid_range_preserved():
    assert render('[20]') == '[20]'
    assert render('[3-1]') == '[3-1]'
    assert render('[1-999999]') == '[1-999999]'
    assert render('[1]') == '[[1]](https://example.org/1)'
