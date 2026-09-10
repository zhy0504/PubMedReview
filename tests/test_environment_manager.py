import importlib.util
from pathlib import Path


def load_environment_manager():
    path = Path(__file__).resolve().parents[1] / 'tools' / 'environment_manager.py'
    spec = importlib.util.spec_from_file_location('environment_manager', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inspect_environment_reports_all_repairable_components(tmp_path, monkeypatch):
    module = load_environment_manager()
    (tmp_path / 'data').mkdir()
    (tmp_path / 'prompts').mkdir()
    (tmp_path / 'prompts' / 'prompts_config.yaml').write_text('{}\n', encoding='utf-8')
    for name in module.JOURNAL_FILES:
        (tmp_path / 'data' / name).write_text('header\n', encoding='utf-8')

    monkeypatch.setattr(module, 'virtualenv_python', lambda root: root / '.venv' / 'Scripts' / 'python.exe')
    monkeypatch.setattr(module, '_version', lambda executable, root: '3.14.6')
    monkeypatch.setattr(module, '_dependency_status', lambda root, python: {'ok': True, 'missing': [], 'message': '依赖已满足'})
    monkeypatch.setattr(module, '_pandoc_path', lambda root: root / 'pandoc.exe')
    monkeypatch.setattr(module, '_pandoc_version', lambda path: 'pandoc 3.8')

    status = module.inspect_environment(tmp_path)
    assert status['python']['supported'] is True
    assert status['virtualenv']['usable'] is False
    assert status['pandoc']['available'] is True
    assert status['data_directory'] is True
    assert status['prompts'] is True
    assert status['journals'] == {name: True for name in module.JOURNAL_FILES}
    assert status['ready'] is False
    assert '需要修复' in module.format_status(status)


def test_format_status_lists_missing_dependency_and_journal(tmp_path):
    module = load_environment_manager()
    status = {
        'root': str(tmp_path),
        'python': {'version': '3.14.6', 'supported': True},
        'virtualenv': {'usable': True},
        'dependencies': {'ok': False, 'missing': ['Flask>=3.1'], 'message': '存在缺失或版本不符合的依赖'},
        'pandoc': {'version': None},
        'data_directory': True,
        'prompts': False,
        'journals': {module.JOURNAL_FILES[0]: True, module.JOURNAL_FILES[1]: False, module.JOURNAL_FILES[2]: True},
        'ready': False,
    }
    output = module.format_status(status)
    assert '缺少：JCR2025-UTF8.csv' in output
    assert '缺失依赖：Flask>=3.1' in output
    assert '提示词文件：缺少' in output
