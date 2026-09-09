# -*- coding: utf-8 -*-
"""
测试配置和共享fixture

使用方法:
    pytest tests/ -v
    pytest tests/test_cache.py -v
"""

import sys
from pathlib import Path

import pytest

# 将src目录添加到路径
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture
def temp_cache_dir(tmp_path):
    """提供临时缓存目录"""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def sample_api_keys():
    """提供测试用API密钥样本"""
    return {
        "valid_openai": "sk-abcdefghij1234567890abcdefghij",
        "valid_gemini": "AIzaSyB1234567890123456789012345678901",
        "invalid_short": "sk-abc",
        "placeholder": "sk-your_openai_api_key_here",
        "empty": "",
    }


@pytest.fixture
def mock_config():
    """提供模拟配置"""
    return {
        "ai_services": {
            "test_service": {
                "name": "test_service",
                "api_type": "openai",
                "base_url": "https://api.test.com/",
                "api_key": "sk-test123456789012345678",
                "default_model": "gpt-3.5-turbo",
                "timeout": 60,
                "status": "active",
            }
        },
        "default_service": "test_service",
    }
