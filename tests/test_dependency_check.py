import importlib.util
from pathlib import Path


def test_dependency_versions_and_missing_packages(tmp_path):
    path = Path(__file__).resolve().parents[1] / 'tools/check_dependencies.py'
    spec = importlib.util.spec_from_file_location('check_dependencies', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    requirements = tmp_path / 'requirements.txt'
    requirements.write_text('pytest>=1\npytest>9999\nnonexistent-literature-package-123\n', encoding='utf-8')
    assert module.missing_requirements(requirements) == ['pytest>9999', 'nonexistent-literature-package-123']
