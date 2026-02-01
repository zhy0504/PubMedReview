# -*- coding: utf-8 -*-
"""
API配置安全管理模块

提供安全的API配置处理：
- 优先从环境变量读取
- 密钥脱敏显示
- 密钥验证
- 运行时安全存储
- 支持API密钥和URL配置

使用方法:
    from secrets_manager import SecretsManager

    secrets = SecretsManager()
    api_key = secrets.get_api_key("openai")
    base_url = secrets.get_base_url("openai")
    model = secrets.get_model("openai")
"""

import os
import re
from dataclasses import dataclass, field
from typing import Optional, Dict
from pathlib import Path


@dataclass
class ServiceConfig:
    """服务配置定义"""
    name: str
    key_prefix: str
    key_pattern: str
    key_env_var: str
    url_env_var: str
    model_env_var: str
    default_url: str
    default_model: str
    description: str


class SecretsManager:
    """
    API配置安全管理器

    优先级顺序:
    1. 环境变量
    2. 配置文件
    3. 运行时设置

    Example:
        manager = SecretsManager()

        # 获取完整服务配置
        key = manager.get_api_key("openai")
        url = manager.get_base_url("openai")
        model = manager.get_model("openai")

        # 验证密钥格式
        if manager.validate_api_key("openai", key):
            print("密钥格式有效")

        # 安全显示密钥
        print(manager.mask_key(key))  # sk-****...****1234
    """

    # 服务配置
    SERVICE_CONFIGS: Dict[str, ServiceConfig] = {
        "openai": ServiceConfig(
            name="OpenAI",
            key_prefix="sk-",
            key_pattern=r"^sk-[a-zA-Z0-9]{20,}$",
            key_env_var="OPENAI_API_KEY",
            url_env_var="OPENAI_BASE_URL",
            model_env_var="OPENAI_MODEL",
            default_url="https://api.openai.com/",
            default_model="gpt-4-turbo",
            description="OpenAI API"
        ),
        "openai_proxy": ServiceConfig(
            name="OpenAI Proxy",
            key_prefix="",
            key_pattern=r".{5,}",
            key_env_var="OPENAI_PROXY_API_KEY",
            url_env_var="OPENAI_PROXY_BASE_URL",
            model_env_var="OPENAI_PROXY_MODEL",
            default_url="",
            default_model="gpt-4-turbo",
            description="OpenAI代理服务"
        ),
        "gemini": ServiceConfig(
            name="Google Gemini",
            key_prefix="AIzaSy",
            key_pattern=r"^AIzaSy[a-zA-Z0-9_-]{33}$",
            key_env_var="GEMINI_API_KEY",
            url_env_var="GEMINI_BASE_URL",
            model_env_var="GEMINI_MODEL",
            default_url="https://generativelanguage.googleapis.com/",
            default_model="gemini-1.5-pro",
            description="Google Gemini API"
        ),
        "deepseek": ServiceConfig(
            name="DeepSeek",
            key_prefix="sk-",
            key_pattern=r"^sk-[a-zA-Z0-9]{20,}$",
            key_env_var="DEEPSEEK_API_KEY",
            url_env_var="DEEPSEEK_BASE_URL",
            model_env_var="DEEPSEEK_MODEL",
            default_url="https://api.deepseek.com/",
            default_model="deepseek-chat",
            description="DeepSeek API"
        ),
        "moonshot": ServiceConfig(
            name="Moonshot",
            key_prefix="sk-",
            key_pattern=r"^sk-[a-zA-Z0-9]{20,}$",
            key_env_var="MOONSHOT_API_KEY",
            url_env_var="MOONSHOT_BASE_URL",
            model_env_var="MOONSHOT_MODEL",
            default_url="https://api.moonshot.cn/",
            default_model="moonshot-v1-8k",
            description="月之暗面Kimi API"
        ),
        "ollama": ServiceConfig(
            name="Ollama",
            key_prefix="",
            key_pattern=r".*",
            key_env_var="OLLAMA_API_KEY",
            url_env_var="OLLAMA_BASE_URL",
            model_env_var="OLLAMA_MODEL",
            default_url="http://localhost:11434/",
            default_model="llama2",
            description="本地Ollama服务"
        ),
    }

    # 占位符密钥列表（不应该使用的密钥）
    PLACEHOLDER_KEYS = {
        "sk-your_openai_api_key_here",
        "sk-your_api_key_here",
        "AIzaSy_your_gemini_api_key_here",
        "sk-your_deepseek_api_key",
        "sk-your_moonshot_api_key",
        "your-api-key-here",
        "YOUR_API_KEY",
        "not-needed",
        "",
    }

    def __init__(self):
        self._runtime_keys: Dict[str, str] = {}
        self._runtime_urls: Dict[str, str] = {}
        self._runtime_models: Dict[str, str] = {}

    def get_api_key(
        self,
        service: str,
        config_key: Optional[str] = None
    ) -> Optional[str]:
        """
        获取API密钥（按优先级）

        Args:
            service: 服务名称 (openai/gemini/deepseek等)
            config_key: 从配置文件读取的密钥值

        Returns:
            API密钥字符串，如果未找到则返回None
        """
        # 1. 运行时设置的密钥（最高优先级）
        if service in self._runtime_keys:
            return self._runtime_keys[service]

        # 2. 环境变量
        config = self.SERVICE_CONFIGS.get(service)
        if config:
            env_key = os.environ.get(config.key_env_var)
            if env_key and not self.is_placeholder(env_key):
                return env_key

        # 3. 配置文件中的密钥
        if config_key and not self.is_placeholder(config_key):
            return config_key

        return None

    def get_base_url(
        self,
        service: str,
        config_url: Optional[str] = None
    ) -> Optional[str]:
        """
        获取API基础URL（按优先级）

        Args:
            service: 服务名称
            config_url: 从配置文件读取的URL

        Returns:
            API URL字符串
        """
        # 1. 运行时设置
        if service in self._runtime_urls:
            return self._runtime_urls[service]

        # 2. 环境变量
        config = self.SERVICE_CONFIGS.get(service)
        if config:
            env_url = os.environ.get(config.url_env_var)
            if env_url:
                return env_url

        # 3. 配置文件
        if config_url:
            return config_url

        # 4. 默认值
        if config:
            return config.default_url

        return None

    def get_model(
        self,
        service: str,
        config_model: Optional[str] = None
    ) -> Optional[str]:
        """
        获取默认模型名称（按优先级）

        Args:
            service: 服务名称
            config_model: 从配置文件读取的模型名

        Returns:
            模型名称字符串
        """
        # 1. 运行时设置
        if service in self._runtime_models:
            return self._runtime_models[service]

        # 2. 环境变量
        config = self.SERVICE_CONFIGS.get(service)
        if config:
            env_model = os.environ.get(config.model_env_var)
            if env_model:
                return env_model

        # 3. 配置文件
        if config_model:
            return config_model

        # 4. 默认值
        if config:
            return config.default_model

        return None

    def set_runtime_key(self, service: str, key: str) -> None:
        """运行时设置API密钥"""
        if key and not self.is_placeholder(key):
            self._runtime_keys[service] = key

    def set_runtime_url(self, service: str, url: str) -> None:
        """运行时设置API URL"""
        if url:
            self._runtime_urls[service] = url

    def set_runtime_model(self, service: str, model: str) -> None:
        """运行时设置默认模型"""
        if model:
            self._runtime_models[service] = model

    def is_placeholder(self, key: str) -> bool:
        """检查是否为占位符密钥"""
        if not key:
            return True
        key_lower = key.lower().strip()
        return key_lower in {k.lower() for k in self.PLACEHOLDER_KEYS}

    def validate_api_key(self, service: str, key: str) -> bool:
        """
        验证API密钥格式

        Args:
            service: 服务名称
            key: API密钥

        Returns:
            格式是否有效
        """
        if not key or self.is_placeholder(key):
            return False

        config = self.SERVICE_CONFIGS.get(service)
        if not config:
            # 未知服务，基本检查
            return len(key) >= 10

        # 检查前缀（如果有）
        if config.key_prefix and not key.startswith(config.key_prefix):
            return False

        # 正则验证
        return bool(re.match(config.key_pattern, key))

    def mask_key(self, key: str, visible_chars: int = 4) -> str:
        """
        脱敏显示API密钥

        Args:
            key: 原始密钥
            visible_chars: 前后各显示的字符数

        Returns:
            脱敏后的密钥字符串

        Example:
            mask_key("sk-abc123456789xyz")  # "sk-a****...****xyz"
        """
        if not key:
            return "[未设置]"

        if self.is_placeholder(key):
            return "[占位符]"

        if len(key) <= visible_chars * 2:
            return "*" * len(key)

        prefix = key[:visible_chars + 3]  # 保留前缀如 "sk-a"
        suffix = key[-visible_chars:]
        return f"{prefix}****...****{suffix}"

    def get_env_var_name(self, service: str) -> Optional[str]:
        """获取服务对应的密钥环境变量名"""
        config = self.SERVICE_CONFIGS.get(service)
        return config.key_env_var if config else None

    def check_env_configured(self, service: str) -> bool:
        """检查环境变量是否已配置"""
        config = self.SERVICE_CONFIGS.get(service)
        if not config:
            return False
        env_key = os.environ.get(config.key_env_var)
        return bool(env_key and not self.is_placeholder(env_key))

    def get_service_config(self, service: str) -> Optional[ServiceConfig]:
        """获取服务的完整配置"""
        return self.SERVICE_CONFIGS.get(service)

    def get_security_recommendations(self) -> list:
        """获取安全建议列表"""
        recommendations = []

        # 检查环境变量配置
        for service, config in self.SERVICE_CONFIGS.items():
            if not self.check_env_configured(service):
                recommendations.append(
                    f"建议设置环境变量 {config.key_env_var} 存储{config.description}密钥"
                )

        return recommendations[:5]  # 最多返回5条建议


def create_env_template() -> str:
    """生成环境变量模板"""
    manager = SecretsManager()
    lines = [
        "# API配置环境变量模板",
        "# 将此文件另存为 .env 并填入实际值",
        "# 注意：.env 文件不应提交到版本控制",
        "",
    ]

    for service, config in manager.SERVICE_CONFIGS.items():
        lines.append(f"# {config.description}")
        lines.append(f"{config.key_env_var}={config.key_prefix}your_key_here")
        lines.append(f"{config.url_env_var}={config.default_url}")
        lines.append(f"{config.model_env_var}={config.default_model}")
        lines.append("")

    return "\n".join(lines)


# 全局单例
_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager() -> SecretsManager:
    """获取全局密钥管理器实例"""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager


# 导出接口
__all__ = [
    'SecretsManager',
    'ServiceConfig',
    'get_secrets_manager',
    'create_env_template',
]
