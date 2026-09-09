using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

sealed class OwnedProcess : IDisposable {
    [StructLayout(LayoutKind.Sequential)] struct Basic { public long PerProcess, PerJob; public uint Flags; public UIntPtr Min, Max; public uint Active; public UIntPtr Affinity; public uint Priority, Scheduling; }
    [StructLayout(LayoutKind.Sequential)] struct Io { public ulong Read, Write, Other, ReadBytes, WriteBytes, OtherBytes; }
    [StructLayout(LayoutKind.Sequential)] struct Extended { public Basic Basic; public Io Io; public UIntPtr ProcessMemory, JobMemory, PeakProcess, PeakJob; }
    [DllImport("kernel32.dll", SetLastError=true)] static extern IntPtr CreateJobObject(IntPtr attributes, string name);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool SetInformationJobObject(IntPtr job, int type, ref Extended info, uint size);
    [DllImport("kernel32.dll", SetLastError=true)] static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
    IntPtr job;
    public Process Process;
    public OwnedProcess(string root, string command, Action<string> output) {
        job = CreateJobObject(IntPtr.Zero, null);
        var info = new Extended(); info.Basic.Flags = 0x2000;
        if (job == IntPtr.Zero || !SetInformationJobObject(job, 9, ref info, (uint)Marshal.SizeOf(info))) { Dispose(); throw new System.ComponentModel.Win32Exception(); }
        try {
            var start = new ProcessStartInfo(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), @"WindowsPowerShell\v1.0\powershell.exe"));
            string gate = "[Console]::InputEncoding=[Text.Encoding]::UTF8; [Console]::OutputEncoding=[Text.Encoding]::UTF8; $null=[Console]::ReadLine(); " + command;
            start.Arguments = "-NoProfile -ExecutionPolicy Bypass -EncodedCommand " + Convert.ToBase64String(Encoding.Unicode.GetBytes(gate));
            start.WorkingDirectory = root; start.UseShellExecute = false; start.CreateNoWindow = true;
            start.RedirectStandardInput = true; start.RedirectStandardOutput = true; start.RedirectStandardError = true;
            start.StandardOutputEncoding = Encoding.UTF8; start.StandardErrorEncoding = Encoding.UTF8;
            start.EnvironmentVariables["WORKBENCH_TRAY"] = "1";
            Process = new Process(); Process.StartInfo = start; Process.Start();
            if (!AssignProcessToJobObject(job, Process.Handle)) { Process.Kill(); throw new System.ComponentModel.Win32Exception(); }
            Process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs args) { if (args.Data != null) output(args.Data); };
            Process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs args) { if (args.Data != null) output(args.Data); };
            Process.BeginOutputReadLine(); Process.BeginErrorReadLine();
            Process.StandardInput.WriteLine("start"); Process.StandardInput.Close();
        } catch { Dispose(); throw; }
    }
    public void Dispose() { if (job != IntPtr.Zero) { CloseHandle(job); job = IntPtr.Zero; } }
}

