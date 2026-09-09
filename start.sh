#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
PYTHON="${PWD}/.venv/bin/python"
SYSTEM_PYTHON="$(command -v python3 || true)"
if [[ ! -x "$PYTHON" ]]; then
  [[ -n "$SYSTEM_PYTHON" ]] || { echo "未找到 Python，请先安装 Python 3.10+。" >&2; exit 1; }
  "$SYSTEM_PYTHON" -m venv .venv
fi
if "$PYTHON" tools/check_dependencies.py; then
  echo 'Dependencies already installed; skipping download.'
else
INDEXES="$("$PYTHON" tools/select_package_indexes.py)"
INSTALLED=0
while IFS= read -r INDEX; do
  echo "Installing from $INDEX (ranked by response time)..."
  if "$PYTHON" -m pip --isolated install -r requirements.txt --index-url "$INDEX" --timeout 30 --retries 1; then
    INSTALLED=1
    break
  fi
done <<< "$INDEXES"
[[ "$INSTALLED" == 1 ]] || { echo "Dependency installation failed." >&2; exit 1; }
fi
echo "正在启动本地 Web 工作台：http://127.0.0.1:8765"
exec "$PYTHON" src/web.py "$@"
