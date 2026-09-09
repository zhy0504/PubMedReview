"""Create a clean source snapshot without modifying the working checkout."""

import ast
import hashlib
import json
from pathlib import Path
import shutil
import sys


def prepare(root, destination):
    root = Path(root).resolve()
    destination = Path(destination).resolve()
    if root not in destination.parents or destination.exists():
        raise ValueError('Destination must be a new directory inside the project')
    roots = ('README.md', 'LICENSE', '.gitignore', '.env.example', 'requirements.txt',
             'pytest.ini', 'system_config.yaml', 'start.ps1', 'start.sh', 'start for win11.bat',
             'docs/tray-launcher.md', 'docs/release-audit.md', 'prompts/prompts_config.yaml')
    files = [root / name for name in roots]
    for directory in ('src', 'tests'):
        files.extend(path for path in (root / directory).rglob('*') if path.is_file()
                     and '__pycache__' not in path.parts and '.before-' not in path.name
                     and path.suffix in {'.py', '.js', '.css', '.html'})
    tools = ('WorkbenchTray.cs', 'build-tray.ps1', 'make-icon.ps1', 'workbench.ico',
             'select_package_indexes.py', 'check_dependencies.py', 'prepare_release.py')
    files.extend(root / 'tools' / name for name in tools)
    secrets = []
    env = root / '.env'
    if env.exists():
        for line in env.read_text(encoding='utf-8-sig').splitlines():
            key, separator, value = line.partition('=')
            if separator and any(label in key.upper() for label in ('KEY', 'TOKEN', 'PASSWORD', 'SECRET')):
                value = value.strip().strip('\"\'')
                if len(value) >= 8:
                    secrets.append(value.encode('utf-8'))
    manifest = []
    for source in sorted(set(files)):
        content = source.read_bytes()
        if any(secret in content for secret in secrets):
            raise ValueError(f'Local credential found in release input: {source.relative_to(root)}')
        if source.suffix == '.py':
            ast.parse(content, filename=str(source))
        manifest.append({'path': source.relative_to(root).as_posix(), 'sha256': hashlib.sha256(content).hexdigest()})
    destination.mkdir(parents=True)
    for record in manifest:
        target = destination / record['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / record['path'], target)
    (destination / 'data').mkdir()
    (destination / 'data/README.md').write_text('请放入有权使用的 FQBJCR2025-UTF8.csv、JCR2025-UTF8.csv、XR2026-UTF8.csv。源代码发布候选不包含第三方期刊数据。\n', encoding='utf-8')
    (destination / 'release-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Prepared {len(manifest)} files; local credential comparison passed.')


if __name__ == '__main__':
    prepare(Path(__file__).resolve().parents[1], sys.argv[1])
