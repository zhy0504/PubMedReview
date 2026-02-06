# -*- coding: utf-8 -*-
"""
Regression tests for CLI/startup robustness improvements.
"""

import builtins

import cli as cli_module
import start as start_module


class _CompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_cli_prompt_yes_no_non_interactive_uses_default(monkeypatch):
    cli = cli_module.IntelligentLiteratureCLI()
    monkeypatch.setattr(cli, "_is_interactive_terminal", lambda: False)

    assert cli._prompt_yes_no("ignored", default=True) is True
    assert cli._prompt_yes_no("ignored", default=False) is False


def test_cli_parse_requirement_supports_extras_and_dotted_names():
    cli = cli_module.IntelligentLiteratureCLI()

    pkg, spec = cli._parse_requirement("google-api-core[grpc]>=2.17.0")
    assert pkg == "google-api-core"
    assert spec == ">=2.17.0"

    pkg2, spec2 = cli._parse_requirement("uvicorn==0.30.0")
    assert pkg2 == "uvicorn"
    assert spec2 == "==0.30.0"


def test_cli_start_project_returns_false_on_subprocess_failure(monkeypatch):
    cli = cli_module.IntelligentLiteratureCLI()
    monkeypatch.setattr(cli, "detect_virtual_environment", lambda: {"venv_active": True, "venv_python": None})
    monkeypatch.setattr(
        cli,
        "get_requirements_status",
        lambda: {"missing_packages": []},
    )
    monkeypatch.setattr(cli, "check_ai_config", lambda: {"valid_services": 1})
    monkeypatch.setattr(cli, "_get_preferred_python", lambda: "venv-python")

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _CompletedProcess(returncode=1)

    monkeypatch.setattr(cli_module.subprocess, "run", fake_run)

    assert cli.start_project("batch") is False
    assert captured["cmd"][0] == "venv-python"
    assert captured["cmd"][1].endswith("intelligent_literature_system.py")


def test_cli_start_project_allows_inactive_shell_if_venv_exists(monkeypatch):
    cli = cli_module.IntelligentLiteratureCLI()
    monkeypatch.setattr(
        cli,
        "detect_virtual_environment",
        lambda: {"venv_active": False, "venv_python": "venv/python"},
    )
    monkeypatch.setattr(
        cli,
        "get_requirements_status",
        lambda: {"missing_packages": []},
    )
    monkeypatch.setattr(cli, "check_ai_config", lambda: {"valid_services": 1})
    monkeypatch.setattr(cli, "_get_preferred_python", lambda: "venv/python")
    monkeypatch.setattr(
        cli_module.subprocess,
        "run",
        lambda cmd, **kwargs: _CompletedProcess(returncode=0),
    )

    assert cli.start_project("interactive") is True


def test_start_check_dependencies_runs_in_project_cwd(tmp_path, monkeypatch):
    base_dir = tmp_path
    requirements_file = base_dir / "requirements.txt"
    requirements_file.write_text("pytest\n", encoding="utf-8")

    venv_python = base_dir / "venv" / "Scripts" / "python.exe"
    venv_pip = base_dir / "venv" / "Scripts" / "pip.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")
    venv_pip.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        start_module,
        "get_venv_paths",
        lambda: (base_dir, base_dir / "venv", venv_python, venv_pip),
    )

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cwd"] = kwargs.get("cwd")
        return _CompletedProcess(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(start_module.subprocess, "run", fake_run)

    assert start_module.check_dependencies() is True
    assert captured["cwd"] == str(base_dir)


def test_start_parallel_checks_uses_cache_without_reading_input(monkeypatch):
    class _FakeCache:
        def load_environment_cache(self):
            return {"dependencies_checked": True, "timestamp": "2026-02-01T00:00:00"}

        def save_environment_cache(self, data):
            return None

    monkeypatch.setattr(start_module, "SystemCache", _FakeCache)
    monkeypatch.setattr(start_module, "is_interactive_terminal", lambda: False)
    monkeypatch.setattr(builtins, "input", lambda _: (_ for _ in ()).throw(AssertionError("input should not be called")))
    monkeypatch.delenv("PS_CACHE_USED", raising=False)
    monkeypatch.delenv("PS_CACHE_ASKED", raising=False)

    results = start_module.parallel_environment_checks(force_check=False)

    assert results
    assert all(results.values())


def test_start_literature_system_prefers_venv_python(tmp_path, monkeypatch):
    base_dir = tmp_path
    venv_python = base_dir / "venv" / "Scripts" / "python.exe"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")

    monkeypatch.setattr(
        start_module,
        "get_venv_paths",
        lambda: (base_dir, base_dir / "venv", venv_python, base_dir / "venv" / "Scripts" / "pip.exe"),
    )
    monkeypatch.setattr(
        start_module,
        "check_pandoc_status",
        lambda: {"status": "installed", "path": "dummy", "version": "1.0"},
    )
    monkeypatch.setattr(start_module, "HAS_ADVANCED_CLI", False)

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _CompletedProcess(returncode=0)

    monkeypatch.setattr(start_module.subprocess, "run", fake_run)

    assert start_module.start_literature_system() is True
    assert captured["cmd"][0] == str(venv_python)
    assert captured["cmd"][1].endswith("intelligent_literature_system.py")


def test_start_main_skips_menu_in_non_interactive(monkeypatch):
    monkeypatch.setattr(start_module, "print_startup_banner", lambda: None)
    monkeypatch.setattr(start_module, "parallel_environment_checks", lambda force_check=False: {"ok": True})
    monkeypatch.setattr(start_module, "is_interactive_terminal", lambda: False)

    called = {"menu": False}

    def fake_menu():
        called["menu"] = True

    monkeypatch.setattr(start_module, "show_quick_menu", fake_menu)
    monkeypatch.setattr(start_module.sys, "argv", ["start.py"])

    start_module.main()

    assert called["menu"] is False
