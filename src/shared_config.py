#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
共享配置管理器模块
统一管理AI模型配置缓存和系统配置，避免代码重复
支持从 system_config.yaml 加载配置
"""

import json
import os
import time
import threading
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


# ============================================================================
# 系统配置类（支持从YAML文件加载）
# ============================================================================

class SystemConfig:
    """
    系统配置类
    优先从 system_config.yaml 加载，否则使用默认值
    """

    _instance = None
    _lock = threading.Lock()
    _config_data: Dict[str, Any] = {}

    # 默认值（当配置文件不存在时使用）
    _defaults = {
        # 缓存配置
        'CACHE_SIZE': 500,
        'CACHE_TTL': 3600,
        'MODEL_CACHE_EXPIRY_DAYS': 7,

        # 批处理配置
        'BATCH_SIZE': 50,
        'MAX_WORKERS': 4,
        'BATCH_DELAY': 5.0,
        'CHUNK_SIZE': 200,

        # 重试配置
        'MAX_RETRIES': 3,
        'RETRY_DELAY_BASE': 2,
        'RETRY_DELAY_MAX': 10,

        # 超时配置
        'REQUEST_TIMEOUT': 30,

        # 内存限制
        'MEMORY_LIMIT_MB': 300,

        # 文件路径
        'MODEL_CACHE_FILE': 'ai_model_cache.json',

        # AI模型默认参数
        'DEFAULT_TEMPERATURE': 0.1,
        'DEFAULT_STREAM': True,
        'DEFAULT_MAX_TOKENS': None,
        'PREFERRED_MODEL': 'gemini-3-pro',
    }

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """从配置文件加载配置"""
        config_file = self._find_config_file()

        if config_file and YAML_AVAILABLE:
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self._config_data = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"[WARN] 加载配置文件失败: {e}，使用默认配置")
                self._config_data = {}
        else:
            self._config_data = {}

    def _find_config_file(self) -> Optional[str]:
        """查找配置文件"""
        # 从当前文件位置向上查找
        current_dir = Path(__file__).parent
        project_root = current_dir.parent

        possible_paths = [
            project_root / 'system_config.yaml',
            current_dir / 'system_config.yaml',
            Path.cwd() / 'system_config.yaml',
        ]

        for path in possible_paths:
            if path.exists():
                return str(path)

        return None

    def _get_nested(self, *keys, default=None):
        """获取嵌套配置值"""
        value = self._config_data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value

    # 配置属性访问器
    @property
    def CACHE_SIZE(self) -> int:
        return self._get_nested('cache', 'size', default=self._defaults['CACHE_SIZE'])

    @property
    def CACHE_TTL(self) -> int:
        return self._get_nested('cache', 'ttl', default=self._defaults['CACHE_TTL'])

    @property
    def MODEL_CACHE_EXPIRY_DAYS(self) -> int:
        return self._get_nested('cache', 'model_cache_expiry_days',
                               default=self._defaults['MODEL_CACHE_EXPIRY_DAYS'])

    @property
    def BATCH_SIZE(self) -> int:
        return self._get_nested('batch', 'size', default=self._defaults['BATCH_SIZE'])

    @property
    def MAX_WORKERS(self) -> int:
        return self._get_nested('batch', 'max_workers', default=self._defaults['MAX_WORKERS'])

    @property
    def BATCH_DELAY(self) -> float:
        return self._get_nested('batch', 'delay', default=self._defaults['BATCH_DELAY'])

    @property
    def CHUNK_SIZE(self) -> int:
        return self._get_nested('batch', 'chunk_size', default=self._defaults['CHUNK_SIZE'])

    @property
    def MAX_RETRIES(self) -> int:
        return self._get_nested('retry', 'max_attempts', default=self._defaults['MAX_RETRIES'])

    @property
    def RETRY_DELAY_BASE(self) -> int:
        return self._get_nested('retry', 'delay_base', default=self._defaults['RETRY_DELAY_BASE'])

    @property
    def RETRY_DELAY_MAX(self) -> int:
        return self._get_nested('retry', 'delay_max', default=self._defaults['RETRY_DELAY_MAX'])

    @property
    def REQUEST_TIMEOUT(self) -> int:
        return self._get_nested('timeout', 'request', default=self._defaults['REQUEST_TIMEOUT'])

    @property
    def MEMORY_LIMIT_MB(self) -> int:
        return self._get_nested('memory', 'limit_mb', default=self._defaults['MEMORY_LIMIT_MB'])

    @property
    def MODEL_CACHE_FILE(self) -> str:
        return self._defaults['MODEL_CACHE_FILE']

    @property
    def DEFAULT_TEMPERATURE(self) -> float:
        return self._get_nested('ai', 'default_temperature',
                               default=self._defaults['DEFAULT_TEMPERATURE'])

    @property
    def DEFAULT_STREAM(self) -> bool:
        return self._get_nested('ai', 'default_stream', default=self._defaults['DEFAULT_STREAM'])

    @property
    def DEFAULT_MAX_TOKENS(self) -> Optional[int]:
        return self._get_nested('ai', 'default_max_tokens',
                               default=self._defaults['DEFAULT_MAX_TOKENS'])

    @property
    def PREFERRED_MODEL(self) -> str:
        return self._get_nested('ai', 'preferred_model', default=self._defaults['PREFERRED_MODEL'])

    # ==================== 导出配置 ====================
    @property
    def REVIEW_FORMAT(self) -> str:
        """综述输出格式: md, docx, both"""
        return self._get_nested('export', 'review_format', default='both')

    @property
    def DOCX_STYLE(self) -> str:
        """DOCX导出样式: academic, simple"""
        return self._get_nested('export', 'docx_style', default='academic')

    @property
    def MEDICAL_TEMPLATE(self) -> str:
        """医学论文模板路径"""
        return self._get_nested('export', 'medical_template', default='tools/medical_template.docx')


# 全局配置实例
system_config = SystemConfig()


@dataclass
class AIModelConfig:
    """AI模型配置数据类"""
    config_name: str
    model_id: str
    parameters: Dict[str, Any]

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'AIModelConfig':
        # 过滤掉时间戳等额外字段
        valid_fields = {'config_name', 'model_id', 'parameters'}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered_data)


class SharedConfigManager:
    """
    共享配置管理器 - 单例模式
    统一管理AI模型配置的加载、缓存和验证
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._cached_config: Optional[AIModelConfig] = None
        self._cache_loaded_at: float = 0
        self._lock = threading.Lock()
        self._initialized = True

    def load_cached_model_config(self, validate: bool = False) -> Optional[AIModelConfig]:
        """
        加载缓存的AI模型配置

        Args:
            validate: 是否验证缓存有效性

        Returns:
            AIModelConfig 或 None
        """
        cache_file = system_config.MODEL_CACHE_FILE

        if not os.path.exists(cache_file):
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 检查缓存时间
            cached_at = data.get('cached_at', 0)
            cache_age_days = (time.time() - cached_at) / (24 * 3600)

            if cache_age_days > system_config.MODEL_CACHE_EXPIRY_DAYS:
                print(f"[INFO] 模型配置缓存已过期 ({cache_age_days:.1f}天)")
                self._remove_cache_file(cache_file)
                return None

            config = AIModelConfig.from_dict(data)

            print(f"[OK] 加载缓存模型配置: {config.model_id} (缓存时间: {cache_age_days:.1f}天)")
            return config

        except Exception as e:
            print(f"[WARN] 加载模型配置缓存失败: {e}")
            self._remove_cache_file(cache_file)
            return None

    def save_model_config(self, config: AIModelConfig) -> bool:
        """
        保存AI模型配置到缓存

        Args:
            config: AI模型配置

        Returns:
            是否保存成功
        """
        try:
            # 确保stream参数为True
            config.parameters['stream'] = True

            cache_data = config.to_dict()
            cache_data['cached_at'] = time.time()

            with open(system_config.MODEL_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            print(f"[SAVE] 模型配置已缓存: {config.model_id}")
            return True

        except Exception as e:
            print(f"[WARN] 保存模型配置缓存失败: {e}")
            return False

    def clear_cache(self) -> bool:
        """清除模型配置缓存"""
        return self._remove_cache_file(system_config.MODEL_CACHE_FILE)

    def _remove_cache_file(self, filepath: str) -> bool:
        """安全删除缓存文件"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
        except Exception:
            pass
        return False

    def get_default_model_parameters(self, stream: bool = True) -> Dict[str, Any]:
        """
        获取默认模型参数

        Args:
            stream: 是否启用流式输出

        Returns:
            默认参数字典
        """
        return {
            "temperature": system_config.DEFAULT_TEMPERATURE,
            "stream": stream,
            "max_tokens": system_config.DEFAULT_MAX_TOKENS
        }

    @staticmethod
    def get_retry_delay(attempt: int) -> float:
        """
        计算重试延迟（指数退避）

        Args:
            attempt: 当前尝试次数（从0开始）

        Returns:
            延迟时间（秒）
        """
        delay = min(
            system_config.RETRY_DELAY_BASE ** attempt,
            system_config.RETRY_DELAY_MAX
        )
        return delay


# 全局单例实例
shared_config = SharedConfigManager()


def get_shared_config() -> SharedConfigManager:
    """获取共享配置管理器实例"""
    return shared_config
