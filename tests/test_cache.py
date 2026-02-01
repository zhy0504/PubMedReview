# -*- coding: utf-8 -*-
"""
缓存模块单元测试
"""

import time
import pytest

from cache import MemoryCache, FileCache, CacheEntry, cached


class TestCacheEntry:
    """CacheEntry测试"""

    def test_entry_not_expired(self):
        """测试未过期的缓存条目"""
        entry = CacheEntry(value="test", created_at=time.time(), ttl=3600)
        assert not entry.is_expired()

    def test_entry_expired(self):
        """测试过期的缓存条目"""
        entry = CacheEntry(value="test", created_at=time.time() - 100, ttl=10)
        assert entry.is_expired()

    def test_entry_no_ttl(self):
        """测试无TTL的缓存条目永不过期"""
        entry = CacheEntry(value="test", created_at=time.time() - 10000, ttl=None)
        assert not entry.is_expired()


class TestMemoryCache:
    """MemoryCache测试"""

    def test_set_and_get(self):
        """测试基本的设置和获取"""
        cache = MemoryCache()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_nonexistent_returns_default(self):
        """测试获取不存在的key返回默认值"""
        cache = MemoryCache()
        assert cache.get("nonexistent") is None
        assert cache.get("nonexistent", "default") == "default"

    def test_delete(self):
        """测试删除缓存项"""
        cache = MemoryCache()
        cache.set("key1", "value1")
        assert cache.delete("key1")
        assert cache.get("key1") is None

    def test_has(self):
        """测试has方法"""
        cache = MemoryCache()
        cache.set("key1", "value1")
        assert cache.has("key1")
        assert not cache.has("key2")

    def test_clear(self):
        """测试清空缓存"""
        cache = MemoryCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.size() == 0

    def test_lru_eviction(self):
        """测试LRU淘汰策略"""
        cache = MemoryCache(maxsize=3)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        # 访问key1使其成为最近使用
        cache.get("key1")
        # 添加新项，应该淘汰key2
        cache.set("key4", "value4")
        assert cache.has("key1")
        assert not cache.has("key2")
        assert cache.has("key3")
        assert cache.has("key4")

    def test_ttl_expiration(self):
        """测试TTL过期"""
        cache = MemoryCache(ttl=0.1)  # 100ms TTL
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        time.sleep(0.15)
        assert cache.get("key1") is None


class TestFileCache:
    """FileCache测试"""

    def test_set_and_get(self, temp_cache_dir):
        """测试基本的设置和获取"""
        cache = FileCache(str(temp_cache_dir))
        cache.set("key1", {"data": "value1"})
        result = cache.get("key1")
        assert result == {"data": "value1"}

    def test_get_nonexistent(self, temp_cache_dir):
        """测试获取不存在的key"""
        cache = FileCache(str(temp_cache_dir))
        assert cache.get("nonexistent") is None

    def test_delete(self, temp_cache_dir):
        """测试删除"""
        cache = FileCache(str(temp_cache_dir))
        cache.set("key1", "value1")
        assert cache.delete("key1")
        assert cache.get("key1") is None

    def test_clear(self, temp_cache_dir):
        """测试清空"""
        cache = FileCache(str(temp_cache_dir))
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_json_serializer(self, temp_cache_dir):
        """测试JSON序列化"""
        cache = FileCache(str(temp_cache_dir), serializer="json")
        data = {"name": "测试", "value": 123}
        cache.set("key1", data)
        assert cache.get("key1") == data


class TestCachedDecorator:
    """cached装饰器测试"""

    def test_caches_result(self):
        """测试结果缓存"""
        cache = MemoryCache()
        call_count = 0

        @cached(cache)
        def expensive_func(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = expensive_func(5)
        result2 = expensive_func(5)

        assert result1 == 10
        assert result2 == 10
        assert call_count == 1  # 只调用了一次

    def test_different_args_different_cache(self):
        """测试不同参数使用不同缓存"""
        cache = MemoryCache()

        @cached(cache)
        def add(a, b):
            return a + b

        assert add(1, 2) == 3
        assert add(2, 3) == 5
        assert cache.size() == 2
