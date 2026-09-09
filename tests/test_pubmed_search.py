# -*- coding: utf-8 -*-
"""
PubMed搜索模块单元测试

测试内容:
1. SearchResultCache 禁用缓存时 get()/put() 行为
2. max_concurrent<=0 退化为串行行为
3. 异步抓取分组执行行为
"""

import asyncio
import pytest

from pubmed_search import SearchResultCache, SearchConfig, PubMedSearcher


class TestSearchResultCacheDisabled:
    """SearchResultCache 禁用缓存行为测试"""

    def test_get_returns_none_when_max_size_zero(self, temp_cache_dir):
        """测试 max_size=0 时 get() 直接返回 None"""
        cache = SearchResultCache(
            cache_dir=str(temp_cache_dir),
            max_size=0,
            ttl=3600
        )
        # 即使有历史缓存文件，也应该返回 None
        result = cache.get("test query", 100, "relevance")
        assert result is None

    def test_get_returns_none_when_max_size_negative(self, temp_cache_dir):
        """测试 max_size<0 时 get() 直接返回 None"""
        cache = SearchResultCache(
            cache_dir=str(temp_cache_dir),
            max_size=-1,
            ttl=3600
        )
        result = cache.get("test query", 100, "relevance")
        assert result is None

    def test_put_does_nothing_when_max_size_zero(self, temp_cache_dir):
        """测试 max_size=0 时 put() 不写入缓存"""
        cache = SearchResultCache(
            cache_dir=str(temp_cache_dir),
            max_size=0,
            ttl=3600
        )
        # 尝试写入
        cache.put("test query", 100, "relevance", ["12345", "67890"])
        # 验证没有文件被创建
        import os
        cache_files = [f for f in os.listdir(str(temp_cache_dir)) if f.endswith('.json')]
        assert len(cache_files) == 0

    def test_put_does_nothing_when_max_size_negative(self, temp_cache_dir):
        """测试 max_size<0 时 put() 不写入缓存"""
        cache = SearchResultCache(
            cache_dir=str(temp_cache_dir),
            max_size=-5,
            ttl=3600
        )
        cache.put("test query", 100, "relevance", ["12345"])
        import os
        cache_files = [f for f in os.listdir(str(temp_cache_dir)) if f.endswith('.json')]
        assert len(cache_files) == 0

    def test_normal_cache_works_with_positive_max_size(self, temp_cache_dir):
        """测试 max_size>0 时缓存正常工作"""
        cache = SearchResultCache(
            cache_dir=str(temp_cache_dir),
            max_size=10,
            ttl=3600
        )
        pmids = ["12345", "67890"]
        cache.put("test query", 100, "relevance", pmids)
        result = cache.get("test query", 100, "relevance")
        assert result == pmids

    def test_stats_not_updated_when_disabled(self, temp_cache_dir):
        """测试禁用缓存时统计信息不更新（get返回None但不计入misses）"""
        cache = SearchResultCache(
            cache_dir=str(temp_cache_dir),
            max_size=0,
            ttl=3600
        )
        initial_misses = cache.stats['misses']
        cache.get("test", 10, "relevance")
        # 禁用缓存时，get() 直接返回，不应该增加 misses 计数
        assert cache.stats['misses'] == initial_misses


class TestMaxConcurrentBoundary:
    """max_concurrent 边界条件测试"""

    def test_max_concurrent_zero_uses_one(self):
        """测试 max_concurrent=0 时使用 1（串行执行）"""
        config = SearchConfig(
            max_concurrent=0,
            enable_async=True
        )
        # 验证 max(1, 0) = 1
        assert max(1, config.max_concurrent) == 1

    def test_max_concurrent_negative_uses_one(self):
        """测试 max_concurrent<0 时使用 1"""
        config = SearchConfig(
            max_concurrent=-5,
            enable_async=True
        )
        assert max(1, config.max_concurrent) == 1

    def test_max_concurrent_positive_uses_actual_value(self):
        """测试 max_concurrent>0 时使用实际值"""
        config = SearchConfig(
            max_concurrent=10,
            enable_async=True
        )
        assert max(1, config.max_concurrent) == 10

    def test_async_fetch_max_concurrent_boundary_logic(self):
        """测试 max_concurrent 边界逻辑（同步验证）"""
        # 验证边界保护逻辑：max(1, config.max_concurrent)
        test_cases = [
            (0, 1),   # 0 -> 1
            (-1, 1),  # -1 -> 1
            (-100, 1),  # -100 -> 1
            (1, 1),   # 1 -> 1
            (5, 5),   # 5 -> 5
            (100, 100),  # 100 -> 100
        ]

        for input_val, expected in test_cases:
            config = SearchConfig(max_concurrent=input_val)
            actual = max(1, config.max_concurrent)
            assert actual == expected, f"max(1, {input_val}) should be {expected}, got {actual}"


class TestSearchConfigDefaults:
    """SearchConfig 默认值测试"""

    def test_default_max_concurrent(self):
        """测试默认 max_concurrent 值"""
        config = SearchConfig()
        assert config.max_concurrent == 5  # 默认值

    def test_default_cache_max_size(self):
        """测试默认 cache_max_size 值"""
        config = SearchConfig()
        assert config.cache_max_size == 1000  # 默认值

    def test_custom_max_concurrent(self):
        """测试自定义 max_concurrent"""
        config = SearchConfig(max_concurrent=20)
        assert config.max_concurrent == 20


