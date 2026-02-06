# 用户使用手册（操作指南）

本手册聚焦“怎么操作程序”，默认你已经在项目根目录下执行命令。

## 1. 使用前准备

### 1.1 环境准备

- Python 3.8+
- 已安装依赖：`pip install -r requirements.txt`
- 已配置 `.env`（至少有一个可用 AI 服务）

### 1.2 数据准备

满足任一条件即可：

- `data/processed_zky_data.csv` 和 `data/processed_jcr_data.csv` 已存在
- 或 `data/zky.csv` 和 `data/jcr.csv` 已存在（系统可自动预处理）

## 2. 推荐启动方式（start.py）

### 2.1 直接进入交互流程

```bash
python src/start.py
```

程序会先做环境检查，然后进入菜单。

### 2.2 脚本启动（Windows / macOS / Linux 小白版）

如果你不熟悉命令行，优先用项目自带脚本启动。

Windows：

- 图形方式（推荐）：双击 `start for win11.bat`
- 终端方式（PowerShell）：`.\start.ps1`

macOS / Linux：

```bash
bash start.sh
```

如果提示 `Permission denied`，先执行：

```bash
chmod +x start.sh
./start.sh
```

补充说明：

- 脚本会自动做 Python 环境检查、虚拟环境创建、依赖检查，然后调用主启动器。
- 第一次启动可能较慢（需要创建 `venv` 和安装依赖）。
- 脚本方式失败时，回退到命令：`python src/start.py`

### 2.3 给脚本传参数（可选）

Windows PowerShell：

```powershell
.\start.ps1 --check-only
.\start.ps1 start
```

macOS / Linux：

```bash
bash start.sh --check-only
bash start.sh start
```

### 2.4 快速命令

```bash
python src/start.py --check-only
python src/start.py --check-only --force-check
python src/start.py status
python src/start.py start
python src/start.py manage
```

命令说明：

- `--check-only`：只检查环境，不启动业务流程。
- `--force-check`：忽略缓存，强制重新检查。
- `status`：查看系统状态。
- `start`：直接启动主流程。
- `manage`：进入高级管理界面。

## 3. 交互式主流程操作

入口：`python src/start.py` 或 `python src/start.py start`

典型步骤：

1. 输入检索需求（自然语言）。
2. 系统分析检索意图并构建检索策略。
3. 拉取 PubMed 文献并做质量筛选。
4. 显示筛选结果，并询问是否继续生成综述大纲和文章。
5. 生成综述大纲。
6. 生成综述文章（按配置导出 MD / DOCX）。

## 4. 直接命令行运行主程序

入口：`src/intelligent_literature_system.py`

### 4.1 常用示例

```bash
python src/intelligent_literature_system.py -q "糖尿病治疗近5年进展"
python src/intelligent_literature_system.py -q "COVID-19疫苗效果" --max-results 100 --target 30
python src/intelligent_literature_system.py -q "肿瘤免疫治疗" --ai-config gemini --non-interactive-ai
python src/intelligent_literature_system.py --no-cache --no-state --debug
python src/intelligent_literature_system.py --clear-cache
```

### 4.2 关键参数

- `-q, --query`：检索需求。
- `--max-results`：最大检索文献数。
- `--target`：目标筛选文献数。
- `--ai-config`：指定 AI 配置名称（服务名）。
- `--non-interactive-ai`：使用非交互 AI 配置流程。
- `--no-cache`：关闭缓存。
- `--no-state`：关闭状态管理。
- `--debug`：调试模式。
- `--resume`：尝试恢复上次任务。
- `--clear-cache`：清空缓存与状态。

## 5. 基础管理 CLI（cli.py）

入口：`src/cli.py`

### 5.1 常用命令

```bash
python src/cli.py --check
python src/cli.py --setup-venv
python src/cli.py --install-deps
python src/cli.py --upgrade-deps
python src/cli.py --setup-ai
python src/cli.py --setup-prompts
python src/cli.py --start --mode interactive
python src/cli.py --start --mode batch
```

## 6. 高级管理 CLI（advanced_cli.py）

入口：`python src/advanced_cli.py -i`

主菜单功能：

- 系统状态检查
- 虚拟环境管理
- 依赖包管理
- AI 配置管理
- 提示词配置管理
- 项目启动
- 数据管理
- 日志和监控
- 系统工具

适合做日常维护和排障。

## 7. 输出结果查看

默认输出目录：`output/`

- `output/文献检索结果/`：CSV / JSON
- `output/综述大纲/`：MD（可配置 DOCX）
- `output/综述文章/`：MD / DOCX
- `output/综述AI返回原始数据/`：原始响应留档（如果启用）

## 8. 常见操作问题

### 8.1 启动时提示 AI 配置无效

检查 `.env`：

- 默认服务 `DEFAULT_AI_SERVICE` 是否正确
- 对应服务的 API Key 是否为真实值
- Base URL、模型名是否拼写正确

### 8.2 依赖安装到了系统 Python 而不是 venv

优先使用以下方式：

1. 激活虚拟环境后再安装。
2. 或通过 `python src/cli.py --install-deps` 安装。
3. 或通过 `python src/advanced_cli.py -i` 的依赖管理安装。

### 8.3 想在 CI 或非交互终端运行

推荐：

```bash
python src/start.py --check-only
python src/intelligent_literature_system.py -q "你的主题" --non-interactive-ai --no-state
```

## 9. 一条完整操作路径（首次上手）

1. `python -m venv venv`
2. 激活 `venv`
3. `pip install -r requirements.txt`
4. `copy .env.example .env`（或 `cp`）
5. 填写 `.env` 的 API Key
6. 准备 `data/` 下的期刊数据
7. `python src/start.py`
8. 按提示完成检索、筛选、大纲和文章生成
9. 到 `output/` 查看结果文件
