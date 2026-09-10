# -*- coding: utf-8 -*-
"""
AI服务配置管理模块

完全从环境变量(.env)加载AI服务配置，替代yaml配置文件。
支持多服务配置、服务切换、运行时覆盖。

使用方法:
    from ai_config import AIConfigManager, get_ai_config

    config = get_ai_config()
    service = config.get_active_service()

    # 获取服务配置
    api_key = service.api_key
    base_url = service.base_url
    model = service.model
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from pathlib import Path
from ai_providers import PROVIDER_PROFILES
from openai_protocol import is_deepseek_url, is_zhipu_url

# 尝试加载 python-dotenv（如果可用）
try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


def _parse_env_file(env_path: Path) -> Dict[str, str]:
    """
    内置 .env 文件解析器（python-dotenv 不可用时的后备方案）

    支持：
    - KEY=value 格式
    - 带引号的值 KEY="value" 或 KEY='value'
    - 注释行 (# 开头)
    - 空行跳过
    """
    env_vars = {}

    if not env_path.exists():
        return env_vars

    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()

                # 跳过空行和注释
                if not line or line.startswith('#'):
                    continue

                # 解析 KEY=VALUE
                if '=' in line:
                    key, _, value = line.partition('=')
                    key = key.strip()
                    value = value.strip()

                    # 移除引号
                    if len(value) >= 2:
                        if (value.startswith('"') and value.endswith('"')) or \
                           (value.startswith("'") and value.endswith("'")):
                            value = value[1:-1]

                    if key:
                        env_vars[key] = value
    except Exception:
        pass

    return env_vars


@dataclass
class AIServiceConfig:
    """AI服务配置"""
    name: str
    api_type: str  # "openai" 或 "gemini"
    api_key: str
    base_url: str
    model: str
    timeout: int = 300
    status: str = "active"
    description: str = ""
    requires_api_key: bool = True

    def is_active(self) -> bool:
        """检查服务是否激活"""
        return self.status.lower() == "active"

    def is_valid(self) -> bool:
        """检查配置是否有效"""
        if self.requires_api_key and (not self.api_key or self.api_key.startswith("sk-your")):
            return False
        if not self.base_url:
            return False
        return True


class AIConfigManager:
    """
    AI配置管理器

    从环境变量加载所有AI服务配置，支持：
    - 多服务配置
    - 默认服务选择
    - 运行时服务切换
    - 环境变量优先
    """

    # 支持的服务列表及其环境变量前缀
    SERVICE_PREFIXES = {
        service_id: (profile.env_prefix, profile.api_type)
        for service_id, profile in PROVIDER_PROFILES.items()
    }

    # 默认配置
    DEFAULTS = {
        service_id: {
            "base_url": profile.base_url,
            "model": profile.default_model,
            "description": profile.description,
        }
        for service_id, profile in PROVIDER_PROFILES.items()
    }

    _instance: Optional['AIConfigManager'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._services: Dict[str, AIServiceConfig] = {}
        self._default_service: Optional[str] = None
        self._active_service: Optional[str] = None
        self._settings: Dict[str, Any] = {}

        # 加载 .env 文件
        self._load_dotenv()

        # 加载配置
        self._load_services()
        self._load_settings()

        self._initialized = True

    @staticmethod
    def _safe_int(value: Any, default: int, min_value: Optional[int] = None) -> int:
        """安全解析整数环境变量，异常或越界时回退默认值。"""
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError):
            return default

        if min_value is not None and parsed < min_value:
            return default
        return parsed

    def _load_dotenv(self):
        """加载 .env 文件"""
        # 查找 .env 文件
        current_dir = Path(__file__).parent
        project_root = current_dir.parent

        env_paths = [
            project_root / ".env",
            current_dir / ".env",
            Path.cwd() / ".env",
        ]

        env_file = None
        for env_path in env_paths:
            if env_path.exists():
                env_file = env_path
                break

        if not env_file:
            return

        # 优先使用 python-dotenv
        if DOTENV_AVAILABLE:
            load_dotenv(env_file)
        else:
            # 使用内置解析器作为后备
            env_vars = _parse_env_file(env_file)
            for key, value in env_vars.items():
                # 不覆盖已存在的环境变量
                if key not in os.environ:
                    os.environ[key] = value

    def _load_services(self):
        """从环境变量加载所有服务配置"""
        self._services.clear()
        for service_name, (prefix, api_type) in self.SERVICE_PREFIXES.items():
            config = self._load_service_config(service_name, prefix, api_type)
            if config:
                self._services[service_name] = config

        # 加载默认服务
        self._default_service = os.environ.get("DEFAULT_AI_SERVICE", "openai")
        self._active_service = self._default_service

    def _load_service_config(
        self,
        service_name: str,
        prefix: str,
        api_type: str
    ) -> Optional[AIServiceConfig]:
        """加载单个服务配置"""
        defaults = self.DEFAULTS.get(service_name, {})

        api_key = os.environ.get(f"{prefix}_API_KEY", "")
        configured_base_url = os.environ.get(f"{prefix}_BASE_URL")
        configured_model = os.environ.get(f"{prefix}_MODEL")
        configured_status = os.environ.get(f"{prefix}_STATUS")
        base_url = configured_base_url or defaults.get("base_url", "")
        model = configured_model if configured_model is not None and configured_model.strip() else defaults.get("model", "")
        if (not configured_model or not configured_model.strip()) and is_deepseek_url(base_url):
            model = self.DEFAULTS['deepseek']['model']
        elif (not configured_model or not configured_model.strip()) and is_zhipu_url(base_url):
            model = self.DEFAULTS['zhipu']['model']
        timeout = self._safe_int(os.environ.get(f"{prefix}_TIMEOUT", "300"), default=300, min_value=1)
        profile = PROVIDER_PROFILES.get(service_name)
        requires_api_key = profile.requires_api_key if profile else True
        local_configured = bool(configured_base_url or configured_model or configured_status)
        explicitly_selected = os.environ.get("DEFAULT_AI_SERVICE", "").strip().lower() == service_name
        status = configured_status or ("active" if (api_key or (not requires_api_key and (local_configured or explicitly_selected))) else "inactive")

        # 检查是否为占位符
        if requires_api_key and self._is_placeholder(api_key):
            status = "inactive"

        return AIServiceConfig(
            name=service_name,
            api_type=os.environ.get(f'{prefix}_API_TYPE', api_type),
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout=timeout,
            status=status,
            description=defaults.get("description", service_name),
            requires_api_key=requires_api_key,
        )

    def _load_settings(self):
        """加载通用设置"""
        self._settings = {
            "request_timeout": self._safe_int(
                os.environ.get("AI_REQUEST_TIMEOUT", "300"), default=300, min_value=1
            ),
            "max_retries": self._safe_int(
                os.environ.get("AI_MAX_RETRIES", "3"), default=3, min_value=0
            ),
            "enable_streaming": os.environ.get("AI_ENABLE_STREAMING", "true").lower() == "true",
            "allow_service_switch": os.environ.get("AI_ALLOW_SERVICE_SWITCH", "true").lower() == "true",
        }

    def reload(self, reload_env: bool = True, preserve_active_service: bool = True) -> None:
        """重新从环境变量加载配置。"""
        previous_active = self._active_service if preserve_active_service else None

        if reload_env:
            self._load_dotenv()
        self._load_services()
        self._load_settings()

        if preserve_active_service and previous_active in self._services:
            self._active_service = previous_active

    def _is_placeholder(self, key: str) -> bool:
        """检查是否为占位符"""
        if not key:
            return True
        placeholders = {
            "sk-your", "aizasy_your", "your_key", "your-key",
            "your_api_key", "not-needed", "placeholder"
        }
        key_lower = key.lower()
        return any(p in key_lower for p in placeholders)

    # ==================== 公共API ====================

    def get_service(self, name: str) -> Optional[AIServiceConfig]:
        """获取指定服务配置"""
        return self._services.get(name)

    def get_active_service(self) -> Optional[AIServiceConfig]:
        """获取当前活动服务"""
        return self._services.get(self._active_service)

    def get_default_service(self) -> Optional[AIServiceConfig]:
        """获取默认服务"""
        return self._services.get(self._default_service)

    def set_active_service(self, name: str) -> bool:
        """设置当前活动服务"""
        if name in self._services:
            self._active_service = name
            return True
        return False

    def list_services(self) -> List[str]:
        """列出所有服务名称"""
        return list(self._services.keys())

    def list_active_services(self) -> List[AIServiceConfig]:
        """列出所有激活的服务"""
        return [s for s in self._services.values() if s.is_active()]

    def list_valid_services(self) -> List[AIServiceConfig]:
        """列出所有有效的服务（激活且配置有效）"""
        return [s for s in self._services.values() if s.is_active() and s.is_valid()]

    def get_setting(self, key: str, default: Any = None) -> Any:
        """获取设置项"""
        return self._settings.get(key, default)

    def get_first_valid_service(self) -> Optional[AIServiceConfig]:
        """获取第一个有效的服务"""
        # 优先返回活动服务
        active = self.get_active_service()
        if active and active.is_valid():
            return active

        # 查找其他有效服务
        for service in self.list_valid_services():
            return service

        return None

    # ==================== 兼容性API ====================

    def get_config(self, service_name: str = None) -> Optional[Dict[str, Any]]:
        """
        兼容旧API：获取服务配置字典

        Returns:
            {
                'name': str,
                'api_type': str,
                'api_key': str,
                'base_url': str,
                'default_model': str,
                'timeout': int,
                'status': str,
            }
        """
        service = self._services.get(service_name) if service_name else self.get_active_service()
        if not service:
            return None

        return {
            'name': service.name,
            'api_type': service.api_type,
            'api_key': service.api_key,
            'base_url': service.base_url,
            'default_model': service.model,
            'timeout': service.timeout,
            'status': service.status,
            'description': service.description,
        }

    def get_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """兼容旧API：获取所有服务配置"""
        return {name: self.get_config(name) for name in self._services}

    def show_services_status(self):
        """显示服务状态（用于CLI）"""
        print("\n" + "=" * 50)
        print("AI服务配置状态")
        print("=" * 50)

        for name, service in self._services.items():
            status_icon = "✓" if service.is_active() and service.is_valid() else "✗"
            active_mark = " [当前]" if name == self._active_service else ""
            print(f"  {status_icon} {name}: {service.description}{active_mark}")
            if service.is_active():
                masked_key = self._mask_key(service.api_key)
                print(f"      URL: {service.base_url}")
                print(f"      Key: {masked_key}")
                print(f"      Model: {service.model}")

        print("=" * 50 + "\n")

    def _mask_key(self, key: str) -> str:
        """脱敏显示密钥"""
        if not key or len(key) < 10:
            return "[未配置]"
        if self._is_placeholder(key):
            return "[占位符]"
        return f"{key[:7]}****{key[-4:]}"

    @classmethod
    def reset_instance(cls) -> None:
        """重置单例（用于测试或需要彻底重载的场景）。"""
        cls._instance = None


# 全局单例
_ai_config: Optional[AIConfigManager] = None


def get_ai_config(force_reload: bool = False) -> AIConfigManager:
    """获取AI配置管理器实例"""
    global _ai_config
    if _ai_config is None:
        _ai_config = AIConfigManager()
    elif force_reload:
        _ai_config.reload()
    return _ai_config


def reset_ai_config_cache() -> None:
    """重置全局AI配置缓存（主要用于测试）。"""
    global _ai_config
    _ai_config = None
    AIConfigManager.reset_instance()


# 兼容性函数
def load_ai_config(config_file: str = None) -> AIConfigManager:
    """
    兼容旧API：加载AI配置

    注意：config_file 参数已废弃，配置现在从环境变量加载
    """
    return get_ai_config()


# 导出接口
__all__ = [
    'AIConfigManager',
    'AIServiceConfig',
    'get_ai_config',
    'reset_ai_config_cache',
    'load_ai_config',
]
