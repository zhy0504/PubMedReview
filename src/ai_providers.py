"""AI provider registry shared by configuration, HTTP and Web workbench.

The registry deliberately keeps provider-specific data in one place.  Most
commercial services expose an OpenAI-compatible endpoint, so adding a new
provider should not require another copy of the request/response adapter.
"""

from dataclasses import asdict, dataclass
import re
from urllib.parse import urlsplit


@dataclass(frozen=True)
class ProviderProfile:
    """Wire-level capabilities and defaults for one AI service."""

    id: str
    label: str
    env_prefix: str
    api_type: str
    base_url: str
    default_model: str
    description: str
    request_style: str = "legacy"
    supports_responses: bool = False
    supports_model_discovery: bool = True
    requires_api_key: bool = True
    model_prefixes: tuple = ()


PROVIDER_PROFILES = {
    "openai": ProviderProfile(
        "openai", "OpenAI", "OPENAI", "openai", "https://api.openai.com/",
        "gpt-4-turbo", "OpenAI 官方 API", "openai", True, True, True, (),
    ),
    "openai_proxy": ProviderProfile(
        "openai_proxy", "OpenAI 兼容代理", "OPENAI_PROXY", "openai", "",
        "gpt-4-turbo", "自定义 OpenAI 兼容服务", "openai", True, True, True, (),
    ),
    "deepseek": ProviderProfile(
        "deepseek", "DeepSeek", "DEEPSEEK", "openai", "https://api.deepseek.com",
        "deepseek-v4-flash", "DeepSeek API", "deepseek", True, True, True, ("deepseek-",),
    ),
    "zhipu": ProviderProfile(
        "zhipu", "智谱 GLM", "ZHIPU", "openai", "https://open.bigmodel.cn/api/paas/v4",
        "glm-5.3", "智谱 AI OpenAI 兼容接口", "legacy", False, True, True, ("glm-", "charglm-"),
    ),
    "moonshot": ProviderProfile(
        "moonshot", "月之暗面 Kimi", "MOONSHOT", "openai", "https://api.moonshot.cn/v1",
        "moonshot-v1-8k", "Kimi OpenAI 兼容接口", "legacy", True, True, True, ("moonshot-", "kimi-"),
    ),
    "qwen": ProviderProfile(
        "qwen", "阿里通义千问", "DASHSCOPE", "openai", "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "qwen-plus", "DashScope OpenAI 兼容接口", "legacy", False, True, True, (),
    ),
    "volcengine_ark": ProviderProfile(
        "volcengine_ark", "火山方舟 / 豆包", "VOLCENGINE_ARK", "openai", "https://ark.cn-beijing.volces.com/api/v3",
        "doubao-seed-2-0-lite-260215", "火山方舟 OpenAI 兼容接口", "legacy", True, True, True, (),
    ),
    "siliconflow": ProviderProfile(
        "siliconflow", "SiliconFlow", "SILICONFLOW", "openai", "https://api.siliconflow.cn/v1",
        "deepseek-ai/DeepSeek-V4-Flash", "SiliconFlow OpenAI 兼容接口", "legacy", False, True, True, (),
    ),
    "openrouter": ProviderProfile(
        "openrouter", "OpenRouter", "OPENROUTER", "openai", "https://openrouter.ai/api/v1",
        "openai/gpt-4o-mini", "多模型路由服务", "legacy", False, True, True, (),
    ),
    "groq": ProviderProfile(
        "groq", "Groq", "GROQ", "openai", "https://api.groq.com/openai/v1",
        "llama-3.3-70b-versatile", "Groq OpenAI 兼容接口", "legacy", True, True, True, (),
    ),
    "together": ProviderProfile(
        "together", "Together AI", "TOGETHER", "openai", "https://api.together.ai/v1",
        "meta-llama/Llama-3.3-70B-Instruct-Turbo", "Together AI OpenAI 兼容接口", "legacy", False, True, True, (),
    ),
    "mistral": ProviderProfile(
        "mistral", "Mistral AI", "MISTRAL", "openai", "https://api.mistral.ai/v1",
        "mistral-small-latest", "Mistral OpenAI 兼容接口", "legacy", False, True, True, (),
    ),
    "gemini": ProviderProfile(
        "gemini", "Google Gemini", "GEMINI", "gemini", "https://generativelanguage.googleapis.com/",
        "gemini-3.8-flash", "Google Gemini 原生接口", "gemini", False, True, True, ("gemini-", "models/gemini-"),
    ),
    "anthropic": ProviderProfile(
        "anthropic", "Anthropic Claude", "ANTHROPIC", "anthropic", "https://api.anthropic.com",
        "claude-sonnet-5", "Anthropic Messages API", "anthropic", False, False, True, ("claude-",),
    ),
    "ollama": ProviderProfile(
        "ollama", "Ollama（本地）", "OLLAMA", "openai", "http://localhost:11434/v1",
        "llama3.2", "本地 Ollama OpenAI 兼容接口", "legacy", False, True, False, (),
    ),
    "lmstudio": ProviderProfile(
        "lmstudio", "LM Studio（本地）", "LMSTUDIO", "openai", "http://localhost:1234/v1",
        "local-model", "本地 LM Studio OpenAI 兼容接口", "legacy", False, True, False, (),
    ),
}


