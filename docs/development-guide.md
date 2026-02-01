# 智能文献综述系统 - 开发指南

## 1. 开发环境设置

### 1.1 系统要求

- **Python**: 3.8 或更高版本
- **操作系统**: Windows / Linux / macOS
- **网络**: 需要访问 PubMed API 和 AI 服务
- **可选**: Pandoc (用于 DOCX 导出)

### 1.2 环境初始化

```bash
# 1. 克隆项目
git clone <repository-url>
cd Intelligent-Literature-Review-main

# 2. 创建虚拟环境
python -m venv venv

# 3. 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 4. 安装依赖
pip install -r requirements.txt
```

### 1.3 配置文件

#### AI服务配置 (ai_config.yaml)

```yaml
configs:
  - name: "openai_default"
    api_type: "openai"
    api_key: "your-api-key-here"
    base_url: "https://api.openai.com/v1"
    model: "gpt-4"

  - name: "gemini_default"
    api_type: "gemini"
    api_key: "your-gemini-api-key"
```

#### 系统配置 (system_config.yaml)

```yaml
cache:
  enabled: true
  ttl_hours: 24
  max_size_mb: 500

batch_processing:
  max_concurrent: 10
  chunk_size: 50

retry:
  max_attempts: 3
  delay_seconds: 1
  backoff_multiplier: 2

timeout:
  api_request_seconds: 30
  batch_operation_seconds: 300
```

## 2. 项目结构

```
src/
├── 入口模块
│   ├── start.py                 # 交互式入口
│   ├── cli.py                   # 命令行接口
│   └── intelligent_literature_system.py  # 核心系统
│
├── 业务模块
│   ├── intent_analyzer.py       # 意图分析
│   ├── pubmed_search.py         # PubMed检索
│   ├── literature_filter.py     # 文献筛选
│   ├── review_outline_generator.py   # 大纲生成
│   └── medical_review_generator.py   # 综述生成
│
└── 基础模块
    ├── ai_client.py             # AI服务客户端
    ├── data_processor.py        # 数据处理
    ├── prompts_manager.py       # 提示词管理
    ├── shared_config.py         # 配置管理
    └── exceptions.py            # 异常处理
```

## 3. 运行和测试

### 3.1 运行系统

```bash
# 交互式模式 (推荐)
python src/start.py

# 命令行模式
python src/intelligent_literature_system.py --query "糖尿病治疗近5年研究" --max-results 100

# 非交互模式
python src/intelligent_literature_system.py --query "COVID-19疫苗" --non-interactive
```

### 3.2 命令行参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--query` | 检索需求 | `--query "糖尿病治疗"` |
| `--max-results` | 最大结果数 | `--max-results 200` |
| `--non-interactive` | 非交互模式 | 无需确认 |
| `--debug` | 调试模式 | 显示详细日志 |

### 3.3 调试模式

```bash
# 启用调试输出
python src/intelligent_literature_system.py --debug --query "test query"
```

## 4. 代码规范

### 4.1 代码风格

- 遵循 PEP 8 代码风格指南
- 使用 4 空格缩进
- 最大行长度 120 字符
- 使用类型注解

### 4.2 命名规范

```python
# 类名: PascalCase
class IntentAnalyzer:
    pass

# 函数/方法: snake_case
def analyze_intent(query: str) -> dict:
    pass

# 常量: UPPER_CASE
MAX_RETRY_COUNT = 3

# 私有成员: 单下划线前缀
def _internal_method(self):
    pass
```

### 4.3 文档字符串

```python
def analyze_intent(query: str, options: dict = None) -> dict:
    """分析用户查询意图并生成检索词。

    Args:
        query: 用户输入的自然语言查询
        options: 可选的分析选项
            - language: 语言设置
            - max_terms: 最大检索词数量

    Returns:
        dict: 包含检索词和分析结果的字典
            - terms: 检索词列表
            - confidence: 置信度评分
            - suggestions: 优化建议

    Raises:
        ValidationError: 当查询为空或无效时
        APIError: 当AI服务调用失败时
    """
    pass
```

