# -*- coding: utf-8 -*-
"""
Behavior tests for advanced_cli utility methods.
"""

from pathlib import Path

from advanced_cli import AdvancedCLI


class _CompletedProcess:
    def __init__(self, stdout=""):
        self.stdout = stdout
        self.returncode = 0


def _build_cli(tmp_path):
    cli = AdvancedCLI()
    cli.project_root = tmp_path
    cli.history_file = tmp_path / ".cli_history.json"
    cli.log_file = tmp_path / "logs" / "cli.log"
    cli.log_file.parent.mkdir(parents=True, exist_ok=True)
    cli.requirements_file = tmp_path / "requirements.txt"
    return cli


def test_update_default_service_replaces_existing_line(tmp_path):
    cli = _build_cli(tmp_path)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "OPENAI_API_KEY=sk-test\nDEFAULT_AI_SERVICE=openai\n",
        encoding="utf-8",
    )

    assert cli._update_default_service_in_config("gemini") is True
    content = env_file.read_text(encoding="utf-8")
    assert "DEFAULT_AI_SERVICE=gemini" in content
    assert "DEFAULT_AI_SERVICE=openai" not in content


def test_update_default_service_appends_when_missing(tmp_path):
    cli = _build_cli(tmp_path)
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=sk-test\n", encoding="utf-8")

    assert cli._update_default_service_in_config("deepseek") is True
    content = env_file.read_text(encoding="utf-8")
    assert "DEFAULT_AI_SERVICE=deepseek" in content


def test_install_package_uses_preferred_python(monkeypatch, tmp_path):
    cli = _build_cli(tmp_path)
    monkeypatch.setattr(cli, "_get_preferred_python", lambda: "venv-python")
    monkeypatch.setattr(cli, "_log_action", lambda *args, **kwargs: None)

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return _CompletedProcess()

    monkeypatch.setattr("advanced_cli.subprocess.run", fake_run)

    cli.install_package("requests")

    assert captured["cmd"] == ["venv-python", "-m", "pip", "install", "requests"]