def get_provider(provider_id):
    """Return a profile by id, or ``None`` for a custom provider."""
    return PROVIDER_PROFILES.get(str(provider_id or "").strip().lower())


def provider_for_url(base_url):
    """Best-effort provider detection used for legacy configurations."""
    try:
        parsed = urlsplit(str(base_url or ""))
    except ValueError:
        return "openai_proxy"
    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()
    if host == "api.openai.com":
        return "openai"
    if host == "api.deepseek.com" or host.endswith(".deepseek.com"):
        return "deepseek"
    if host == "open.bigmodel.cn" or host.endswith(".bigmodel.cn"):
        return "zhipu"
    if host == "api.moonshot.cn" or host.endswith(".moonshot.cn"):
        return "moonshot"
    if host == "dashscope.aliyuncs.com" or host.endswith(".dashscope.aliyuncs.com"):
        return "qwen"
    if host.endswith("volces.com") or host.endswith("volcengine.com"):
        return "volcengine_ark"
    if host == "api.siliconflow.cn" or host.endswith(".siliconflow.cn"):
        return "siliconflow"
    if host == "openrouter.ai" or host.endswith(".openrouter.ai"):
        return "openrouter"
    if host == "api.groq.com" or host.endswith(".groq.com"):
        return "groq"
    if host == "api.together.ai" or host.endswith(".together.ai"):
        return "together"
    if host == "api.mistral.ai" or host.endswith(".mistral.ai"):
        return "mistral"
    if host == "generativelanguage.googleapis.com" and "/openai" not in path:
        return "gemini"
    if host == "api.anthropic.com" or host.endswith(".anthropic.com"):
        return "anthropic"
    if host in {"localhost", "127.0.0.1", "::1"}:
        if parsed.port == 11434:
            return "ollama"
        if parsed.port == 1234:
            return "lmstudio"
    return "openai_proxy"


def resolve_provider(provider_id=None, base_url=None):
    """Resolve an explicit provider first, then infer it from its URL."""
    explicit = get_provider(provider_id)
    if explicit:
        return explicit
    return get_provider(provider_for_url(base_url))


def provider_env_prefix(provider_id, base_url=None):
    profile = resolve_provider(provider_id, base_url)
    return profile.env_prefix if profile else "OPENAI_PROXY"


def provider_api_type(provider_id=None, base_url=None):
    profile = resolve_provider(provider_id, base_url)
    return profile.api_type if profile else "openai"


def provider_options(include_sensitive=False):
    """Return UI-safe provider metadata."""
    items = []
    for profile in PROVIDER_PROFILES.values():
        item = asdict(profile)
        item["model_prefixes"] = list(profile.model_prefixes)
        if not include_sensitive:
            item.pop("env_prefix", None)
        items.append(item)
    return items


def is_versioned_path(path):
    """Whether a URL path already contains a versioned API prefix."""
    return bool(re.search(r"/(?:v\d+(?:[a-z0-9._-]*)?)(?:/|$)", str(path or "").lower()))


__all__ = [
    "ProviderProfile",
    "PROVIDER_PROFILES",
    "get_provider",
    "provider_for_url",
    "resolve_provider",
    "provider_env_prefix",
    "provider_api_type",
    "provider_options",
    "is_versioned_path",
]
