"""Loopback-only HTTP presentation; business execution lives in jobs/worker."""

import atexit
import secrets
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file
from werkzeug.exceptions import HTTPException

from workbench.jobs import JobManager
from workbench.store import HistoryStore
from workbench.validation import validate_options


def create_app(root=None, data_dir=None, command=None):
    root = Path(root or Path(__file__).resolve().parents[2]).resolve()
    data_dir = Path(data_dir or root / 'workspace_data').resolve()
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.update(MAX_CONTENT_LENGTH=64 * 1024, TRUSTED_HOSTS=['127.0.0.1', 'localhost', '[::1]'])
    token = secrets.token_urlsafe(32)
    store = HistoryStore(data_dir / 'history.sqlite3')
    manager = JobManager(store, root, command=command)
    app.extensions.update(history=store, jobs=manager)
    atexit.register(manager.close)

    @app.before_request
    def protect_local_api():
        if request.remote_addr not in {'127.0.0.1', '::1', None}:
            abort(403)
        if request.headers.get('Sec-Fetch-Site') == 'cross-site':
            abort(403)
        origin = request.headers.get('Origin')
        if origin and origin != request.host_url.rstrip('/'):
            abort(403)
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            if not secrets.compare_digest(request.headers.get('X-Workbench-Token', ''), token):
                abort(403)
            if not request.is_json:
                abort(415)

    @app.after_request
    def security_headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.errorhandler(Exception)
    def error_response(error):
        if isinstance(error, HTTPException):
            return jsonify(error=error.description), error.code
        if isinstance(error, ValueError):
            return jsonify(error=str(error)), 400
        if isinstance(error, RuntimeError):
            return jsonify(error=str(error)), 409
        app.logger.error('Workbench request failed: %s', type(error).__name__)
        return jsonify(error='操作失败，请检查任务状态或本地日志'), 500

    def paging(default=30):
        offset = int(request.args.get('offset', 0))
        limit = int(request.args.get('limit', default))
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError('分页参数无效')
        return offset, limit

    def require_job(job_id):
        job = store.get_job(job_id)
        if job is None:
            abort(404)
        return job

    @app.get('/')
    def index():
        from datetime import date
        return render_template('index.html', token=token, current_year=date.today().year)

    @app.route('/api/configuration', methods=['GET', 'PUT'])
    def configuration():
        from workbench.configuration import read_configuration, save_configuration
        if request.method == 'PUT':
            if manager.active_id:
                raise RuntimeError('请等待当前任务结束再修改连接配置')
            return jsonify(save_configuration(root, request.get_json()))
        return jsonify(read_configuration(root))

    @app.get('/api/providers')
    def providers():
        from ai_providers import provider_options
        return jsonify(providers=provider_options())

    @app.post('/api/models')
    def models():
        from workbench.configuration import discover_models
        return jsonify(models=discover_models(root))

    @app.get('/api/bootstrap')
    def bootstrap():
        from workbench.configuration import read_configuration
        from shared_config import system_config
        config = read_configuration(root)
        return jsonify(stats=store.stats(), preferences=store.preferences(), active_id=manager.active_id,
            configuration={'service': config['service'], 'provider': config['provider'],
                'key_configured': config['api_key_configured'],
                'model': config['model'] or system_config.PREFERRED_MODEL,
                'api_type': config['api_type'],
                'temperature': system_config.DEFAULT_TEMPERATURE, 'max_tokens': system_config.DEFAULT_MAX_TOKENS,
                'review_format': system_config.REVIEW_FORMAT,
                'data_available': any((root / 'data' / filename).exists() for filename in ('processed_zky_data.csv', 'processed_jcr_data.csv', 'zky.csv', 'jcr.csv'))})

    @app.get('/api/system/status')
    def system_status():
        import importlib.util, platform, shutil, sys
        return jsonify(python=sys.version.split()[0], platform=platform.platform(),
            executable=sys.executable, virtualenv=bool(sys.prefix != getattr(sys, 'base_prefix', sys.prefix)),
            pandoc=shutil.which('pandoc') or (str(root / 'tools/pandoc/windows/pandoc.exe') if (root / 'tools/pandoc/windows/pandoc.exe').exists() else None),
            data_directory=(root / 'data').exists(), prompts=(root / 'prompts/prompts_config.yaml').exists(),
            dependencies={name: bool(importlib.util.find_spec(name)) for name in ('flask','requests','yaml','aiohttp','lxml')})

    @app.post('/api/system/install')
    def install_system_component():
        import subprocess, sys
        component = (request.get_json() or {}).get('component')
        if component == 'dependencies':
            subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(root / 'requirements.txt')], cwd=root, check=True, timeout=900)
            return jsonify(ok=True, component=component)
        if component in {'pandoc', 'pandoc_update'}:
            script = root / 'src' / 'setup_pandoc_portable.py'
            if not script.exists(): raise ValueError('项目内未提供 Pandoc 安装脚本')
            command = [sys.executable, str(script)] + (['--update'] if component == 'pandoc_update' else [])
            result = subprocess.run(command, cwd=root, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900)
            if result.returncode != 0:
                raise ValueError('Pandoc 安装失败，请检查网络连接或代理配置')
            return jsonify(ok=True, component=component)
        raise ValueError('不支持的安装项目')

    @app.get('/api/journals/status')
    def journal_status():
        from journal_update import latest_status
        return jsonify(latest_status(root))


    @app.route('/api/prompts', methods=['GET', 'PUT'])
    def prompts():
        import yaml
        path = root / 'prompts/prompts_config.yaml'
        if request.method == 'GET':
            if not path.exists(): abort(404)
            raw = path.read_text(encoding='utf-8')
            data = yaml.safe_load(raw) or {}
            return jsonify(content=raw, modules={key: yaml.safe_dump(data.get(key, {}), allow_unicode=True, sort_keys=False) for key in ('intent_analysis', 'outline_generation', 'review_generation')})
        if manager.active_id: raise RuntimeError('请等待任务结束再修改提示词')
        payload = request.get_json() if isinstance(request.get_json(), dict) else {}
        content = payload.get('content')
        modules = payload.get('modules')
        if isinstance(modules, dict):
            current = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
            for key in ('intent_analysis', 'outline_generation', 'review_generation'):
                if key in modules:
                    value = modules[key]
                    if not isinstance(value, str) or len(value) > 50000: raise ValueError('提示词模块无效')
                    try:
                        parsed = yaml.safe_load(value)
                    except yaml.YAMLError:
                        parsed = None
                    if isinstance(parsed, dict):
                        current[key] = parsed
                    else:
                        current[key] = {'user_prompt_template': value}
            content = yaml.safe_dump(current, allow_unicode=True, sort_keys=False)
        if not isinstance(content, str) or len(content) > 100000: raise ValueError('提示词配置无效')
        try: yaml.safe_load(content)
        except yaml.YAMLError: raise ValueError('提示词 YAML 格式无效')
        path.write_text(content, encoding='utf-8')
        return jsonify(ok=True)

    @app.route('/api/preferences', methods=['GET', 'PUT'])
    def preferences():
        data = validate_options(request.get_json(), require_query=False) if request.method == 'PUT' else None
        return jsonify(store.preferences(data))

    @app.route('/api/jobs', methods=['GET', 'POST'])
    def jobs():
        if request.method == 'POST':
            return jsonify(manager.start(request.get_json())), 201
        offset, limit = paging()
        return jsonify(store.list_jobs(request.args.get('q', '')[:500], request.args.get('status', ''), offset, limit))

    @app.route('/api/jobs/<job_id>', methods=['GET', 'DELETE'])
    def job_detail(job_id):
        job = require_job(job_id)
        if request.method == 'DELETE':
            if manager.active_id == job_id: raise RuntimeError('当前任务运行中，不能清理')
            store.delete_job(job_id)
            return jsonify(ok=True)
        return jsonify(**job, artifacts=store.artifacts(job_id), outline=store.latest_payload(job_id, 'outline'),
                       criteria=store.latest_payload(job_id, 'criteria'), article_count=store.articles(job_id, limit=1)['total'])

    @app.get('/api/jobs/<job_id>/events')
    def events(job_id):
        require_job(job_id)
        after = int(request.args.get('after', 0))
        if after < 0:
            raise ValueError('事件游标无效')
        return jsonify(items=store.events(job_id, after))

    @app.get('/api/jobs/<job_id>/articles')
    def articles(job_id):
        require_job(job_id)
        offset, limit = paging(50)
        return jsonify(store.articles(job_id, request.args.get('q', '')[:500], offset, limit))

    @app.post('/api/jobs/<job_id>/respond')
    def respond(job_id):
        require_job(job_id)
        data = request.get_json()
        if not isinstance(data, dict):
            raise ValueError('交互回答格式无效')
        manager.respond(job_id, data.get('prompt_id'), data.get('value'))
        return jsonify(ok=True)

    @app.post('/api/jobs/<job_id>/cancel')
    def cancel(job_id):
        require_job(job_id)
        manager.cancel(job_id)
        return jsonify(ok=True)

    @app.get('/api/artifacts/<int:artifact_id>')
    def artifact(artifact_id):
        record = store.artifact(artifact_id)
        if not record:
            abort(404)
        path = (data_dir / record['path']).resolve()
        artifact_root = (data_dir / 'artifacts').resolve()
        if artifact_root not in path.parents or not path.is_file():
            abort(404)
        if request.args.get('preview') == '1':
            if path.suffix.lower() not in {'.md', '.txt', '.csv', '.json'}:
                raise ValueError('此格式请下载后查看')
            with path.open('r', encoding='utf-8-sig', errors='replace') as stream:
                text = stream.read(200001)
            return jsonify(content=text[:200000], truncated=len(text) > 200000)
        return send_file(path, as_attachment=True, download_name=path.name)

    return app

