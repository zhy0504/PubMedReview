from pathlib import Path

import yaml

from shared_config import SystemConfig


def test_system_yaml_contains_only_exposed_defaults():
    path = Path(__file__).resolve().parents[1] / 'system_config.yaml'
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    assert set(data) == {'ai', 'export'}
    assert set(data['ai']) == {'preferred_model'}
    assert set(data['export']) == {'review_format', 'medical_template'}


def test_retained_defaults_are_read_and_removed_fields_fall_back():
    config = object.__new__(SystemConfig)
    config._config_data = {'ai': {'preferred_model': 'test-model'}, 'export': {'review_format': 'md', 'medical_template': 'test.docx'}}
    assert config.PREFERRED_MODEL == 'test-model'
    assert config.REVIEW_FORMAT == 'md'
    assert config.MEDICAL_TEMPLATE == 'test.docx'
    assert config.CACHE_SIZE == 500
    assert config.REQUEST_TIMEOUT == 30
    assert config.DEFAULT_TEMPERATURE == 0.1
    assert config.DEFAULT_MAX_TOKENS is None
