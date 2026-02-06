# -*- coding: utf-8 -*-
"""
Flow-level tests for SmartLiteratureSearchSystem orchestration.
These tests use fakes only (no network / no real model calls).
"""

from intent_analyzer import SearchCriteria
from smart_literature_search import SmartLiteratureSearchSystem


class DummyIntentAnalyzer:
    def __init__(
        self,
        criteria,
        pubmed_query,
        raise_on_analyze=False,
        raise_on_build=False,
    ):
        self.criteria = criteria
        self.pubmed_query = pubmed_query
        self.raise_on_analyze = raise_on_analyze
        self.raise_on_build = raise_on_build
        self.analyze_inputs = []
        self.built_criteria_queries = []
        self.printed_criteria = []

    def analyze_intent(self, user_input):
        self.analyze_inputs.append(user_input)
        if self.raise_on_analyze:
            raise RuntimeError("analyze failed")
        return self.criteria

    def print_analysis_result(self, criteria):
        self.printed_criteria.append(criteria)

    def build_pubmed_query(self, criteria):
        if self.raise_on_build:
            raise RuntimeError("build failed")
        self.built_criteria_queries.append(criteria.query)
        return self.pubmed_query


class DummyPubMedSearcher:
    def __init__(self, pmids, details_sequence):
        self.pmids = pmids
        self.details_sequence = list(details_sequence)
        self.search_calls = []
        self.detail_calls = []

    def search_articles(self, query, max_results, sort_by):
        self.search_calls.append(
            {"query": query, "max_results": max_results, "sort_by": sort_by}
        )
        return self.pmids

    def fetch_article_details(self, pmids):
        self.detail_calls.append(list(pmids))
        if not self.details_sequence:
            return []
        return self.details_sequence.pop(0)


class DummyLiteratureFilter:
    def __init__(self, filtered_articles):
        self.filtered_articles = filtered_articles
        self.filter_calls = []
        self.stats_calls = []
        self.analysis_calls = []
        self.export_calls = []

    def filter_articles(self, basic_articles, criteria):
        self.filter_calls.append((basic_articles, criteria))
        return self.filtered_articles

    def print_filter_statistics(self, basic_count, filtered_count, criteria):
        self.stats_calls.append((basic_count, filtered_count, criteria))

    def analyze_filtered_results(self, articles):
        self.analysis_calls.append(articles)

    def export_filtered_results(self, articles, output_format, output_path):
        self.export_calls.append((articles, output_format, output_path))
        return f"{output_path}.{output_format}"


def _build_system(intent_analyzer, pubmed_searcher, literature_filter):
    system = SmartLiteratureSearchSystem(interactive_ai=False)
    system.data_ready = True
    system.intent_analyzer = intent_analyzer
    system.pubmed_searcher = pubmed_searcher
    system.literature_filter = literature_filter
    return system


def test_search_literature_requires_initialized_system():
    system = SmartLiteratureSearchSystem(interactive_ai=False)
    assert system.search_literature("query") is None


def test_search_literature_returns_none_when_required_components_missing():
    system = SmartLiteratureSearchSystem(interactive_ai=False)
    system.data_ready = True
    # intent/pubmed/filter are missing
    assert system.search_literature("query") is None


