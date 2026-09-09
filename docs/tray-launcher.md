# Windows 托盘启动程序

在项目根目录双击 `文献综述工作台.exe`。程序调用 `start.ps1` 完成环境检测，日志显示在启动程序窗口。服务就绪后自动打开浏览器。

- 最小化或点击窗口关闭按钮：收起到系统托盘，服务继续运行。
- 双击托盘图标：恢复日志窗口。
- 右键托盘图标：打开网页、显示日志或退出并停止服务。
- 退出需确认，将结束本次启动的服务和任务；未完成任务下次启动时按中断处理。
- 端口已被占用时提示启动失败，不接管其他服务。

EXE 必须与 `start.ps1`、`src` 等项目文件放在一起，并非内嵌 Python 的独立安装包。使用 Windows 自带 .NET Framework，不新增系统依赖。

构建命令：`powershell -NoProfile -ExecutionPolicy Bypass -File tools/build-tray.ps1`。

`--self-test` 测试模式验证启动、日志转发、父子进程回收，结果保存到 `logs/tray-self-test.txt`。该模式不运行真实检索任务。