sealed class WorkbenchTray : Form {
    readonly TextBox logs = new TextBox();
    readonly NotifyIcon tray = new NotifyIcon();
    readonly System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer();
    OwnedProcess owned;
    bool quitting, ready, probing;
    readonly string root = AppDomain.CurrentDomain.BaseDirectory;
    public WorkbenchTray() {
        Text = "文献综述工作台 · 启动与日志"; Size = new Size(900, 560); MinimumSize = new Size(560, 340);
        Font = new Font("Microsoft YaHei", 10); Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath) ?? SystemIcons.Application;
        logs.Multiline = true; logs.ReadOnly = true; logs.ScrollBars = ScrollBars.Both; logs.Dock = DockStyle.Fill;
        var actions = new FlowLayoutPanel(); actions.Dock = DockStyle.Top; actions.Height = 48;
        AddButton(actions, "打开 Web 工作台", OpenWeb);
        AddButton(actions, "最小化到托盘", delegate { Hide(); });
        AddButton(actions, "退出并停止服务", Quit);
        Controls.Add(logs); Controls.Add(actions);
        tray.Icon = Icon; tray.Text = "文献综述工作台";
        var menu = new ContextMenuStrip();
        menu.Items.Add("打开 Web 工作台", null, delegate { OpenWeb(); });
        menu.Items.Add("显示运行日志", null, delegate { Show(); WindowState = FormWindowState.Normal; Activate(); });
        menu.Items.Add("退出并停止服务", null, delegate { Quit(); });
        tray.ContextMenuStrip = menu; tray.DoubleClick += delegate { Show(); WindowState = FormWindowState.Normal; Activate(); };
        tray.Visible = true;
        Resize += delegate { if (WindowState == FormWindowState.Minimized) Hide(); };
        FormClosing += delegate(object sender, FormClosingEventArgs args) {
            if (!quitting && args.CloseReason == CloseReason.UserClosing) { args.Cancel = true; Hide(); tray.ShowBalloonTip(2000, Text, "已收起到托盘。右键托盘图标可退出并停止服务。", ToolTipIcon.Info); }
        };
        FormClosed += delegate { timer.Stop(); tray.Visible = false; tray.Dispose(); if (owned != null) owned.Dispose(); };
        Shown += delegate { StartService(); };
        timer.Interval = 1000; timer.Tick += delegate { CheckService(); };
    }
    void AddButton(Control parent, string text, Action action) { var button = new Button(); button.Text = text; button.AutoSize = true; button.Click += delegate { action(); }; parent.Controls.Add(button); }
    void Log(string line) {
        if (IsDisposed) return;
        if (InvokeRequired) { try { BeginInvoke(new Action<string>(Log), line); } catch (InvalidOperationException) {} return; }
        if (logs.TextLength > 200000) logs.Text = logs.Text.Substring(logs.TextLength - 100000);
        logs.AppendText(line + Environment.NewLine);
    }
    void StartService() {
        try {
            if (!File.Exists(Path.Combine(root, "start.ps1"))) throw new IOException("请将启动程序放在项目根目录，与 start.ps1 同级。");
            foreach (var endpoint in System.Net.NetworkInformation.IPGlobalProperties.GetIPGlobalProperties().GetActiveTcpListeners())
                if (endpoint.Port == 8765) throw new IOException("8765 端口已被占用。请先关闭旧启动窗口；本程序不会接管或终止其他服务。");
            owned = new OwnedProcess(root, "& './start.ps1'; exit $LASTEXITCODE", Log);
            timer.Start();
        } catch (Exception error) { Log("启动失败：" + error.Message); }
    }
    void CheckService() {
        if (owned == null) return;
        if (owned.Process.HasExited) { timer.Stop(); Log("服务已退出，退出码：" + owned.Process.ExitCode); owned.Dispose(); ready = false; return; }
        if (ready || probing) return;
        probing = true;
        ThreadPool.QueueUserWorkItem(delegate {
            bool ok = false;
            try { var request = (HttpWebRequest)WebRequest.Create("http://127.0.0.1:8765/"); request.Proxy = null; request.Timeout = 800; using (var response = request.GetResponse()) { ok = true; } } catch (WebException) {}
            try { BeginInvoke(new Action(delegate { probing = false; if (ok && !quitting && !owned.Process.HasExited) { ready = true; Log("Web 服务已就绪。"); OpenWeb(); } })); } catch (InvalidOperationException) {}
        });
    }
    void OpenWeb() { if (!ready) { Log("Web 服务尚未就绪，请查看启动日志。"); return; } try { Process.Start(new ProcessStartInfo("http://127.0.0.1:8765") { UseShellExecute = true }); } catch (Exception error) { Log(error.Message); } }
    void Quit() { if (MessageBox.Show("退出将停止本程序启动的服务及运行中的检索/综述任务，是否继续？", "退出确认", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes) return; quitting = true; Close(); }
    [STAThread] static int Main(string[] args) {
        if (args.Length == 1 && args[0] == "--self-test") {
            try {
                int child = 0; var received = new ManualResetEvent(false);
                var runner = new OwnedProcess(AppDomain.CurrentDomain.BaseDirectory, "$child=Start-Process powershell.exe -WindowStyle Hidden -ArgumentList '-NoProfile -Command Start-Sleep -Seconds 60' -PassThru; Write-Output $child.Id; Start-Sleep -Seconds 60", delegate(string line) { int value; if (int.TryParse(line, out value)) { child = value; received.Set(); } });
                using (runner) { if (!received.WaitOne(10000) || runner.Process.HasExited) throw new Exception("Startup/log forwarding failed"); }
                if (!runner.Process.WaitForExit(5000)) throw new Exception("Parent process remained alive");
                Thread.Sleep(500);
                try { var process = Process.GetProcessById(child); if (!process.HasExited) throw new Exception("Child process remained alive"); } catch (ArgumentException) {}
                File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "logs/tray-self-test.txt"), "PASS: startup, redirected output, parent and child termination"); return 0;
            } catch (Exception error) { File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "logs/tray-self-test.txt"), error.ToString()); return 1; }
        }
        bool created;
        using (var mutex = new Mutex(true, @"Local\IntelligentLiteratureReviewTray", out created)) {
            if (!created) { MessageBox.Show("启动程序已运行，请查看右下角托盘图标。"); return 0; }
            Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false); Application.Run(new WorkbenchTray());
        }
        return 0;
    }
}
