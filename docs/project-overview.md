# 智能文献综述系统 - 项目概述

## 项目信息

| 属性 | 值 |
|------|-----|
| **项目名称** | Intelligent Literature Review System |
| **项目类型** | CLI + Data Pipeline (命令行工具 + 数据处理管道) |
| **主要语言** | Python 3.8+ |
| **架构模式** | 分层管道架构 (Layered Pipeline Architecture) |
| **仓库类型** | Monolith (单体应用) |

## 项目简介

基于AI大模型的医学文献检索与综述自动生成系统，支持PubMed文献检索、期刊质量筛选、综述大纲生成和完整综述文章撰写。

## 核心功能

1. **智能意图分析**: 基于AI分析用户自然语言输入，自动生成PubMed检索词
2. **PubMed文献检索**: 支持批量异步检索，内置缓存机制
3. **期刊质量筛选**: 支持中科院分区、JCR分区、影响因子多维度筛选
4. **综述大纲生成**: AI自动分析文献摘要，生成结构化综述大纲
5. **综述文章撰写**: 基于大纲和文献自动生成完整医学综述
6. **多格式导出**: 支持Markdown、CSV、JSON、BibTeX、DOCX格式

## 技术栈

### 核心依赖

| 类别 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 编程语言 | Python | 3.8+ | 核心开发语言 |
| 数据处理 | pandas | >=2.0.0 | 数据分析和处理 |
| 数据处理 | numpy | >=1.24.0 | 数值计算 |
| HTTP客户端 | requests | >=2.28.0 | 同步HTTP请求 |
| 异步HTTP | aiohttp | >=3.8.0 | 异步HTTP请求 |
| 配置管理 | PyYAML | >=6.0 | YAML配置解析 |
| XML解析 | lxml | >=4.9.0 | PubMed XML解析 |
| 系统监控 | psutil | >=5.9.0 | 系统资源监控 |

### 外部集成

| 集成目标 | 类型 | 说明 |
|----------|------|------|
| PubMed E-utilities | REST API | NCBI文献检索服务 |
| OpenAI API | REST API | GPT模型服务 |
| Google Gemini API | REST API | Gemini模型服务 |
| 兼容OpenAI的服务 | REST API | DeepSeek、通义千问等 |

## 项目结构

```
Intelligent-Literature-Review-main/
├── src/                              # 核心源代码 (17个模块)
│   ├── start.py                      # 交互式启动入口
│   ├── intelligent_literature_system.py  # 核心系统模块
│   ├── ai_client.py                  # AI服务客户端
│   ├── intent_analyzer.py            # 用户意图分析
│   ├── pubmed_search.py              # PubMed文献检索
│   ├── literature_filter.py          # 文献筛选模块
│   ├── review_outline_generator.py   # 综述大纲生成
│   ├── medical_review_generator.py   # 医学综述生成
│   ├── shared_config.py              # 共享配置管理
│   └── exceptions.py                 # 统一异常处理
├── data/                             # 期刊评级数据
├── prompts/                          # AI提示词配置
├── cache/                            # 缓存目录
└── docs/                             # 文档目录
```

## 入口点

| 入口 | 文件 | 说明 |
|------|------|------|
| 交互式入口 | `src/start.py` | 引导式交互操作 |
| 核心系统 | `src/intelligent_literature_system.py` | 完整系统功能 |
| 命令行 | `src/cli.py` | 命令行接口 |

## 数据流

```
用户输入 → 意图分析 → PubMed检索 → 文献筛选 → 大纲生成 → 综述撰写 → 导出
   │           │            │           │           │           │
   │     AI分析生成     批量异步     分区/IF    AI结构化    AI生成
   │      检索词        检索        筛选        大纲        正文
   ▼           ▼            ▼           ▼           ▼           ▼
intent_   pubmed_     literature_  review_    medical_    多格式
analyzer  search      filter       outline    review      导出
```

## 配置文件

| 文件 | 说明 |
|------|------|
| `ai_config.yaml` | AI服务配置（API密钥、端点） |
| `system_config.yaml` | 系统配置（缓存、批处理、超时） |
| `prompts/prompts_config.yaml` | AI提示词模板 |

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置AI服务
# 编辑 ai_config.yaml

# 3. 运行系统
python src/start.py
```

## 相关文档

- [源码树分析](./source-tree-analysis.md)
- [架构文档](./architecture.md) _(待生成)_
- [开发指南](./development-guide.md) _(待生成)_

---
*文档生成时间: 2026-02-01*
*BMAD Document Project Workflow v1.2.0*