def test_search_literature_happy_path_exports_json_and_csv():
    criteria = SearchCriteria(query="diabetes")
    analyzer = DummyIntentAnalyzer(criteria=criteria, pubmed_query="diabetes[Title]")
    searcher = DummyPubMedSearcher(
        pmids=["1", "2"],
        details_sequence=[
            [
                {
                    "pmid": "1",
                    "title": "T1",
                    "journal": "J1",
                    "issn": "1111-1111",
                    "eissn": "2222-2222",
                    "publication_date": "2024",
                    "doi": "10.1/1",
                    "authors": ["A"],
                    "authors_str": "A",
                    "keywords": ["k1"],
                    "keywords_str": "k1",
                    "abstract": "ABS1",
                },
                {
                    "pmid": "2",
                    "title": "T2",
                    "journal": "J2",
                    "issn": "3333-3333",
                    "eissn": "4444-4444",
                    "publication_date": "2023",
                    "doi": "10.1/2",
                    "authors": ["B"],
                    "authors_str": "B",
                    "keywords": ["k2"],
                    "keywords_str": "k2",
                    "abstract": "ABS2",
                },
            ],
            [{"pmid": "1", "abstract": "ABS1"}],
        ],
    )
    literature_filter = DummyLiteratureFilter(filtered_articles=[{"pmid": "1"}])
    system = _build_system(analyzer, searcher, literature_filter)

    result = system.search_literature("find diabetes", max_results=2)

    assert result is not None
    csv_path, json_path = result
    assert csv_path.endswith(".csv")
    assert json_path.endswith(".json")
    assert searcher.search_calls == [
        {"query": "diabetes[Title]", "max_results": 2, "sort_by": "relevance"}
    ]
    assert searcher.detail_calls == [["1", "2"], ["1"]]
    assert [call[1] for call in literature_filter.export_calls] == ["json", "csv"]
    assert literature_filter.export_calls[0][0][0]["abstract"] == "ABS1"


def test_search_literature_falls_back_when_intent_analysis_fails():
    analyzer = DummyIntentAnalyzer(
        criteria=SearchCriteria(query="unused"),
        pubmed_query="fallback_query",
        raise_on_analyze=True,
    )
    searcher = DummyPubMedSearcher(
        pmids=["9"],
        details_sequence=[[{"pmid": "9"}], [{"pmid": "9", "abstract": "A"}]],
    )
    literature_filter = DummyLiteratureFilter(filtered_articles=[{"pmid": "9"}])
    system = _build_system(analyzer, searcher, literature_filter)

    result = system.search_literature("fallback topic", max_results=1)

    assert result is not None
    # When analyze_intent fails, code falls back to SearchCriteria(query=user_input)
    assert analyzer.built_criteria_queries[-1] == "fallback topic"


def test_search_literature_falls_back_when_build_query_fails():
    criteria = SearchCriteria(query="criteria_query")
    analyzer = DummyIntentAnalyzer(
        criteria=criteria,
        pubmed_query="unused",
        raise_on_build=True,
    )
    searcher = DummyPubMedSearcher(
        pmids=["10"],
        details_sequence=[[{"pmid": "10"}], [{"pmid": "10", "abstract": "abs"}]],
    )
    literature_filter = DummyLiteratureFilter(filtered_articles=[{"pmid": "10"}])
    system = _build_system(analyzer, searcher, literature_filter)

    result = system.search_literature("user query", max_results=1)

    assert result is not None
    assert searcher.search_calls[0]["query"] == "criteria_query"


def test_search_and_generate_outline_uses_json_path_from_search_result():
    system = SmartLiteratureSearchSystem(interactive_ai=False)
    system.outline_generator = object()  # mark outline feature available

    calls = {}

    def fake_search(user_input, max_results):
        calls["search"] = (user_input, max_results)
        return ("out.csv", "out.json")

    def fake_generate(json_file_path, topic):
        calls["generate"] = (json_file_path, topic)
        return "outline.md"

    system.search_literature = fake_search
    system.generate_review_outline = fake_generate

    result = system.search_and_generate_outline("topic x", max_results=77)

    assert result == "outline.md"
    assert calls["search"] == ("topic x", 77)
    assert calls["generate"] == ("out.json", "topic x")


def test_search_and_generate_outline_returns_none_without_outline_generator():
    system = SmartLiteratureSearchSystem(interactive_ai=False)
    system.outline_generator = None
    system.search_literature = lambda user_input, max_results: ("out.csv", "out.json")

    assert system.search_and_generate_outline("topic y", max_results=10) is None
