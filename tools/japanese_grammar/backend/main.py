"""Loopback-only CLI entrypoint for the Japanese grammar local-personal backend."""

from __future__ import annotations

import argparse
from typing import Sequence

import uvicorn

from .api import create_app
from .runtime import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    LocalRuntime,
    data_lock,
    remove_server_metadata,
    resolve_data_dir,
    resolve_packages_dir,
    resolve_web_dir,
    validate_loopback_host,
    validate_port,
    write_server_metadata,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Start the GraspMemoEdu Japanese Grammar local-personal loopback backend.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Loopback bind address (127.0.0.1 or localhost, default {DEFAULT_HOST}).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Loopback TCP port (default {DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Runtime state directory (defaults to GRASPMEMOEDU_JP_DATA_DIR or .runtime/japanese-grammar).",
    )
    parser.add_argument(
        "--packages-dir",
        default=None,
        help="Curriculum packages directory (defaults to GRASPMEMOEDU_JP_PACKAGES_DIR or tools/japanese_grammar/packages).",
    )
    parser.add_argument(
        "--web-dir",
        default=None,
        help="Static frontend directory (defaults to tools/japanese_grammar/web).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Explicitly clear local SQLite progress, daily quotas, and event logs before startup.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    host = validate_loopback_host(args.host)
    port = validate_port(args.port)
    data_dir = resolve_data_dir(args.data_dir)
    packages_dir = resolve_packages_dir(args.packages_dir)
    web_dir = resolve_web_dir(args.web_dir)

    with data_lock(data_dir):
        runtime = LocalRuntime(
            packages_dir=packages_dir,
            data_dir=data_dir,
            web_dir=web_dir,
            host=host,
            port=port,
            reset=bool(args.reset),
        )
        app = create_app(runtime)
        write_server_metadata(
            runtime.data_dir,
            port=runtime.port,
            instance_id=runtime.instance_id,
            host=runtime.host,
            started_at=runtime.process_started_at,
        )
        try:
            config = uvicorn.Config(
                app,
                host=runtime.host,
                port=runtime.port,
                log_level="info",
                access_log=False,
            )
            server = uvicorn.Server(config)
            server.run()
        finally:
            remove_server_metadata(runtime.data_dir, instance_id=runtime.instance_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
