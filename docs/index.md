# 智能文献综述系统 - 文档索引

## 核心文档

- [README](../README.md)：快速上手、命令速查、配置说明。
- [用户使用手册](./user-manual.md)：以程序操作步骤为主的使用指南。
- [项目概览](./project-overview.md)：项目定位、模块总览。
- [架构说明](./architecture.md)：系统架构和模块关系。
- [开发指南](./development-guide.md)：开发与维护相关约定。
- [源码树分析](./source-tree-analysis.md)：目录和模块扫描结果。

## 推荐阅读顺序

1. 先读 `README`，完成环境和配置。
2. 再读 `用户使用手册`，按步骤完成实际操作。
3. 需要二次开发时，再读架构和开发指南。

## 关键入口

- 启动器：`python src/start.py`
- 主程序：`python src/intelligent_literature_system.py`
- 基础管理：`python src/cli.py`
- 高级管理：`python src/advanced_cli.py -i`

## 配置文件

- AI 服务配置：`.env`（从 `.env.example` 复制）
- 系统运行配置：`system_config.yaml`
- 提示词配置：`prompts/prompts_config.yaml`
