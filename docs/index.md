# 智能文献综述系统 - 文档索引

## 项目概览

| 属性 | 值 |
|------|-----|
| **类型** | Monolith (单体应用) |
| **主要语言** | Python 3.8+ |
| **架构模式** | 分层管道架构 (CLI + Data Pipeline) |

## 快速参考

- **技术栈**: Python + pandas + aiohttp + PyYAML
- **入口点**: `src/start.py` (交互式) / `src/intelligent_literature_system.py` (命令行)
- **架构模式**: 分层管道架构

## 生成的文档

### 核心文档

- [项目概述](./project-overview.md) - 项目简介、技术栈、快速开始
- [架构文档](./architecture.md) - 系统架构、模块设计、外部集成
- [源码树分析](./source-tree-analysis.md) - 目录结构、模块依赖关系
- [开发指南](./development-guide.md) - 开发环境、代码规范、扩展指南

### 现有文档

- [README](../README.md) - 项目说明文档

## 快速开始

### 安装

```bash
# 创建虚拟环境
python -m venv venv

# 激活环境 (Windows)
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 配置

编辑 `ai_config.yaml` 配置您的 AI 服务:

```yaml
configs:
  - name: "your_config"
    api_type: "openai"  # 或 "gemini"
    api_key: "your-api-key"
```

### 运行

```bash
# 交互式模式 (推荐)
python src/start.py

# 命令行模式
python src/intelligent_literature_system.py --query "您的检索需求"
```

## 项目结构概览

```
├── src/                    # 源代码 (17个模块)
│   ├── start.py            # 交互式入口
│   ├── intelligent_literature_system.py  # 核心系统
│   ├── ai_client.py        # AI服务客户端
│   ├── pubmed_search.py    # PubMed检索
│   └── ...
├── data/                   # 期刊数据
├── prompts/                # AI提示词配置
├── docs/                   # 本文档目录
├── ai_config.yaml          # AI服务配置
└── requirements.txt        # Python依赖
```

## 关键模块

| 模块 | 职责 | 文件 |
|------|------|------|
| AI客户端 | OpenAI/Gemini集成 | `ai_client.py` |
| 意图分析 | 自然语言 → 检索词 | `intent_analyzer.py` |
| 文献检索 | PubMed API调用 | `pubmed_search.py` |
| 文献筛选 | 分区/IF筛选 | `literature_filter.py` |
| 大纲生成 | 综述大纲 | `review_outline_generator.py` |
| 综述生成 | 完整综述 | `medical_review_generator.py` |

## 配置文件

| 文件 | 说明 |
|------|------|
| `ai_config.yaml` | AI服务配置（API密钥、端点） |
| `system_config.yaml` | 系统配置（缓存、超时、重试） |
| `prompts/prompts_config.yaml` | AI提示词模板 |

## 外部集成

| 服务 | 类型 | 说明 |
|------|------|------|
| PubMed E-utilities | REST API | 文献检索 |
| OpenAI API | REST API | GPT模型 |
| Google Gemini API | REST API | Gemini模型 |

---

## 文档信息

- **生成时间**: 2026-02-01
- **工作流版本**: BMAD Document Project v1.2.0
- **扫描级别**: Quick Scan
- **项目类型**: CLI + Data Pipeline

## 下一步

1. 阅读 [架构文档](./architecture.md) 了解系统设计
2. 参考 [开发指南](./development-guide.md) 进行开发
3. 根据需要创建 PRD 规划新功能

---
*此文档由 BMAD Document Project Workflow 自动生成*