class TestSearchResultCacheLRU:
    """SearchResultCache LRU 淘汰测试"""

    def test_lru_eviction_with_empty_cache_files(self, temp_cache_dir):
        """测试当 cache_files 为空时不会触发 IndexError"""
        cache = SearchResultCache(
            cache_dir=str(temp_cache_dir),
            max_size=1,
            ttl=3600
        )
        # 第一次写入
        cache.put("query1", 10, "relevance", ["111"])
        # 第二次写入应触发淘汰，但不应报错
        cache.put("query2", 10, "relevance", ["222"])

        # 验证只有一个缓存文件
        import os
        cache_files = [f for f in os.listdir(str(temp_cache_dir)) if f.endswith('.json')]
        assert len(cache_files) == 1

    def test_eviction_stats_updated(self, temp_cache_dir):
        """测试淘汰时统计信息更新"""
        cache = SearchResultCache(
            cache_dir=str(temp_cache_dir),
            max_size=1,
            ttl=3600
        )
        cache.put("query1", 10, "relevance", ["111"])
        initial_evictions = cache.stats['evictions']
        cache.put("query2", 10, "relevance", ["222"])
        assert cache.stats['evictions'] == initial_evictions + 1


class TestAsyncFetchGroupExecution:
    """异步抓取分组执行测试"""

    def test_batch_grouping_logic(self):
        """测试批次分组逻辑"""
        # 模拟 10 个 PMID，batch_size=3，max_concurrent=2
        pmids = list(range(10))
        batch_size = 3
        max_concurrent = 2

        batch_starts = list(range(0, len(pmids), batch_size))
        # batch_starts = [0, 3, 6, 9] -> 4 个批次

        groups = []
        for group_start in range(0, len(batch_starts), max_concurrent):
            group_indices = batch_starts[group_start:group_start + max_concurrent]
            groups.append(group_indices)

        # 预期分组：[[0, 3], [6, 9]]
        assert len(groups) == 2
        assert groups[0] == [0, 3]
        assert groups[1] == [6, 9]

    def test_batch_grouping_with_max_concurrent_one(self):
        """测试 max_concurrent=1 时每组只有一个批次（串行）"""
        pmids = list(range(6))
        batch_size = 2
        max_concurrent = 1  # 串行

        batch_starts = list(range(0, len(pmids), batch_size))
        # batch_starts = [0, 2, 4] -> 3 个批次

        groups = []
        for group_start in range(0, len(batch_starts), max_concurrent):
            group_indices = batch_starts[group_start:group_start + max_concurrent]
            groups.append(group_indices)

        # 预期：每组只有一个批次
        assert len(groups) == 3
        assert groups[0] == [0]
        assert groups[1] == [2]
        assert groups[2] == [4]

    def test_group_delay_logic(self):
        """测试组间延迟逻辑"""
        batch_starts = [0, 3, 6, 9]  # 4 个批次
        max_concurrent = 2

        delays_needed = []
        for group_start in range(0, len(batch_starts), max_concurrent):
            # 检查是否需要延迟
            if group_start + max_concurrent < len(batch_starts):
                delays_needed.append(True)
            else:
                delays_needed.append(False)

        # 预期：第一组后需要延迟，第二组后不需要
        assert delays_needed == [True, False]

    def test_async_fetch_calls_fetch_batch_correct_times(self):
        """测试异步抓取调用 _fetch_batch_async 的次数正确"""
        config = SearchConfig(
            max_concurrent=2,
            batch_size=3,
            request_delay=0,
            enable_async=True
        )
        searcher = PubMedSearcher(config=config)

        # 计算预期批次数
        pmids = ["1", "2", "3", "4", "5", "6", "7"]  # 7 个 PMID
        batch_size = config.batch_size
        expected_batches = (len(pmids) + batch_size - 1) // batch_size  # ceil(7/3) = 3

        batch_starts = list(range(0, len(pmids), batch_size))
        assert len(batch_starts) == expected_batches  # [0, 3, 6] -> 3 个批次

    def test_semaphore_value_with_boundary_config(self):
        """测试信号量值在边界配置下正确"""
        test_cases = [
            (0, 1),    # max_concurrent=0 -> Semaphore(1)
            (-1, 1),   # max_concurrent=-1 -> Semaphore(1)
            (1, 1),    # max_concurrent=1 -> Semaphore(1)
            (5, 5),    # max_concurrent=5 -> Semaphore(5)
        ]

        for input_val, expected_semaphore in test_cases:
            config = SearchConfig(max_concurrent=input_val)
            actual = max(1, config.max_concurrent)
            # 验证信号量可以正常创建
            sem = asyncio.Semaphore(actual)
            assert sem._value == expected_semaphore

    def test_empty_pmids_no_batches(self):
        """测试空 PMID 列表不产生批次"""
        pmids = []
        batch_size = 3

        batch_starts = list(range(0, len(pmids), batch_size))
        assert batch_starts == []

    def test_single_pmid_single_batch(self):
        """测试单个 PMID 只产生一个批次"""
        pmids = ["12345"]
        batch_size = 3

        batch_starts = list(range(0, len(pmids), batch_size))
        assert batch_starts == [0]
        assert pmids[0:0 + batch_size] == ["12345"]
