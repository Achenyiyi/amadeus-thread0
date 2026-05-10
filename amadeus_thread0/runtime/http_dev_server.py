from __future__ import annotations

import argparse
import os
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any
from wsgiref.simple_server import WSGIServer, make_server

from ..env_bootstrap import load_project_dotenv
from .http_transport import WsgiApp, create_http_transport_app
from .runtime_bundle import RuntimeBundle
from .settings import get_settings


class ThreadedWsgiServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


def create_dev_server_app(
    *,
    thread_id: str | None = None,
    base_data_dir: Path | None = None,
    cwd: Path | None = None,
    settings: Any | None = None,
) -> tuple[WsgiApp, RuntimeBundle]:
    load_project_dotenv(override=False)
    current_settings = settings or get_settings()
    resolved_thread_id = str(thread_id or current_settings.thread_id or "thread0").strip() or "thread0"
    runtime_bundle = RuntimeBundle.create(thread_id=resolved_thread_id, settings=current_settings)
    root = Path(base_data_dir or current_settings.data_dir)
    backend_api = runtime_bundle.backend_api(base_data_dir=root, cwd=Path(cwd or Path.cwd()))
    return create_http_transport_app(backend_api), runtime_bundle


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m amadeus_thread0.runtime.http_dev_server",
        description="Serve the Amadeus-K backend.v1 WSGI transport for local frontend development.",
    )
    parser.add_argument("--host", default=os.getenv("AMADEUS_HTTP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("AMADEUS_HTTP_PORT", "4180")))
    parser.add_argument("--thread-id", default=os.getenv("AMADEUS_THREAD_ID", "thread0"))
    parser.add_argument("--base-data-dir", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    app, runtime_bundle = create_dev_server_app(
        thread_id=str(args.thread_id or "thread0"),
        base_data_dir=Path(args.base_data_dir) if str(args.base_data_dir or "").strip() else None,
        cwd=Path.cwd(),
    )
    try:
        with make_server(str(args.host), int(args.port), app, server_class=ThreadedWsgiServer) as server:
            print(
                "Amadeus-K backend HTTP dev server listening at "
                f"http://{args.host}:{args.port} "
                f"(thread_id={runtime_bundle.thread_id})",
                flush=True,
            )
            server.serve_forever()
    except KeyboardInterrupt:
        print("Amadeus-K backend HTTP dev server stopped.", flush=True)
    finally:
        runtime_bundle.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["ThreadedWsgiServer", "create_dev_server_app", "main"]
