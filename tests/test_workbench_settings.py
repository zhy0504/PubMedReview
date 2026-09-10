from types import SimpleNamespace

import pytest

from workbench.validation import validate_options
from workbench.worker import apply_model_options
from workbench.app import create_app


def test_settings_save_reload_and_apply(tmp_path):
    app = create_app(root=tmp_path, data_dir=tmp_path / 'history')
    try:
        client = app.test_client()
        page = client.get('/').get_data(as_text=True)
        assert 'id="setting-service"' not in page
        assert 'id="ai-config"' not in page
        assert 'id="configuration"' not in page
        assert 'id="use-cache"' not in page
        script = client.get('/static/app.js').get_data(as_text=True)
        assert "byId('configuration')" not in script
        assert '默认温度' not in script
        token = page.split('name="workbench-token" content="')[1].split('"')[0]
        settings = {'model': 'local-test-model', 'temperature': 0.6, 'max_tokens': 4096, 'review_format': 'md', 'ai_config': 'custom'}
        response = client.put('/api/preferences', json=settings, headers={'X-Workbench-Token': token})
        assert response.status_code == 200
        saved = client.get('/api/preferences').json
        assert all(saved[key] == value for key, value in settings.items())
        components = [SimpleNamespace(model_id='old', model_parameters={'stream': True}) for _ in range(3)]
        system = SimpleNamespace(intent_analyzer=components[0], outline_generator=components[1], review_generator=components[2])
        apply_model_options(system, validate_options({'query': 'test', **saved}))
        for index, component in enumerate(components):
            assert component.model_id == 'local-test-model'
            assert component.model_parameters == {'stream': True, 'temperature': 0.6, 'max_tokens': 4096, 'reasoning_effort': 'medium' if index == 2 else 'low'}
    finally:
        app.extensions['jobs'].close()


@pytest.mark.parametrize('override', [{'temperature': float('nan')}, {'temperature': True}, {'max_tokens': -1}, {'review_format': []}, {'model': 123}])
def test_settings_validation(override):
    with pytest.raises(ValueError):
        validate_options({'query': 'test', **override})
