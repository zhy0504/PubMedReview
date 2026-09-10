# PubMedReview

**PubMed 文献综述工作台**

基于 Intelligent-Literature-Review 改造的本地 Web 工作台，用于 PubMed 检索、期刊条件筛选、综述大纲和正文生成。原项目作者及 MIT 许可证保留在 LICENSE 中。

## 工作流程

1. 启动后进入系统状态页，查看环境、Pandoc、提示词和期刊数据。
2. 在配置页保存 AI 服务地址、API Key、模型和各模块思考强度；可从服务接口获取模型列表。
3. 输入研究主题、年份、影响因子及分区条件，提交检索。
4. 查看目标篇数与实际筛选结果，调整条件或点击“开始综述”。未确认不生成综述。
5. 在历史任务中查看文献和成果文件；支持选择记录后统一清理。

支持 OpenAI Chat Completions 与 OpenAI Responses 两种兼容协议，并内置常见服务预设：OpenAI、OpenAI 兼容代理、DeepSeek、智谱 GLM、Kimi、通义千问、豆包/火山方舟、SiliconFlow、OpenRouter、Groq、Together AI、Mistral、Ollama 和 LM Studio；另提供 Gemini 原生接口与 Claude Messages API。AI 用于意图分析、大纲及正文生成；期刊条件由程序筛选，不由 AI 判断。各模块提示词独立配置。

## 快速启动

需要 Python 3.10 或更高版本、可访问 PubMed 和所配置的 AI 服务。本项目当前在 Windows / Python 3.14.6 上执行测试，其他平台未完成真实启动验收。

### Windows

推荐直接双击 `start for win11.bat`。脚本会先检查 Python、`.venv` 和 `requirements.txt` 中的依赖：已满足版本要求时跳过下载，只有缺失或版本不符合时才安装，并按镜像响应时间排序尝试下载。启动完成后会自动打开本机 Web 工作台。

可选托盘启动器：在 PowerShell 执行以下命令构建，再双击项目根目录的 `文献综述工作台.exe`：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/build-tray.ps1
```

托盘版不是独立的 Python 打包程序，必须和 `start.ps1`、`src/`、`tools/`、`requirements.txt` 等项目文件放在同一根目录。启动窗口提供以下入口：

- `检测环境`：检查 Python、虚拟环境、依赖、Pandoc、数据目录、提示词和三份期刊 CSV。
- `修复环境/依赖`：创建缺失的 `.venv`，并只安装缺失或不兼容的依赖；不会删除项目文件。
- `安装 Pandoc` / `更新 Pandoc`：分别安装或更新 Pandoc，完成后可重新检测。
- `打开 Web 工作台`：打开本机控制台；启动完成后会自动进入系统状态页。

托盘窗口会转发启动和环境操作日志。关闭窗口只隐藏界面；需要停止后台服务时，请使用托盘菜单的 `退出`。旧版 EXE 构建时会保留 `.bak` 恢复副本。更多说明见 `docs/tray-launcher.md`。

也可以直接运行环境管理器：

```powershell
python tools/environment_manager.py --status
python tools/environment_manager.py --repair
python tools/environment_manager.py --pandoc
python tools/environment_manager.py --update-pandoc
```

这些操作只作用于当前项目目录；Python 本身缺失时，需要先由系统安装 Python 3.10 或更高版本。

### Linux / macOS

```bash
bash start.sh
```

默认访问 `http://127.0.0.1:8765`。程序仅供本机使用，不是可直接部署到公网的多用户服务。

## 配置与数据

在 Web 配置页先选择 AI 服务，再保存地址、密钥和模型；也可以将 `.env.example` 复制为 `.env` 后填写。模型列表按钮会调用当前服务的模型端点；服务不提供模型列表时可手动填写模型，不会阻止运行。OpenAI 兼容服务按其完整基础地址工作：例如 DeepSeek 使用 `https://api.deepseek.com`，智谱使用 `https://open.bigmodel.cn/api/paas/v4`，火山方舟使用 `https://ark.cn-beijing.volces.com/api/v3`。Gemini 和 Claude 使用各自原生协议。不要将真实密钥提交到 Git。思考强度、Responses 和其他参数是否可用取决于服务及具体模型；工作台会阻止已知不支持的协议组合。提交任务可能产生 AI 服务费用。

期刊文件放在 `data/` 下：

| 文件 | 用途 |
|---|---|
| FQBJCR2025-UTF8.csv | 中科院2025大类分区 |
| JCR2025-UTF8.csv | JCR2025影响因子及第一学科分区 |
| XR2026-UTF8.csv | 新锐2026大类分区 |

程序只检测文件是否存在，不自动更新期刊表。多项分区条件按交集筛选；“3区及以上”表示1–3区。指定分区后，缺少该分区数据的期刊不会入选。期刊影响因子不代表单篇文章质量。

这些 CSV 来源于此前使用的 ShowJCR 数据快照，不属于本项目原创数据。对外分发前须核实数据许可；源代码发布准备目录默认不包含期刊数据，需自行放入有权使用的文件。

## 文件与隐私

- `src/`：核心处理与 Web 工作台。
- `prompts/`：三个模块的提示词。
- `tools/`：环境检测与修复、依赖镜像选择、Pandoc 管理和 Windows 托盘构建工具。
- `tests/`：自动化回归测试。
- `workspace_data/`：SQLite 历史、偏好和任务成果副本，仅本地保留。
- `output/`、`cache/`、`pubmed_cache/`、`logs/`：运行数据，不上传。
- `.env`、虚拟环境、旧备份和测试临时文件：不上传。

历史成果可能包含研究主题、提示词和 AI 返回内容。备份历史前先停止服务，再复制整个 workspace_data 目录，避免遗漏 SQLite 附属文件。

## 开发验证

使用项目虚拟环境安装 requirements.txt 后，在项目根目录执行：

```bash
python -m pytest -q
```

Windows 托盘启动器可使用以下命令做本地自检：

```powershell
.\文献综述工作台.exe --self-test
```

最近一次 Windows 验证通过 `201 passed, 1 skipped`，并已验证托盘启动、日志转发、环境检测以及关闭启动器后后台服务进程能够退出。该结果不代表已完成所有操作系统和第三方 AI 服务的端到端验收。

测试通过不等于完成真实付费 AI 服务、所有操作系统或全新环境的端到端验收。发布前检查及已知限制见 `docs/release-audit.md`。

## 研究使用边界

结果是辅助检索和写作材料，并非自动完成的系统综述。候选数受检索预算限制，标题摘要相关性、引用准确性和研究结论仍需人工核验；不得将期刊筛选结果直接视为完整纳排审查。
