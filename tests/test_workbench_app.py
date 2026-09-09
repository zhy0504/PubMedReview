from workbench.app import create_app


def test_ris_collected_listed_and_downloaded(tmp_path):
    app = create_app(root=tmp_path, data_dir=tmp_path / 'history', command=['python', '-c', ''])
    manager = app.extensions['jobs']
    store = app.extensions['history']
    try:
        store.create_job('ris-test', {'query': 'RIS test'})
        before = manager._snapshot()
        output = tmp_path / 'output'
        output.mkdir()
        name = '检索主题-最终纳入综述文献.ris'
        content = 'TY  - JOUR\nTI  - Test article\nER  - \n'
        (output / name).write_text(content, encoding='utf-8')
        manager._collect_artifacts('ris-test', before)
        client = app.test_client()
        detail = client.get('/api/jobs/ris-test')
        assert detail.status_code == 200
        artifacts = detail.json['artifacts']
        assert len(artifacts) == 1
        assert artifacts[0]['name'] == name
        response = client.get('/api/artifacts/' + str(artifacts[0]['id']))
        assert response.status_code == 200
        assert response.data == (output / name).read_bytes()
        assert 'attachment' in response.headers['Content-Disposition']
    finally:
        manager.close()


def test_app_requires_token_for_write_and_serves_ui(tmp_path):
    app = create_app(root=tmp_path, data_dir=tmp_path / 'data', command=['python', '-c', ''])
    client = app.test_client()
    assert client.get('/').status_code == 200
    status = client.get('/api/system/status')
    assert status.status_code == 200
    assert {'data_directory', 'prompts', 'pandoc'}.issubset(status.json)
    assert client.post('/api/jobs', json={'query': 'q'}).status_code == 403
    app.extensions['jobs'].close()


def test_app_rejects_non_loopback_and_path_escape(tmp_path):
    app = create_app(root=tmp_path, data_dir=tmp_path / 'data', command=['python', '-c', ''])
    client = app.test_client()
    token = client.get('/').get_data(as_text=True).split('name="workbench-token" content="')[1].split('"', 1)[0]
    response = client.get('/api/artifacts/1?preview=1')
    assert response.status_code == 404
    assert client.get('/api/bootstrap', environ_overrides={'REMOTE_ADDR': '192.0.2.1'}).status_code == 403
    assert client.get('/api/bootstrap', headers={'Host': 'evil.example'}).status_code == 400
    assert client.put('/api/preferences', json={}, headers={'X-Workbench-Token': token, 'Origin': 'https://evil.example'}).status_code == 403
    store = app.extensions['history']
    store.create_job('escape', {'query': 'escape'})
    outside = tmp_path / 'private.txt'
    outside.write_text('private', encoding='utf-8')
    store.add_artifact('escape', '../private.txt', 'private.txt', 7)
    artifact_id = store.artifacts('escape')[0]['id']
    assert client.get(f'/api/artifacts/{artifact_id}').status_code == 404
    assert client.put('/api/preferences', json={'target': 10}, headers={'X-Workbench-Token': token}).status_code == 200
    app.extensions['jobs'].close()
