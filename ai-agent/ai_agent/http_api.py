from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable


class _Handler(BaseHTTPRequestHandler):
    server_version = "ai-agent/0.1"

    def _send_json(self, status: int, body: Any) -> None:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        routes: dict[str, Callable[[], Any]] = self.server.routes  # type: ignore[attr-defined]

        if self.path in routes:
            try:
                body = routes[self.path]()
                self._send_json(200, body)
            except Exception as exc:  # pragma: no cover
                self._send_json(500, {"ok": False, "error": str(exc)})
            return

        self._send_json(404, {"ok": False, "error": "not_found"})

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        # Keep container logs clean; findings are written to JSONL.
        return


class HttpApi:
    def __init__(self, host: str, port: int) -> None:
        self._server = ThreadingHTTPServer((host, port), _Handler)
        self._thread: threading.Thread | None = None

    def start(self, routes: dict[str, Callable[[], Any]]) -> None:
        self._server.routes = routes  # type: ignore[attr-defined]

        def _run() -> None:
            self._server.serve_forever(poll_interval=0.5)

        self._thread = threading.Thread(target=_run, name="http-api", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        try:
            self._server.shutdown()
        finally:
            self._server.server_close()


def health_payload(start_time: float) -> dict[str, Any]:
    return {"ok": True, "uptime_s": int(time.time() - start_time)}

