# 智能文献综述系统 - 源码树分析

## 目录结构

```
Intelligent-Literature-Review-main/
│
├── 📁 src/                           # 核心源代码目录
│   │
│   ├── 🚀 入口模块
│   │   ├── start.py                  # 交互式启动入口 (41KB)
│   │   │                             # - 引导式用户交互
│   │   │                             # - 系统初始化和配置加载
│   │   │                             # - 错误处理和用户提示
│   │   │
│   │   ├── intelligent_literature_system.py  # 核心系统模块 (90KB)
│   │   │                             # - 主要业务逻辑协调
│   │   │                             # - 完整工作流管理
│   │   │                             # - 命令行参数解析
│   │   │
│   │   └── cli.py                    # 命令行界面 (23KB)
│   │                                 # - CLI命令定义
│   │                                 # - 参数处理
│   │
│   ├── 🤖 AI服务层
│   │   ├── ai_client.py              # AI服务客户端 (72KB)
│   │   │                             # - OpenAI API集成
│   │   │                             # - Google Gemini API集成
│   │   │                             # - 流式输出支持
│   │   │                             # - 重试和错误处理
│   │   │
│   │   └── intent_analyzer.py        # 用户意图分析 (50KB)
│   │                                 # - 自然语言理解
│   │                                 # - 检索词生成
│   │                                 # - 搜索策略推荐
│   │
│   ├── 🔍 文献检索层
│   │   ├── pubmed_search.py          # PubMed文献检索 (44KB)
│   │   │                             # - E-utilities API集成
│   │   │                             # - 批量异步检索
│   │   │                             # - 结果缓存
│   │   │
│   │   ├── literature_filter.py      # 文献筛选模块 (51KB)
│   │   │                             # - 中科院分区筛选
│   │   │                             # - JCR分区筛选
│   │   │                             # - 影响因子过滤
│   │   │
│   │   └── smart_literature_search.py # 智能文献搜索 (32KB)
│   │                                 # - 高级搜索功能
│   │                                 # - 搜索优化
│   │
│   ├── 📝 综述生成层
│   │   ├── review_outline_generator.py # 综述大纲生成 (37KB)
│   │   │                             # - 文献摘要分析
│   │   │                             # - 结构化大纲生成
│   │   │                             # - 主题聚类
│   │   │
│   │   └── medical_review_generator.py # 医学综述生成 (44KB)
│   │                                 # - 完整综述撰写
│   │                                 # - 引用格式化
│   │                                 # - 多格式导出
│   │
│   ├── 📊 数据处理层
│   │   ├── data_processor.py         # 数据处理模块 (33KB)
│   │   │                             # - 期刊数据加载
│   │   │                             # - 数据清洗转换
│   │   │                             # - 结果格式化
│   │   │
│   │   └── prompts_manager.py        # 提示词管理 (11KB)
│   │                                 # - 提示词模板加载
│   │                                 # - 动态提示词构建
│   │
│   ├── 🛠️ 基础设施层
│   │   ├── shared_config.py          # 共享配置管理 (10KB) 🆕
│   │   │                             # - 单例配置管理器
│   │   │                             # - YAML配置加载
│   │   │                             # - AI模型配置
│   │   │
│   │   ├── exceptions.py             # 统一异常处理 (8KB) 🆕
│   │   │                             # - 异常类层次结构
│   │   │                             # - 错误分类
│   │   │
│   │   ├── advanced_cli.py           # 高级CLI功能 (51KB)
│   │   │                             # - 高级交互模式
│   │   │                             # - 批处理支持
│   │   │
│   │   └── setup_pandoc_portable.py  # Pandoc安装工具 (10KB)
│   │                                 # - 自动下载安装
│   │                                 # - 路径配置
│   │
│   └── __init__.py                   # 包初始化
│
├── 📁 data/                          # 期刊评级数据
│   ├── zky.csv                       # 中科院分区原始数据
│   ├── jcr.csv                       # JCR分区原始数据
│   ├── processed_zky_data.csv        # 处理后的中科院数据
│   └── processed_jcr_data.csv        # 处理后的JCR数据
│
├── 📁 prompts/                       # 提示词配置
│   └── prompts_config.yaml           # AI提示词模板配置
│
├── 📁 tools/                         # 工具目录
│   └── pandoc/                       # Pandoc便携版
│
├── 📁 cache/                         # 通用缓存
├── 📁 pubmed_cache/                  # PubMed检索缓存
├── 📁 logs/                          # 运行日志
├── 📁 docs/                          # 生成的文档
│
├── 📄 配置文件
│   ├── ai_config.yaml                # AI服务配置
│   ├── system_config.yaml            # 系统配置 🆕
│   └── requirements.txt              # Python依赖
│
├── 📄 启动脚本
│   ├── start.sh                      # Linux/Mac启动
│   ├── start.ps1                     # PowerShell启动
│   └── start for win11.bat           # Windows启动
│
├── 📄 README.md                      # 项目说明
└── 📄 LICENSE                        # 许可证
```

