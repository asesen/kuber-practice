import json
import os
import socket
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from prometheus_client import Counter, Histogram, CONTENT_TYPE_LATEST, generate_latest


def _load_config() -> dict:
    config_dir = Path(os.environ.get("APP_CONFIG_DIR", "/app/config"))
    config_path = config_dir / "config.json"

    greeting = os.environ.get("APP_GREETING", "Welcome to the custom app")
    log_level = os.environ.get("APP_LOG_LEVEL", "info")

    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            greeting = str(cfg.get("greeting", greeting))
            log_level = str(cfg.get("log_level", log_level))
        except Exception:
            pass

    return {"greeting": greeting, "log_level": log_level}


LOG_DIR = Path(os.environ.get("APP_LOG_DIR", "/app/logs"))
LOG_FILE = LOG_DIR / "app.log"

REQUEST_COUNT = Counter(
    "custom_app_requests_total",
    "Total number of HTTP requests handled by the app",
    ["endpoint", "method", "status"],
)
LOG_SUCCESS_COUNT = Counter(
    "custom_app_log_success_total",
    "Successful /log requests",
)
LOG_FAILURE_COUNT = Counter(
    "custom_app_log_failure_total",
    "Failed /log requests",
)
REQUEST_DURATION_SECONDS = Histogram(
    "custom_app_request_duration_seconds",
    "Request duration in seconds",
    ["endpoint", "method", "status"],
)


def _append_log_line(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = message.rstrip("\n") + "\n"
    LOG_FILE.open("a", encoding="utf-8").write(line)
    print(f"app.log: {message}", flush=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "custom-app/1.0"

    def _send_json(self, obj: dict, status: int = 200) -> None:
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("X-Pod-Hostname", socket.gethostname())
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, text: str, status: int = 200) -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("X-Pod-Hostname", socket.gethostname())
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _record_metrics(self, endpoint: str, status: int) -> None:
        duration = time.monotonic() - getattr(self, "_start_time", time.monotonic())
        REQUEST_COUNT.labels(endpoint=endpoint, method=self.command, status=str(status)).inc()
        REQUEST_DURATION_SECONDS.labels(endpoint=endpoint, method=self.command, status=str(status)).observe(duration)
        if endpoint == "/log":
            if status == 200:
                LOG_SUCCESS_COUNT.inc()
            else:
                LOG_FAILURE_COUNT.inc()

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b""
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):  # noqa: N802
        self._start_time = time.monotonic()
        if self.path == "/metrics":
            data = generate_latest()
            self.send_response(200)
            self.send_header("Content-Type", CONTENT_TYPE_LATEST)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if self.path == "/":
            cfg = _load_config()
            self._send_text(cfg["greeting"])
            self._record_metrics("/", 200)
            return
        if self.path == "/status":
            self._send_json({"status": "ok"})
            self._record_metrics("/status", 200)
            return
        if self.path == "/logs":
            if not LOG_FILE.exists():
                self._send_text("", status=200)
                self._record_metrics("/logs", 200)
                return
            self._send_text(LOG_FILE.read_text(encoding="utf-8"), status=200)
            self._record_metrics("/logs", 200)
            return
        self._send_json({"error": "not found"}, status=404)
        self._record_metrics(self.path, 404)

    def do_POST(self):  # noqa: N802
        self._start_time = time.monotonic()
        if self.path != "/log":
            self._send_json({"error": "not found"}, status=404)
            self._record_metrics(self.path, 404)
            return

        try:
            body = self._read_json_body()
        except Exception:
            self._send_json({"error": "invalid json"}, status=400)
            self._record_metrics("/log", 400)
            return

        msg = body.get("message")
        if not isinstance(msg, str) or not msg.strip():
            self._send_json({"error": "message must be non-empty string"}, status=400)
            self._record_metrics("/log", 400)
            return

        _append_log_line(msg)
        self._send_json({"written": True})
        self._record_metrics("/log", 200)
        return

    def log_message(self, format, *args):  # noqa: A002
        cfg = _load_config()
        if str(cfg.get("log_level", "info")).lower() in {"debug", "info"}:
            super().log_message(format, *args)


def main() -> None:
    port = int(os.environ.get("APP_PORT", "8080"))
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"listening on :{port}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
