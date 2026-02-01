# 智能文献综述系统 - 架构文档

## 1. 执行摘要

智能文献综述系统是一个基于AI大模型的医学文献检索与综述自动生成工具。系统采用分层管道架构，通过集成PubMed E-utilities API和多种AI服务（OpenAI、Google Gemini），实现从用户需求到完整综述的自动化流程。

### 核心价值

- **智能化**: AI驱动的意图分析和内容生成
- **自动化**: 端到端的文献综述生成流程
- **专业化**: 支持中科院/JCR分区的期刊质量筛选

## 2. 系统架构

### 2.1 架构概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        用户界面层 (Presentation Layer)               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐ │
│  │  start.py   │  │   cli.py    │  │ intelligent_literature_     │ │
│  │ (交互式)    │  │ (命令行)    │  │ system.py (核心入口)        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────┤
│                        业务逻辑层 (Business Logic Layer)             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ intent_analyzer  │  │ literature_filter │  │ review_outline_  │  │
│  │ (意图分析)       │  │ (文献筛选)        │  │ generator(大纲)  │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
│  ┌──────────────────┐  ┌──────────────────┐                        │
│  │ medical_review_  │  │ smart_literature_│                        │
│  │ generator(综述)  │  │ search (智能搜索)│                        │
│  └──────────────────┘  └──────────────────┘                        │
├─────────────────────────────────────────────────────────────────────┤
│                        服务集成层 (Service Integration Layer)        │
│  ┌──────────────────┐  ┌──────────────────┐                        │
│  │   ai_client      │  │  pubmed_search   │                        │
│  │ (AI服务客户端)   │  │ (PubMed检索)     │                        │
│  │ ├─ OpenAI API   │  │ ├─ E-utilities   │                        │
│  │ └─ Gemini API   │  │ └─ 异步批量检索  │                        │
│  └──────────────────┘  └──────────────────┘                        │
├─────────────────────────────────────────────────────────────────────┤
│                        基础设施层 (Infrastructure Layer)             │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐   │
│  │ shared_    │  │ exceptions │  │ data_      │  │ prompts_   │   │
│  │ config     │  │ (异常处理) │  │ processor  │  │ manager    │   │
│  │ (配置管理) │  │            │  │ (数据处理) │  │ (提示词)   │   │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│                        数据持久层 (Data Persistence Layer)           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐   │
│  │ data/*.csv │  │ cache/     │  │pubmed_cache│  │ logs/      │   │
│  │ (期刊数据) │  │ (通用缓存) │  │ (检索缓存) │  │ (日志)     │   │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流架构

```
用户输入检索需求
        │
        ▼
┌───────────────────┐
│   意图分析器      │ ← AI模型 (GPT/Gemini)
│ intent_analyzer   │
└───────────────────┘
        │ 生成检索词
        ▼
┌───────────────────┐
│   PubMed检索      │ ← E-utilities API
│   pubmed_search   │
└───────────────────┘
        │ 原始文献列表
        ▼
┌───────────────────┐
│   文献筛选        │ ← 期刊分区数据
│ literature_filter │
└───────────────────┘
        │ 高质量文献
        ▼
┌───────────────────┐
│   大纲生成器      │ ← AI模型
│ review_outline    │
└───────────────────┘
        │ 结构化大纲
        ▼
┌───────────────────┐
│   综述生成器      │ ← AI模型
│ medical_review    │
└───────────────────┘
        │ 完整综述
        ▼
   多格式导出
   (MD/DOCX/CSV/JSON/BibTeX)
```

## 3. 模块设计

### 3.1 核心模块

#### intelligent_literature_system.py

**职责**: 系统核心协调器，管理完整工作流

**主要类/函数**:
- `IntelligentLiteratureSystem`: 主系统类
- `main()`: 命令行入口
- `main_async()`: 异步主函数

**依赖关系**:
```python
from ai_client import AIClient
from intent_analyzer import IntentAnalyzer
from pubmed_search import PubMedSearcher
from literature_filter import LiteratureFilter
from review_outline_generator import ReviewOutlineGenerator
from medical_review_generator import MedicalReviewGenerator
```

#### ai_client.py

**职责**: AI服务抽象层，统一管理多种AI服务

**主要类**:
- `AIClient`: AI客户端基类
- `OpenAIClient`: OpenAI兼容API客户端
- `GeminiClient`: Google Gemini API客户端

**特性**:
- 流式输出支持
- 自动重试机制
- 配置热切换

#### pubmed_search.py

**职责**: PubMed E-utilities API集成

**主要类**:
- `PubMedSearcher`: 异步文献检索器

**特性**:
- 批量异步检索
- 结果缓存
- 速率限制处理

### 3.2 业务模块

#### intent_analyzer.py

**职责**: 用户意图分析，生成检索策略

**输入**: 自然语言检索需求
**输出**: 结构化检索词列表

#### literature_filter.py

**职责**: 文献质量筛选

**筛选维度**:
- 中科院分区 (1-4区)
- JCR分区 (Q1-Q4)
- 影响因子范围
- 发表时间范围

#### review_outline_generator.py

**职责**: 综述大纲生成

**功能**:
- 文献摘要聚类
- 主题提取
- 结构化大纲生成

#### medical_review_generator.py

**职责**: 完整综述撰写

**功能**:
- 基于大纲生成正文
- 引用格式化
- 多格式导出

### 3.3 基础设施模块

#### shared_config.py

**职责**: 统一配置管理

**设计模式**: 单例模式

```python
class SharedConfigManager:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
```

#### exceptions.py

**职责**: 统一异常处理

**异常层次**:
```
LiteratureSystemError (基类)
├── ConfigurationError (配置错误)
├── NetworkError (网络错误)
├── APIError (API错误)
├── ValidationError (验证错误)
└── ProcessingError (处理错误)
```

## 4. 外部集成

### 4.1 PubMed E-utilities

**端点**: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`

**使用的API**:
- `esearch`: 搜索文献
- `efetch`: 获取详情
- `einfo`: 数据库信息

**注意事项**:
- 速率限制: 3请求/秒 (无API Key)
- 推荐使用API Key提升限额

### 4.2 OpenAI API

**端点**: 配置于 `ai_config.yaml`

**使用模型**:
- GPT-4
- GPT-3.5-Turbo
- 兼容的第三方模型

### 4.3 Google Gemini API

**端点**: `https://generativelanguage.googleapis.com/`

**使用模型**:
- Gemini Pro
- Gemini 2.5

## 5. 配置管理

### 5.1 配置文件

| 文件 | 用途 | 格式 |
|------|------|------|
| `ai_config.yaml` | AI服务配置 | YAML |
| `system_config.yaml` | 系统参数配置 | YAML |
| `prompts/prompts_config.yaml` | AI提示词模板 | YAML |

### 5.2 系统配置项

```yaml
# system_config.yaml 示例
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

## 6. 缓存策略

### 6.1 缓存类型

| 缓存类型 | 位置 | 用途 |
|----------|------|------|
| PubMed缓存 | `pubmed_cache/` | 检索结果缓存 |
| 通用缓存 | `cache/` | 处理中间结果 |
| 模型缓存 | `ai_model_cache.json` | AI模型配置缓存 |

### 6.2 缓存策略

- **TTL**: 默认24小时过期
- **LRU**: 超出容量时清理最少使用的缓存
- **按需刷新**: 可手动清理重新获取

## 7. 错误处理

### 7.1 异常处理策略

1. **网络错误**: 自动重试 (最多3次)
2. **API错误**: 记录日志，返回友好错误信息
3. **配置错误**: 启动时验证，提前失败
4. **数据错误**: 验证输入，拒绝无效数据

### 7.2 日志记录

```
logs/
├── system.log      # 系统日志
├── error.log       # 错误日志
└── debug.log       # 调试日志 (可选)
```

## 8. 性能考量

### 8.1 优化策略

- **异步IO**: 使用aiohttp进行并发请求
- **批处理**: 大量文献分批处理
- **缓存**: 减少重复API调用
- **流式输出**: AI响应流式显示

### 8.2 资源限制

| 资源 | 限制 | 说明 |
|------|------|------|
| 并发请求 | 10 | PubMed API限制 |
| 内存使用 | 视数据量 | 大型检索需要更多内存 |
| 磁盘缓存 | 500MB | 可配置 |

## 9. 安全考量

### 9.1 敏感数据

- **API密钥**: 存储在 `ai_config.yaml`，不应提交到版本控制
- **用户数据**: 本地处理，不上传到第三方

### 9.2 建议

- 使用环境变量存储API密钥
- 定期轮换API密钥
- 检查 `.gitignore` 确保敏感文件不被提交

## 10. 扩展点

### 10.1 添加新的AI服务

1. 继承 `AIClient` 基类
2. 实现 `generate()` 和 `generate_stream()` 方法
3. 在 `ai_config.yaml` 中添加配置

### 10.2 添加新的文献源

1. 创建新的搜索模块 (类似 `pubmed_search.py`)
2. 实现统一的搜索接口
3. 在核心系统中集成

### 10.3 添加新的导出格式

1. 在 `medical_review_generator.py` 中添加导出方法
2. 注册到导出格式列表

---
*文档生成时间: 2026-02-01*
*BMAD Document Project Workflow v1.2.0*