## 5. 异常处理

### 5.1 异常类层次

```python
from src.exceptions import (
    LiteratureSystemError,  # 基类
    ConfigurationError,     # 配置错误
    NetworkError,           # 网络错误
    APIError,               # API错误
    ValidationError,        # 验证错误
    ProcessingError         # 处理错误
)
```

### 5.2 使用示例

```python
from src.exceptions import APIError, NetworkError

try:
    result = ai_client.generate(prompt)
except NetworkError as e:
    logger.error(f"网络连接失败: {e}")
    # 可以尝试重试
except APIError as e:
    logger.error(f"API调用失败: {e.component} - {e.error_type}")
    # 返回错误信息给用户
```

## 6. 配置管理

### 6.1 使用SharedConfigManager

```python
from src.shared_config import SharedConfigManager

# 获取配置管理器实例 (单例)
config = SharedConfigManager.get_instance()

# 读取配置
cache_enabled = config.get("cache.enabled", default=True)
max_concurrent = config.get("batch_processing.max_concurrent", default=10)

# 获取AI模型配置
ai_config = config.get_ai_config("openai_default")
```

### 6.2 动态配置更新

```python
# 重新加载配置
config.reload()

# 检查配置是否存在
if config.has("custom.setting"):
    value = config.get("custom.setting")
```

## 7. 添加新功能

### 7.1 添加新的AI服务

```python
# src/ai_client.py

class NewAIClient(AIClient):
    """新的AI服务客户端"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.endpoint = config.get("endpoint")
        self.api_key = config.get("api_key")

    def generate(self, prompt: str, **kwargs) -> str:
        """生成响应"""
        # 实现API调用逻辑
        pass

    def generate_stream(self, prompt: str, **kwargs):
        """流式生成响应"""
        # 实现流式API调用逻辑
        yield chunk
```

### 7.2 添加新的导出格式

```python
# src/medical_review_generator.py

def export_to_new_format(self, content: str, output_path: str):
    """导出到新格式

    Args:
        content: 综述内容
        output_path: 输出文件路径
    """
    # 实现导出逻辑
    pass
```

### 7.3 添加新的筛选维度

```python
# src/literature_filter.py

def filter_by_new_criteria(self, articles: list, criteria: dict) -> list:
    """按新条件筛选文献

    Args:
        articles: 文献列表
        criteria: 筛选条件

    Returns:
        list: 筛选后的文献列表
    """
    filtered = []
    for article in articles:
        if self._matches_new_criteria(article, criteria):
            filtered.append(article)
    return filtered
```

## 8. 日志记录

### 8.1 日志配置

```python
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/system.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

### 8.2 日志使用

```python
# 信息日志
logger.info(f"开始检索: {query}")

# 警告日志
logger.warning(f"缓存即将过期: {cache_key}")

# 错误日志
logger.error(f"API调用失败: {error}", exc_info=True)

# 调试日志
logger.debug(f"请求详情: {request_data}")
```

## 9. 常见问题

### 9.1 网络问题

**问题**: PubMed API 连接超时

**解决**:
1. 检查网络连接
2. 增加超时时间 (`system_config.yaml`)
3. 使用代理 (如果需要)

### 9.2 API配额

**问题**: AI API 调用配额耗尽

**解决**:
1. 切换到备用配置
2. 减少批处理并发数
3. 启用缓存减少重复调用

### 9.3 内存问题

**问题**: 大量文献导致内存不足

**解决**:
1. 减少 `max-results` 参数
2. 增加分批处理
3. 清理缓存

## 10. 发布流程

### 10.1 版本号规范

遵循语义化版本 (SemVer):
- **主版本号**: 不兼容的API变更
- **次版本号**: 向后兼容的功能新增
- **修订号**: 向后兼容的问题修复

### 10.2 发布检查清单

- [ ] 所有测试通过
- [ ] 更新 README.md
- [ ] 更新版本号
- [ ] 更新更新日志
- [ ] 检查敏感信息未提交

---
*文档生成时间: 2026-02-01*
*BMAD Document Project Workflow v1.2.0*
