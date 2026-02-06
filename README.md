# 智能文献综述系统 (Intelligent Literature Review System)

基于大模型的医学文献检索与综述生成工具，覆盖从检索需求输入、PubMed 拉取、期刊质量筛选，到综述大纲与综述正文生成的完整流程。

## 功能概览

- 智能意图分析：从自然语言需求生成检索策略。
- 文献检索：对接 PubMed，支持批量获取与缓存。
- 文献筛选：支持中科院分区、JCR 分区、影响因子等条件筛选。
- 大纲生成：基于筛选后文献自动生成结构化综述大纲。
- 文章生成：根据大纲和文献生成综述正文。
- 多格式输出：支持 JSON、CSV、Markdown、DOCX（取决于配置与环境）。

## 运行要求

- Python 3.8 及以上。
- 可访问 PubMed 和所选 AI 服务。
- 可选：Pandoc（用于更稳定的 DOCX 导出）。

## 快速开始

### 1) 安装依赖

```bash
python -m venv venv

# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 2) 配置 AI 服务

```bash
# Linux / macOS
cp .env.example .env
# Windows PowerShell
copy .env.example .env
```

编辑 `.env`，至少填好默认服务对应的密钥，例如：

```env
OPENAI_API_KEY=sk-your-real-key
OPENAI_BASE_URL=https://api.openai.com/
OPENAI_MODEL=gpt-4-turbo
DEFAULT_AI_SERVICE=openai
```

### 3) 准备数据文件

确保 `data/` 下存在以下文件之一：

- 预处理文件：`processed_zky_data.csv`、`processed_jcr_data.csv`
- 或原始文件：`zky.csv`、`jcr.csv`（系统可自动处理生成预处理文件）

### 4) 启动系统（推荐）

```bash
python src/start.py
```

如果你是 Windows/macOS 技术新手，可直接使用脚本启动：

- Windows：双击 `start for win11.bat` 或在 PowerShell 执行 `.\start.ps1`
- macOS / Linux：执行 `bash start.sh`

## 文档导航

- 用户使用手册（操作重点）：`docs/user-manual.md`
- 文档索引：`docs/index.md`
- 架构说明：`docs/architecture.md`

## 常用入口

| 入口 | 命令 | 说明 |
|---|---|---|
| 启动器（推荐） | `python src/start.py` | 自动检查环境并进入交互菜单 |
| 启动主流程 | `python src/start.py start` | 直接启动文献综述主流程 |
| 状态检查 | `python src/start.py status` | 查看系统状态 |
| 仅检查环境 | `python src/start.py --check-only` | 仅做环境检查，不启动业务流程 |
| 高级管理 | `python src/start.py manage` | 进入高级 CLI |
| 核心 CLI 直连 | `python src/intelligent_literature_system.py -q "主题"` | 直接调用主程序 |

## 核心命令速查

### `src/start.py`

```bash
python src/start.py --help
python src/start.py --check-only
python src/start.py --check-only --force-check
python src/start.py start
python src/start.py status
python src/start.py manage
```

### `src/intelligent_literature_system.py`

```bash
python src/intelligent_literature_system.py -q "糖尿病治疗近5年进展"
python src/intelligent_literature_system.py -q "COVID-19疫苗效果" --max-results 100 --target 30
python src/intelligent_literature_system.py -q "肿瘤免疫治疗" --ai-config gemini --non-interactive-ai
python src/intelligent_literature_system.py --no-cache --no-state --debug
python src/intelligent_literature_system.py --clear-cache
```

### `src/cli.py`（基础管理 CLI）

```bash
python src/cli.py --check
python src/cli.py --setup-venv
python src/cli.py --install-deps
python src/cli.py --setup-ai
python src/cli.py --setup-prompts
python src/cli.py --start --mode interactive
```

### `src/advanced_cli.py`（高级管理 CLI）

```bash
python src/advanced_cli.py -i
python src/advanced_cli.py --basic
```

## 输出目录说明

默认输出位于 `output/`：

- `output/文献检索结果/`：检索与筛选结果（CSV / JSON）。
- `output/综述大纲/`：综述大纲（MD，按配置可导出 DOCX）。
- `output/综述文章/`：综述正文（MD / DOCX，取决于 `system_config.yaml`）。
- `output/综述AI返回原始数据/`：部分原始响应留档（若启用）。

## 配置说明

### `.env`（AI 服务）

常用配置项：

- `DEFAULT_AI_SERVICE`：默认服务，如 `openai`、`gemini`、`deepseek`、`moonshot`、`openai_proxy`、`ollama`
- `OPENAI_*`、`GEMINI_*`、`DEEPSEEK_*`、`MOONSHOT_*`、`OLLAMA_*`：各服务的密钥、URL、模型
- `AI_REQUEST_TIMEOUT`、`AI_MAX_RETRIES`：请求超时与重试次数

### `system_config.yaml`（系统行为）

常见可调项：

- 缓存大小和 TTL
- 批处理大小与并发
- 重试和超时策略
- 输出格式（`md` / `docx` / `both`）

## 测试

```bash
python -m pytest -q
python -m pytest --cov=src --cov-report=term -q
```

## 注意事项

1. 使用真实 API Key，不要提交 `.env` 到仓库。
2. 文献综述结果需人工复核，尤其是结论与引用准确性。
3. 生产使用建议固定模型与参数，并记录生成版本信息。