## 关键目录说明

### src/ - 源代码目录

核心模块分为5个层次：

| 层次 | 模块 | 职责 |
|------|------|------|
| **入口层** | start.py, intelligent_literature_system.py, cli.py | 用户交互、命令解析 |
| **AI服务层** | ai_client.py, intent_analyzer.py | AI模型调用、意图分析 |
| **检索层** | pubmed_search.py, literature_filter.py, smart_literature_search.py | 文献检索和筛选 |
| **生成层** | review_outline_generator.py, medical_review_generator.py | 大纲和综述生成 |
| **基础设施层** | shared_config.py, exceptions.py, data_processor.py, prompts_manager.py | 配置、异常、数据处理 |

### data/ - 数据目录

| 文件 | 说明 | 用途 |
|------|------|------|
| zky.csv | 中科院分区数据 | 期刊分区筛选 |
| jcr.csv | JCR分区数据 | 期刊分区筛选 |
| processed_*.csv | 预处理数据 | 加速数据加载 |

### prompts/ - 提示词目录

包含AI模型调用的提示词模板，用于：
- 意图分析
- 检索词生成
- 大纲生成
- 综述撰写

## 模块依赖关系

```
start.py / cli.py
       │
       ▼
intelligent_literature_system.py ─────────────────┐
       │                                           │
       ├─────────────────┬─────────────────┐      │
       ▼                 ▼                 ▼      │
intent_analyzer.py  pubmed_search.py  literature_filter.py
       │                 │                 │      │
       └─────────────────┴─────────────────┘      │
                         │                         │
                         ▼                         │
            review_outline_generator.py            │
                         │                         │
                         ▼                         │
            medical_review_generator.py            │
                         │                         │
                         ▼                         │
                    导出结果                       │
                                                   │
共享基础设施 ◄─────────────────────────────────────┘
├── ai_client.py (AI服务)
├── data_processor.py (数据处理)
├── prompts_manager.py (提示词)
├── shared_config.py (配置管理)
└── exceptions.py (异常处理)
```

## 代码统计

| 类别 | 文件数 | 总大小 |
|------|--------|--------|
| Python源文件 | 17 | ~600KB |
| 配置文件 | 3 | ~15KB |
| 数据文件 | 4 | 变化 |
| 启动脚本 | 3 | ~50KB |

## 关键入口点

### 1. 交互式入口 (推荐)

```bash
python src/start.py
```

引导用户完成：
1. 输入检索需求
2. 确认检索词
3. 选择筛选条件
4. 生成综述

### 2. 命令行入口

```bash
python src/intelligent_literature_system.py --query "检索需求" --max-results 100
```

支持参数：
- `--query`: 检索需求
- `--max-results`: 最大结果数
- `--non-interactive`: 非交互模式
- `--debug`: 调试模式

### 3. CLI模块

```bash
python src/cli.py [命令] [选项]
```

---
*文档生成时间: 2026-02-01*
*BMAD Document Project Workflow v1.2.0*
