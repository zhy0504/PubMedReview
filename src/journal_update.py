"""Report presence of the bundled ShowJCR journal tables."""

from pathlib import Path
FILES = {'FQBJCR2025-UTF8.csv': 'FQBJCR2025-UTF8.csv', 'JCR2025-UTF8.csv': 'JCR2025-UTF8.csv', 'XR2026-UTF8.csv': 'XR2026-UTF8.csv'}


def latest_status(root):
    data = root / 'data'
    return {'files': {name: {'exists': (data / name).is_file(), 'size': (data / name).stat().st_size if (data / name).is_file() else 0} for name in FILES}, 'source': 'ShowJCR', 'source_files': FILES}
