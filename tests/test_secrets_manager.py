# -*- coding: utf-8 -*-
"""
密钥管理模块单元测试
"""

import os
import pytest

from secrets_manager import SecretsManager, get_secrets_manager


class TestSecretsManager:
    """SecretsManager测试"""

    def test_is_placeholder_detection(self, sample_api_keys):
        """测试占位符检测"""
        manager = SecretsManager()
        assert manager.is_placeholder(sample_api_keys["placeholder"])
        assert manager.is_placeholder(sample_api_keys["empty"])
        assert manager.is_placeholder("YOUR_API_KEY")
        assert not manager.is_placeholder(sample_api_keys["valid_openai"])

    def test_validate_openai_key(self, sample_api_keys):
        """测试OpenAI密钥验证"""
        manager = SecretsManager()
        assert manager.validate_api_key("openai", sample_api_keys["valid_openai"])
        assert not manager.validate_api_key("openai", sample_api_keys["invalid_short"])
        assert not manager.validate_api_key("openai", sample_api_keys["placeholder"])

    def test_validate_gemini_key(self, sample_api_keys):
        """测试Gemini密钥验证"""
        manager = SecretsManager()
        assert manager.validate_api_key("gemini", sample_api_keys["valid_gemini"])
        assert not manager.validate_api_key("gemini", "invalid_key")

    def test_mask_key(self, sample_api_keys):
        """测试密钥脱敏"""
        manager = SecretsManager()
        masked = manager.mask_key(sample_api_keys["valid_openai"])
        assert "****" in masked
        assert masked.startswith("sk-")
        assert not sample_api_keys["valid_openai"] in masked

    def test_mask_empty_key(self):
        """测试空密钥脱敏"""
        manager = SecretsManager()
        assert manager.mask_key("") == "[未设置]"
        assert manager.mask_key(None) == "[未设置]"

    def test_mask_placeholder(self, sample_api_keys):
        """测试占位符密钥脱敏"""
        manager = SecretsManager()
        assert manager.mask_key(sample_api_keys["placeholder"]) == "[占位符]"

    def test_runtime_key_priority(self, sample_api_keys):
        """测试运行时密钥优先级"""
        manager = SecretsManager()
        manager.set_runtime_key("openai", sample_api_keys["valid_openai"])
        result = manager.get_api_key("openai", config_key="config_key_value")
        assert result == sample_api_keys["valid_openai"]

    def test_config_key_fallback(self, sample_api_keys):
        """测试配置密钥作为fallback"""
        manager = SecretsManager()
        result = manager.get_api_key("openai", config_key=sample_api_keys["valid_openai"])
        assert result == sample_api_keys["valid_openai"]

    def test_env_var_names(self):
        """测试环境变量名获取"""
        manager = SecretsManager()
        assert manager.get_env_var_name("openai") == "OPENAI_API_KEY"
        assert manager.get_env_var_name("gemini") == "GEMINI_API_KEY"
        assert manager.get_env_var_name("unknown") is None

    def test_security_recommendations(self):
        """测试安全建议生成"""
        manager = SecretsManager()
        recommendations = manager.get_security_recommendations()
        assert isinstance(recommendations, list)
        assert len(recommendations) <= 5


class TestURLAndModelConfig:
    """URL和模型配置测试"""

    def test_get_base_url_default(self):
        """测试默认URL获取"""
        manager = SecretsManager()
        url = manager.get_base_url("openai")
        assert url == "https://api.openai.com/"

    def test_get_base_url_from_config(self):
        """测试从配置获取URL"""
        manager = SecretsManager()
        url = manager.get_base_url("openai", config_url="https://custom.api.com/")
        assert url == "https://custom.api.com/"

    def test_set_runtime_url(self):
        """测试运行时设置URL"""
        manager = SecretsManager()
        manager.set_runtime_url("openai", "https://runtime.api.com/")
        url = manager.get_base_url("openai", config_url="https://config.api.com/")
        assert url == "https://runtime.api.com/"

    def test_get_model_default(self):
        """测试默认模型获取"""
        manager = SecretsManager()
        model = manager.get_model("deepseek")
        assert model == "deepseek-chat"

    def test_get_model_from_config(self):
        """测试从配置获取模型"""
        manager = SecretsManager()
        model = manager.get_model("openai", config_model="gpt-4o")
        assert model == "gpt-4o"

    def test_set_runtime_model(self):
        """测试运行时设置模型"""
        manager = SecretsManager()
        manager.set_runtime_model("openai", "gpt-4-turbo-preview")
        model = manager.get_model("openai", config_model="gpt-3.5-turbo")
        assert model == "gpt-4-turbo-preview"

    def test_get_service_config(self):
        """测试获取服务完整配置"""
        manager = SecretsManager()
        config = manager.get_service_config("gemini")
        assert config is not None
        assert config.name == "Google Gemini"
        assert config.default_url == "https://generativelanguage.googleapis.com/"


class TestGetSecretsManager:
    """全局单例测试"""

    def test_singleton(self):
        """测试单例模式"""
        manager1 = get_secrets_manager()
        manager2 = get_secrets_manager()
        assert manager1 is manager2
