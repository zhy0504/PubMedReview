# -*- coding: utf-8 -*-
"""
Helper-level tests for intelligent_literature_system.py
Focus on deterministic utilities and pure orchestration logic.
"""

from pathlib import Path
from types import SimpleNamespace

from intelligent_literature_system import (
    SystemCleaner,
    PerformanceMonitor,
    StateManager,
    IntelligentCache,
    ProgressTracker,
    SimpleOutlineGenerator,
    IntelligentLiteratureSystem,
)


def test_system_cleaner_cleanup_on_startup_removes_expected_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    removable = [
        "system_state.json",
        "temp_literature_1.json",
        "temp_outline_1.md",
        "temp_any.json",
        "temp_any.md",
        "abc.cache",
    ]
    for name in removable:
        Path(name).write_text("x", encoding="utf-8")
    Path("keep.txt").write_text("x", encoding="utf-8")

    cleaned = SystemCleaner.cleanup_on_startup(verbose=False)

    assert len(cleaned) == len(removable)
    for name in removable:
        assert not Path(name).exists()
    assert Path("keep.txt").exists()


def test_system_cleaner_manual_cleanup_removes_cache_and_ai_model_cache(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    Path("system_state.json").write_text("x", encoding="utf-8")
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "one.cache").write_text("x", encoding="utf-8")
    Path("ai_model_cache.json").write_text("x", encoding="utf-8")

    cleaned = SystemCleaner.manual_cleanup(verbose=False)

    assert cleaned
    assert not Path("system_state.json").exists()
    assert not (cache_dir / "one.cache").exists()
    assert not Path("ai_model_cache.json").exists()


def test_performance_monitor_reports_categories_and_bottlenecks():
    monitor = PerformanceMonitor()
    monitor.metrics = {
        "完整工作流程": 10.0,
        "serial_op": 4.0,
        "parallel_fast": 2.0,
        "parallel_slow": 6.0,
    }
    monitor.operation_counts = {
        "完整工作流程": 1,
        "serial_op": 1,
        "parallel_fast": 1,
        "parallel_slow": 1,
    }
    monitor.parallel_operations = {"parallel_fast", "parallel_slow"}

    report = monitor.get_performance_report()

    assert report["actual_total_time"] == 10.0
    assert report["serial_total_time"] == 4.0
    assert report["parallel_total_time"] == 6.0
    assert "serial_op" in report["operation_categories"]["serial"]
    assert "parallel_slow" in report["operation_categories"]["parallel"]
    assert "完整工作流程" not in report["bottlenecks"]
    assert report["bottlenecks"][0] == "parallel_slow"


def test_state_manager_save_load_resume_and_clear(tmp_path):
    state_file = tmp_path / "state.json"
    manager = StateManager(state_file=str(state_file))

    manager.save_state({"processing": True, "step": 1})
    loaded = manager.load_state()

    assert loaded["processing"] is True
    assert loaded["step"] == 1
    assert "timestamp" in loaded
    assert manager.can_resume() is True

    manager.clear_state()
    assert not state_file.exists()
    assert manager.can_resume() is False


def test_state_manager_load_invalid_json_returns_empty(tmp_path):
    state_file = tmp_path / "state_invalid.json"
    state_file.write_text("{invalid json", encoding="utf-8")
    manager = StateManager(state_file=str(state_file))

    assert manager.load_state() == {}


def test_intelligent_cache_search_hit_and_expiry(tmp_path):
    cache = IntelligentCache(cache_dir=str(tmp_path / "cache"))
    cache.cache_search_result("q", 5, ["1", "2"])
    hit = cache.get_cached_search("q", 5)
    assert hit is not None
    assert hit["results"] == ["1", "2"]
    assert hit["count"] == 2

    cache.cache_ttl = 0
    expired = cache.get_cached_search("q", 5)
    assert expired is None
    assert "q_5" not in cache.search_cache


def test_intelligent_cache_ai_response_supports_dict_and_legacy_value(tmp_path):
    cache = IntelligentCache(cache_dir=str(tmp_path / "cache"))
    cache.cache_ai_response("h1", "resp1")
    assert cache.get_cached_ai_response("h1") == "resp1"

    cache.ai_response_cache["legacy"] = "legacy_resp"
    assert cache.get_cached_ai_response("legacy") == "legacy_resp"


def test_intelligent_cache_clear_cache_removes_memory_and_cache_files(tmp_path):
    cache_dir = tmp_path / "cache"
    cache = IntelligentCache(cache_dir=str(cache_dir))
    cache.cache_search_result("q", 1, ["x"])
    cache.cache_ai_response("h", "r")
    (cache_dir / "a.cache").write_text("x", encoding="utf-8")

    cache.clear_cache()

    assert cache.search_cache == {}
    assert cache.ai_response_cache == {}
    assert not (cache_dir / "a.cache").exists()


def test_progress_tracker_updates_and_records_step_time():
    tracker = ProgressTracker(total_steps=2, description="test")
    tracker.update("step1")
    assert tracker.current_step == 1
    assert tracker.get_step_time("step1") > 0

    tracker.update_progress_only("step1", "running", 50)
    assert tracker.current_step == 1

    bar = tracker._generate_progress_bar(50, width=10)
    assert bar == "[#####.....]"


def test_simple_outline_generator_contains_topic_and_count():
    generator = SimpleOutlineGenerator()
    outline = generator.generate_outline_from_data(
        literature_data=[{"pmid": "1"}, {"pmid": "2"}],
        research_topic="糖尿病",
    )
    assert "糖尿病" in outline
    assert "2篇文献" in outline


def test_filter_by_user_criteria_applies_if_zone_and_quartile():
    system = object.__new__(IntelligentLiteratureSystem)
    criteria = SimpleNamespace(min_if=5.0, cas_zones=[1], jcr_quartiles=["Q1"])
    enriched = [
        {
            "pmid": "A",
            "journal_info": {"impact_factor": 6.0, "cas_zone": 1, "jcr_quartile": "Q1"},
        },
        {
            "pmid": "B",
            "journal_info": {"impact_factor": 4.0, "cas_zone": 1, "jcr_quartile": "Q1"},
        },
        {
            "pmid": "C",
            "journal_info": {"impact_factor": 8.0, "cas_zone": 2, "jcr_quartile": "Q1"},
        },
        {
            "pmid": "D",
            "journal_info": {"impact_factor": 8.0, "cas_zone": 1, "jcr_quartile": "Q2"},
        },
        {"pmid": "E", "journal_info": {}},
    ]

    result = system._filter_by_user_criteria(enriched, criteria)
    assert result == ["A"]


def test_extract_core_research_topic_removes_filter_words_and_keeps_core():
    system = object.__new__(IntelligentLiteratureSystem)
    result = system._extract_core_research_topic("糖尿病治疗近5年高影响因子Q1期刊研究")

    assert "糖尿病" in result
    assert "Q1" not in result
    assert "期刊" not in result


def test_extract_core_research_topic_falls_back_to_default_when_meaningless():
    system = object.__new__(IntelligentLiteratureSystem)
    result = system._extract_core_research_topic("期刊")
    assert result == "医学研究"
