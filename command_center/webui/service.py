"""Read-only, localhost-bound HTTP service for the graphical dashboard.

Security posture (binding per issue #22):
- Binds 127.0.0.1 only; a non-loopback address is refused at startup.
- Strict CSP: ``default-src 'self'``; no inline script/style; no remote origins.
- Read-only API: GET /api/state plus an SSE stream; POST/PUT/DELETE rejected.
- No command execution from display data anywhere in the request path.
- Demo mode serves fixtures only -- no SSH, no GitHub, no subprocess.
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from command_center.webui import fixtures
from command_center.webui.collectors import build_node_state, collect_github_state, github_queue_items
from command_center.webui.config import DEFAULT_HOST, DEFAULT_PORT, WebUIConfig
from command_center.webui.model import DashboardState, QueueItem, WorkflowSnapshot
from command_center.webui.todos import TodoCache
from command_center.webui.workflow import Handoff

STATIC_DIR = Path(__file__).resolve().parent / "static"
SSE_HEARTBEAT_S = 15.0
MAX_SSE_CLIENT_SECONDS = 3600.0

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".json": "application/json; charset=utf-8",
    ".ico": "image/x-icon",
}

CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "font-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "frame-ancestors 'none'"
)


class DashboardStateProvider:
    """Produces the current DashboardState.

    - Demo mode serves sanitized fixtures only: no SSH, no GitHub, no
      subprocess. This is the default so starting the service on any
      machine is safe.
    - Live mode (explicit config with ``demo_mode=false`` and nodes) runs
      bounded, fail-closed collectors; unreachable pieces degrade to
      OFFLINE/stale instead of blocking the response.
    """

    def __init__(self, config: WebUIConfig) -> None:
        self.config = config
        self.todos_cache = TodoCache(Path.home() / ".cache" / "r510-command-center")
        self._last_github_ok = False
        self._last_workflow_stage = "intake"

    def state(self) -> DashboardState:
        now = time.time()
        if self.config.demo_mode:
            return self._demo_state(now)
        return self._live_state(now)

    def _demo_state(self, now: float) -> DashboardState:
        base = fixtures.demo_dashboard()
        return DashboardState(
            generated_at_epoch_s=now,
            demo_mode=True,
            github_reachable=base.github_reachable,
            github_stale=base.github_stale,
            nodes=base.nodes,
            workflow=base.workflow,
            queue=base.queue,
        )

    def _live_state(self, now: float) -> DashboardState:
        cfg = self.config
        nodes = []
        for node_cfg in cfg.nodes:
            nodes.append(
                build_node_state(
                    node_id=node_cfg.node_id,
                    role=node_cfg.role,
                    host_alias=node_cfg.host_alias,
                    ssh_destination=node_cfg.ssh_destination,
                    agent_id=node_cfg.node_id,
                    timeout_s=cfg.ssh_timeout_s,
                    stale_after_s=cfg.stale_after_s,
                    todos_cache=self.todos_cache,
                    now_s=now,
                )
            )
        github_ok, github_stale, raw_entries = (
            collect_github_state() if cfg.github_enabled else (False, True, [])
        )
        self._last_github_ok = github_ok
        queue_items = github_queue_items(raw_entries)
        workflow = self._workflow_from(queue_items, now)
        return DashboardState(
            generated_at_epoch_s=now,
            demo_mode=False,
            github_reachable=github_ok,
            github_stale=github_stale,
            nodes=tuple(nodes),
            workflow=workflow,
            queue=queue_items,
        )

    def _workflow_from(self, queue_items: tuple[QueueItem, ...], now: float) -> WorkflowSnapshot:
        """Derive a coarse workflow snapshot from queue items + last stage."""
        focus = next((q for q in queue_items if q.state in ("working", "awaiting-human")), None)
        stage = focus.stage if focus else self._last_workflow_stage
        handoff = Handoff(
            from_stage=self._last_workflow_stage,
            to_stage=stage,
            timestamp=time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(now)),
            evidence_url="",
        )
        self._last_workflow_stage = stage
        return WorkflowSnapshot(
            current_stage=stage,
            item_label=focus.title if focus else "",
            state=focus.state if focus else "queued",
            handoffs=(handoff,),
        )


def _assert_loopback(host: str) -> str:
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError(
            f"refusing non-loopback bind ({host}); the dashboard is localhost-only"
        )
    return "127.0.0.1" if host == "localhost" else host


def make_handler(provider: DashboardStateProvider):  # noqa: ANN201
    class Handler(BaseHTTPRequestHandler):
        server_version = "r510-command-center-webui/1.0"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: object) -> None:  # quiet by default
            pass

        def _send_bytes(self, status: int, body: bytes, content_type: str, extra: Optional[dict] = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Security-Policy", CSP_POLICY)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 -- stdlib signature
            path = self.path.split("?", 1)[0]
            if path == "/api/state":
                body = json.dumps(provider.state().to_dict()).encode("utf-8")
                self._send_bytes(200, body, CONTENT_TYPES[".json"])
                return
            if path == "/api/stream":
                self._handle_sse()
                return
            if path == "/healthz":
                self._send_bytes(200, b"ok", "text/plain; charset=utf-8")
                return
            if path in ("/", "/index.html"):
                self._serve_static("index.html")
                return
            clean = path.lstrip("/")
            if clean.startswith("static/") and ".." not in clean:
                self._serve_static(clean.removeprefix("static/"))
                return
            self._send_bytes(404, b"not found", "text/plain; charset=utf-8")

        def _serve_static(self, name: str) -> None:
            candidate = (STATIC_DIR / name).resolve()
            try:
                candidate.relative_to(STATIC_DIR.resolve())
            except ValueError:
                self._send_bytes(404, b"not found", "text/plain; charset=utf-8")
                return
            if not candidate.is_file():
                self._send_bytes(404, b"not found", "text/plain; charset=utf-8")
                return
            suffix = candidate.suffix.lower()
            if suffix not in CONTENT_TYPES:
                self._send_bytes(403, b"forbidden", "text/plain; charset=utf-8")
                return
            self._send_bytes(200, candidate.read_bytes(), CONTENT_TYPES[suffix])

        def _handle_sse(self) -> None:
            """Server-sent events with heartbeat; client disconnect ends it."""
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            deadline = time.time() + MAX_SSE_CLIENT_SECONDS
            try:
                while time.time() < deadline:
                    payload = json.dumps(provider.state().to_dict())
                    event = f"event: state\ndata: {payload}\n\n"
                    self.wfile.write(event.encode("utf-8"))
                    self.wfile.flush()
                    time.sleep(SSE_HEARTBEAT_S)
            except (BrokenPipeError, ConnectionResetError, OSError):
                return

        def do_POST(self) -> None:  # noqa: N802
            self._reject_write()

        def do_PUT(self) -> None:  # noqa: N802
            self._reject_write()

        def do_DELETE(self) -> None:  # noqa: N802
            self._reject_write()

        def _reject_write(self) -> None:
            self._send_bytes(405, b"read-only service", "text/plain; charset=utf-8")

    Handler.__name__ = f"DashboardHandler[{provider.config.demo_mode and 'demo' or 'live'}]"
    return Handler


def build_server(config: Optional[WebUIConfig] = None) -> ThreadingHTTPServer:
    cfg = config or WebUIConfig()
    host = _assert_loopback(cfg.host)
    provider = DashboardStateProvider(cfg)
    handler_cls = make_handler(provider)
    server = ThreadingHTTPServer((host, cfg.port), handler_cls)
    server.daemon_threads = True
    return server


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="R510 three-node web dashboard (localhost-only)")
    parser.add_argument("--host", default=DEFAULT_HOST, help="bind address (loopback enforced)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--demo",
        action="store_true",
        help="serve sanitized fixtures only (default when no --live)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="collect live telemetry/GitHub per ~/.config/r510-command-center/webui.toml",
    )
    args = parser.parse_args(argv)

    if args.live:
        from command_center.webui.config import load_webui_config

        config, warnings = load_webui_config()
        for warning in warnings:
            print(f"config warning: {warning}")
        config = WebUIConfig(
            host=config.host,
            port=args.port,
            demo_mode=len(config.nodes) == 0,
            poll_seconds=config.poll_seconds,
            stale_after_s=config.stale_after_s,
            ssh_timeout_s=config.ssh_timeout_s,
            github_enabled=config.github_enabled,
            nodes=config.nodes,
        )
        if config.demo_mode:
            print("no nodes configured; staying in fixture mode")
    else:
        config = WebUIConfig(host=args.host, port=args.port, demo_mode=True)

    server = build_server(config)
    url = f"http://{server.server_address[0]}:{server.server_address[1]}/"
    mode = "fixtures" if config.demo_mode else "live collectors"
    print(f"r510 web dashboard: {url} ({mode}, localhost-only)")
    print("Ctrl+C to stop.")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
