#!/usr/bin/env python3
"""Start the local workbench without environment auto-installation or remote hosting."""

import argparse
import os

from werkzeug.serving import make_server

from workbench.app import create_app


def main():
    parser = argparse.ArgumentParser(description='智能文献综述 · 本地工作台')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    app = create_app()
    manager = app.extensions['jobs']
    try:
        server = make_server('127.0.0.1', args.port, app, threaded=True)
        print(f'本地工作台：http://127.0.0.1:{args.port}', flush=True)
        print('仅限本机访问。按 Ctrl+C 停止；历史结果保存在 workspace_data。', flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        manager.close()


if __name__ == '__main__':
    main()
