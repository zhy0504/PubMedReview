"""Project-local environment inspection and repair commands."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


JOURNAL_FILES = (
    "FQBJCR2025-UTF8.csv",
    "JCR2025-UTF8.csv",
    "XR2026-UTF8.csv",
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def virtualenv_python(root: Path) -> Path:
    if os.name == "nt":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def _run(command, root: Path, capture: bool = True):
    kwargs = {
        "cwd": str(root),
        "env": {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        "check": False,
    }
    if capture:
        kwargs.update(capture_output=True, text=True, encoding="utf-8", errors="replace")
    return subprocess.run(command, **kwargs)


def _version(executable: Path | str, root: Path):
    try:
        result = _run([str(executable), "-c", "import sys; print(sys.version.split()[0])"], root)
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def _supported_version(version_text: str | None) -> bool:
    if not version_text:
        return False
    try:
        major, minor = (int(value) for value in version_text.split(".", 2)[:2])
    except (TypeError, ValueError):
        return False
    return (major, minor) >= (3, 10)


def _dependency_status(root: Path, python: Path | None):
    requirements = root / "requirements.txt"
    if python is None or not python.exists():
        return {"ok": False, "missing": [".venv"], "message": "虚拟环境不存在"}
    if not requirements.exists():
        return {"ok": False, "missing": ["requirements.txt"], "message": "缺少 requirements.txt"}
    checker = root / "tools" / "check_dependencies.py"
    if not checker.exists():
        return {"ok": False, "missing": ["tools/check_dependencies.py"], "message": "缺少依赖检查脚本"}
    try:
        result = _run([str(python), str(checker)], root)
    except (OSError, subprocess.SubprocessError) as error:
        return {"ok": False, "missing": [], "message": f"依赖检查失败：{type(error).__name__}"}
    missing = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    if result.returncode == 0:
        return {"ok": True, "missing": [], "message": "依赖已满足"}
    return {"ok": False, "missing": missing, "message": "存在缺失或版本不符合的依赖"}


def _pandoc_path(root: Path) -> Path | None:
    found = shutil.which("pandoc")
    if found:
        return Path(found)
    directory = "windows" if os.name == "nt" else platform.system().lower()
    filename = "pandoc.exe" if os.name == "nt" else "pandoc"
    portable = root / "tools" / "pandoc" / directory / filename
    return portable if portable.exists() else None


def _pandoc_version(path: Path | None):
    if path is None:
        return None
    try:
        result = subprocess.run([str(path), "--version"], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=10, check=False)
        if result.returncode == 0:
            return (result.stdout or "").splitlines()[0].strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def inspect_environment(root: Path | None = None) -> dict:
    root = Path(root or project_root()).resolve()
    current_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    venv = virtualenv_python(root)
    venv_version = _version(venv, root) if venv.exists() else None
    dependency = _dependency_status(root, venv if venv.exists() else None)
    pandoc = _pandoc_path(root)
    data_dir = root / "data"
    prompts = root / "prompts" / "prompts_config.yaml"
    journals = {name: (data_dir / name).exists() for name in JOURNAL_FILES}
    result = {
        "root": str(root),
        "python": {"version": current_version, "executable": sys.executable,
                    "supported": _supported_version(current_version)},
        "virtualenv": {"path": str(venv), "exists": venv.exists(),
                        "usable": bool(venv_version), "version": venv_version},
        "dependencies": dependency,
        "pandoc": {"path": str(pandoc) if pandoc else None,
                    "version": _pandoc_version(pandoc), "available": bool(pandoc)},
        "data_directory": data_dir.exists(),
        "prompts": prompts.exists(),
        "journals": journals,
    }
    result["ready"] = bool(
        result["python"]["supported"]
        and result["virtualenv"]["usable"]
        and result["dependencies"]["ok"]
        and result["data_directory"]
        and result["prompts"]
        and all(journals.values())
    )
    return result


def format_status(status: dict) -> str:
    dependency = status["dependencies"]
    journals = status["journals"]
    journal_state = "已齐全" if all(journals.values()) else "缺少：" + "、".join(name for name, ok in journals.items() if not ok)
    pandoc = status["pandoc"]
    lines = [
        f"[ENV] 项目目录：{status['root']}",
        f"[ENV] Python：{status['python']['version']}（{'可用' if status['python']['supported'] else '需要 3.10+'}）",
        f"[ENV] 虚拟环境：{'可用' if status['virtualenv']['usable'] else '缺少或不可用'}",
        f"[ENV] 依赖：{'已满足' if dependency['ok'] else dependency['message']}",
        f"[ENV] Pandoc：{pandoc['version'] or '未检测到'}",
        f"[ENV] 数据目录：{'存在' if status['data_directory'] else '缺少'}",
        f"[ENV] 提示词文件：{'存在' if status['prompts'] else '缺少'}",
        f"[ENV] 期刊 CSV：{journal_state}",
        f"[ENV] 总体：{'可以运行' if status['ready'] else '需要修复'}",
    ]
    if dependency.get("missing"):
        lines.append("[ENV] 缺失依赖：" + "、".join(dependency["missing"]))
    return "\n".join(lines)


def _creator_python(root: Path) -> str:
    current = Path(sys.executable).resolve()
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        base_python = Path(sys.base_prefix) / ("python.exe" if os.name == "nt" else "bin/python")
        if base_python.exists():
            return str(base_python)
        system_python = shutil.which("python")
        if system_python and Path(system_python).resolve() != current:
            return system_python
    return str(current)


def _ranked_indexes(root: Path) -> list[str]:
    selector = root / "tools" / "select_package_indexes.py"
    if not selector.exists():
        return ["https://pypi.org/simple"]
    result = _run([str(_creator_python(root)), str(selector)], root)
    indexes = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    return indexes or ["https://pypi.org/simple"]


def repair_environment(root: Path | None = None) -> dict:
    root = Path(root or project_root()).resolve()
    venv = virtualenv_python(root)
    if not venv.exists():
        creator = _creator_python(root)
        print("[FIX] 正在创建项目虚拟环境…", flush=True)
        result = _run([creator, "-m", "venv", str(root / ".venv")], root, capture=False)
        if result.returncode != 0 or not venv.exists():
            raise RuntimeError("创建虚拟环境失败，请确认 Python 3.10 或更高版本已安装")
        print("[FIX] 虚拟环境创建完成。", flush=True)
    dependency = _dependency_status(root, venv)
    if not dependency["ok"]:
        print("[FIX] 正在按响应速度选择镜像并安装依赖…", flush=True)
        requirements = root / "requirements.txt"
        installed = False
        for index in _ranked_indexes(root):
            print(f"[FIX] 安装源：{index}", flush=True)
            result = _run([str(venv), "-m", "pip", "--isolated", "install", "-r", str(requirements),
                           "--index-url", index, "--timeout", "30", "--retries", "1"], root, capture=False)
            if result.returncode == 0:
                installed = True
                break
        if not installed:
            raise RuntimeError("依赖安装失败，请检查网络连接或代理配置")
        print("[FIX] 依赖安装完成。", flush=True)
    status = inspect_environment(root)
    print(format_status(status), flush=True)
    return status


def install_pandoc(root: Path | None = None, update: bool = False) -> dict:
    root = Path(root or project_root()).resolve()
    venv = virtualenv_python(root)
    python = venv if venv.exists() else Path(sys.executable)
    script = root / "src" / "setup_pandoc_portable.py"
    if not script.exists():
        raise RuntimeError("项目内未找到 Pandoc 安装脚本")
    print("[FIX] 正在安装/更新 Pandoc…", flush=True)
    command = [str(python), str(script)] + (["--update"] if update else [])
    result = _run(command, root, capture=False)
    if result.returncode != 0:
        raise RuntimeError("Pandoc 安装或更新失败，请检查网络连接")
    status = inspect_environment(root)
    print(format_status(status), flush=True)
    return status


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="文献综述工作台环境检测与修复")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true", help="检测项目环境")
    group.add_argument("--repair", action="store_true", help="创建虚拟环境并安装缺失依赖")
    group.add_argument("--pandoc", action="store_true", help="安装 Pandoc")
    group.add_argument("--update-pandoc", action="store_true", help="更新 Pandoc")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出检测结果")
    args = parser.parse_args(argv)
    try:
        if args.repair:
            status = repair_environment()
        elif args.pandoc:
            status = install_pandoc(update=False)
        elif args.update_pandoc:
            status = install_pandoc(update=True)
        else:
            status = inspect_environment()
            print(json.dumps(status, ensure_ascii=False) if args.json else format_status(status), flush=True)
        return 0 if status.get("ready", True) or args.repair or args.pandoc or args.update_pandoc else 0
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"[FIX] 失败：{error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
