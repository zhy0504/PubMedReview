# 智能文献综述系统 (Intelligent Literature Review System)

基于AI大模型的医学文献检索与综述自动生成系统，支持PubMed文献检索、期刊质量筛选、综述大纲生成和完整综述文章撰写。

## ✨ 功能特性

- **智能意图分析**: 基于AI分析用户自然语言输入，自动生成PubMed检索词
- **PubMed文献检索**: 支持批量异步检索，内置缓存机制
- **期刊质量筛选**: 支持中科院分区、JCR分区、影响因子多维度筛选
- **综述大纲生成**: AI自动分析文献摘要，生成结构化综述大纲
- **综述文章撰写**: 基于大纲和文献自动生成完整医学综述
- **多格式导出**: 支持Markdown、CSV、JSON、BibTeX、DOCX格式

## 📋 系统要求

- Python 3.8+
- 网络连接（用于PubMed API和AI服务）
- 可选：Pandoc（用于DOCX导出）

## 🚀 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置AI服务

复制 `.env.example` 为 `.env` 并配置您的API密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# OpenAI配置
OPENAI_API_KEY=sk-your_actual_key_here
OPENAI_BASE_URL=https://api.openai.com/
OPENAI_MODEL=gpt-4-turbo

# 默认服务
DEFAULT_AI_SERVICE=openai
```

### 3. 运行系统

```bash
# 交互式运行（推荐）
python src/start.py

# 或直接运行主系统
python src/intelligent_literature_system.py
```

## 📁 项目结构

```
Intelligent-Literature-Review-main/
├── src/                          # 源代码目录
│   ├── start.py                  # 交互式启动入口
│   ├── intelligent_literature_system.py  # 核心系统
│   ├── ai_client.py              # AI客户端（OpenAI/Gemini）
│   ├── ai_config.py              # AI服务配置管理
│   ├── intent_analyzer.py        # 用户意图分析
│   ├── pubmed_search.py          # PubMed检索模块
│   ├── literature_filter.py      # 文献筛选模块
│   ├── data_processor.py         # 数据处理模块
│   ├── review_outline_generator.py   # 大纲生成器
│   ├── medical_review_generator.py   # 综述生成器
│   ├── prompts_manager.py        # 提示词管理
│   ├── cache.py                  # 缓存模块
│   ├── logger.py                 # 日志模块
│   └── exceptions.py             # 自定义异常
├── tests/                        # 单元测试
│   ├── conftest.py               # 测试配置和fixtures
│   ├── test_cache.py             # 缓存模块测试
│   └── test_pubmed_search.py     # PubMed搜索测试
├── data/                         # 数据文件
│   ├── zky.csv                   # 中科院分区数据
│   └── jcr.csv                   # JCR分区数据
├── prompts/                      # 提示词配置
│   └── prompts_config.yaml       # 提示词模板
├── tools/                        # 工具目录
│   └── pandoc/                   # Pandoc便携版
├── .env.example                  # AI服务配置模板
├── requirements.txt              # Python依赖
└── README.md                     # 项目说明
```

## 🔧 配置说明

### AI配置 (.env)

| 环境变量 | 说明 | 示例 |
|----------|------|------|
| `OPENAI_API_KEY` | OpenAI API密钥 | `sk-xxx...` |
| `OPENAI_BASE_URL` | API端点 | `https://api.openai.com/` |
| `OPENAI_MODEL` | 默认模型 | `gpt-4-turbo` |
| `DEFAULT_AI_SERVICE` | 默认服务 | `openai` |

支持的服务: `openai`, `openai_proxy`, `gemini`, `deepseek`, `moonshot`, `ollama`

### 系统配置

系统运行时会自动创建以下目录：

- `综述大纲/` - 生成的综述大纲
- `综述文章/` - 生成的综述文章
- `检索结果/` - 文献检索结果
- `.cache/` - 缓存文件

## 📖 使用示例

### 命令行模式

```bash
# 指定检索需求
python src/intelligent_literature_system.py --query "糖尿病治疗近5年高影响因子研究"

# 指定最大结果数
python src/intelligent_literature_system.py --query "COVID-19疫苗效果" --max-results 200

# 非交互模式
python src/intelligent_literature_system.py --query "癌症免疫治疗" --non-interactive
```

### 交互式模式

```bash
python src/start.py
```

系统将引导您：
1. 输入检索需求（如："糖尿病治疗近5年高影响因子研究"）
2. 确认AI生成的检索词
3. 选择筛选条件（分区、影响因子等）
4. 生成综述大纲和文章

## 🔌 支持的AI服务

| 服务 | API类型 | 说明 |
|------|---------|------|
| OpenAI | `openai` | GPT-4, GPT-3.5-Turbo |
| Google Gemini | `gemini` | Gemini Pro, Gemini 2.5 |
| 兼容OpenAI的服务 | `openai` | DeepSeek, 通义千问等 |

## ⚠️ 注意事项

1. **API配额**: 请注意AI服务的API调用配额和费用
2. **网络要求**: 需要访问PubMed E-utilities API和AI服务
3. **数据更新**: 期刊分区数据需要定期更新以保证准确性
4. **文献引用**: 生成的综述仅供参考，请核实引用准确性

## 📝 更新日志

### v2.0
- 新增流式输出支持
- 优化缓存机制
- 支持多种AI服务
- 增强错误处理

## 🧪 测试

运行单元测试：

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_pubmed_search.py -v

# 运行测试并生成覆盖率报告
pytest tests/ --cov=src --cov-report=html
```

## 📄 许可证

本项目仅供学习和研究使用。

## 🤝 贡献

欢迎提交Issue和Pull Request。
