from __future__ import annotations

import argparse

from sellthrough.config import Settings


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    web_parser = subparsers.add_parser("web", help="Local web server")
    web_subparsers = web_parser.add_subparsers(dest="action", required=True)

    serve = web_subparsers.add_parser("serve", help="Run local FastAPI server")
    serve.add_argument("--host", default="127.0.0.1", help="Bind host")
    serve.add_argument("--port", type=int, default=8000, help="Bind port")
    serve.set_defaults(handler=handle_serve)


def handle_serve(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    try:
        import uvicorn
    except ImportError as exc:
        parser.error(
            "Web dependencies are not installed. Install with: "
            "python -m pip install -e .[web]"
        )
        raise exc

    from sellthrough.web.app import create_app

    settings = Settings.from_environment(require_ebay_credentials=False)
    app = create_app(settings=settings)
    uvicorn.run(app, host=args.host, port=args.port, reload=False, log_level="info")
    return 0
