# -*- coding: utf-8 -*-
"""
通用缓存模块

提供统一的缓存抽象，支持：
- 内存缓存（LRU）
- 文件持久化缓存
- TTL过期机制
- 线程安全

使用方法:
    from cache import MemoryCache, FileCache

    # 内存缓存
    cache = MemoryCache(maxsize=1000, ttl=3600)
    cache.set("key", value)
    value = cache.get("key")

    # 文件缓存
    file_cache = FileCache(cache_dir="./cache", ttl=86400)
    file_cache.set("search_results", results)
"""

import hashlib
import json
import pickle
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, Generic, Optional, TypeVar

T = TypeVar('T')


@dataclass
class CacheEntry(Generic[T]):
    """缓存条目"""
    value: T
    created_at: float
    ttl: Optional[float] = None

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl


class CacheBase(ABC, Generic[T]):
    """缓存基类接口"""

    @abstractmethod
    def get(self, key: str, default: T = None) -> Optional[T]:
        """获取缓存值"""
        pass

    @abstractmethod
    def set(self, key: str, value: T, ttl: Optional[float] = None) -> None:
        """设置缓存值"""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除缓存项"""
        pass

    @abstractmethod
    def clear(self) -> None:
        """清空缓存"""
        pass

    @abstractmethod
    def has(self, key: str) -> bool:
        """检查key是否存在且有效"""
        pass


class MemoryCache(CacheBase[T]):
    """
    线程安全的内存LRU缓存

    Args:
        maxsize: 最大缓存条目数
        ttl: 默认过期时间（秒），None表示永不过期

    Example:
        cache = MemoryCache(maxsize=100, ttl=300)
        cache.set("key", "value")
        print(cache.get("key"))  # "value"
    """

    def __init__(self, maxsize: int = 1000, ttl: Optional[float] = None):
        self.maxsize = maxsize
        self.default_ttl = ttl
        self._cache: Dict[str, CacheEntry[T]] = {}
        self._access_order: list = []
        self._lock = threading.RLock()

    def get(self, key: str, default: T = None) -> Optional[T]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return default
            if entry.is_expired():
                self._remove(key)
                return default
            # 更新访问顺序
            self._update_access(key)
            return entry.value

    def set(self, key: str, value: T, ttl: Optional[float] = None) -> None:
        with self._lock:
            effective_ttl = ttl if ttl is not None else self.default_ttl
            entry = CacheEntry(value=value, created_at=time.time(), ttl=effective_ttl)
            self._cache[key] = entry
            self._update_access(key)
            self._evict_if_needed()

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._remove(key)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._access_order.clear()

    def has(self, key: str) -> bool:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                self._remove(key)
                return False
            return True

    def _update_access(self, key: str) -> None:
        """更新访问顺序（LRU）"""
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    def _remove(self, key: str) -> bool:
        """移除缓存项"""
        if key in self._cache:
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            return True
        return False

    def _evict_if_needed(self) -> None:
        """LRU淘汰策略"""
        while len(self._cache) > self.maxsize:
            if self._access_order:
                oldest_key = self._access_order.pop(0)
                self._cache.pop(oldest_key, None)

    def size(self) -> int:
        """返回当前缓存大小"""
        return len(self._cache)


class FileCache(CacheBase[T]):
    """
    文件持久化缓存

    Args:
        cache_dir: 缓存目录路径
        ttl: 默认过期时间（秒）
        serializer: 序列化方式 ('json' 或 'pickle')

    Example:
        cache = FileCache("./cache", ttl=86400)
        cache.set("results", data)
        data = cache.get("results")
    """

    def __init__(
        self,
        cache_dir: str,
        ttl: Optional[float] = None,
        serializer: str = "pickle"
    ):
        self.cache_dir = Path(cache_dir)
        self.default_ttl = ttl
        self.serializer = serializer
        self._lock = threading.RLock()

        # 确保缓存目录存在
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key: str) -> Path:
        """生成缓存文件路径"""
        # 使用MD5哈希避免非法文件名
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"

    def _serialize(self, data: Any) -> bytes:
        """序列化数据"""
        if self.serializer == "json":
            return json.dumps(data, ensure_ascii=False).encode('utf-8')
        return pickle.dumps(data)

    def _deserialize(self, data: bytes) -> Any:
        """反序列化数据"""
        if self.serializer == "json":
            return json.loads(data.decode('utf-8'))
        return pickle.loads(data)

    def get(self, key: str, default: T = None) -> Optional[T]:
        with self._lock:
            cache_path = self._get_cache_path(key)
            meta_path = cache_path.with_suffix('.meta')

            if not cache_path.exists():
                return default

            try:
                # 检查元数据
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text())
                    ttl = meta.get('ttl')
                    created_at = meta.get('created_at', 0)
                    if ttl is not None and time.time() - created_at > ttl:
                        self.delete(key)
                        return default

                # 读取缓存数据
                data = cache_path.read_bytes()
                return self._deserialize(data)
            except (json.JSONDecodeError, pickle.UnpicklingError, OSError):
                return default

    def set(self, key: str, value: T, ttl: Optional[float] = None) -> None:
        with self._lock:
            cache_path = self._get_cache_path(key)
            meta_path = cache_path.with_suffix('.meta')
            effective_ttl = ttl if ttl is not None else self.default_ttl

            try:
                # 写入缓存数据
                data = self._serialize(value)
                cache_path.write_bytes(data)

                # 写入元数据
                meta = {
                    'key': key,
                    'created_at': time.time(),
                    'ttl': effective_ttl
                }
                meta_path.write_text(json.dumps(meta))
            except OSError:
                pass  # 静默失败，缓存不可用不应影响主流程

    def delete(self, key: str) -> bool:
        with self._lock:
            cache_path = self._get_cache_path(key)
            meta_path = cache_path.with_suffix('.meta')
            deleted = False

            try:
                if cache_path.exists():
                    cache_path.unlink()
                    deleted = True
                if meta_path.exists():
                    meta_path.unlink()
            except OSError:
                pass

            return deleted

    def clear(self) -> None:
        with self._lock:
            try:
                for file in self.cache_dir.glob("*.cache"):
                    file.unlink()
                for file in self.cache_dir.glob("*.meta"):
                    file.unlink()
            except OSError:
                pass

    def has(self, key: str) -> bool:
        return self.get(key) is not None


def cached(
    cache: CacheBase,
    key_builder: Optional[Callable[..., str]] = None,
    ttl: Optional[float] = None
) -> Callable:
    """
    缓存装饰器

    Args:
        cache: 缓存实例
        key_builder: 自定义key生成函数
        ttl: 过期时间

    Example:
        cache = MemoryCache(maxsize=100)

        @cached(cache, ttl=300)
        def expensive_computation(x, y):
            return x + y
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            # 生成缓存key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{args}:{kwargs}"

            # 尝试从缓存获取
            result = cache.get(cache_key)
            if result is not None:
                return result

            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl=ttl)
            return result

        return wrapper
    return decorator


# 全局缓存实例（可选使用）
_global_memory_cache: Optional[MemoryCache] = None
_global_file_cache: Optional[FileCache] = None


def get_memory_cache(maxsize: int = 1000, ttl: Optional[float] = None) -> MemoryCache:
    """获取全局内存缓存实例"""
    global _global_memory_cache
    if _global_memory_cache is None:
        _global_memory_cache = MemoryCache(maxsize=maxsize, ttl=ttl)
    return _global_memory_cache


def get_file_cache(
    cache_dir: str = None,
    ttl: Optional[float] = None
) -> FileCache:
    """获取全局文件缓存实例"""
    global _global_file_cache
    if _global_file_cache is None:
        if cache_dir is None:
            cache_dir = str(Path(__file__).parent.parent / "cache")
        _global_file_cache = FileCache(cache_dir=cache_dir, ttl=ttl)
    return _global_file_cache


# 导出接口
__all__ = [
    'CacheBase',
    'CacheEntry',
    'MemoryCache',
    'FileCache',
    'cached',
    'get_memory_cache',
    'get_file_cache',
]
