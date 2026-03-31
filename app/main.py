import json
import os
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


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

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length > 0 else b""
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):  # noqa: N802
        if self.path == "/":
            cfg = _load_config()
            return self._send_text(cfg["greeting"])
        if self.path == "/status":
            return self._send_json({"status": "ok"})
        if self.path == "/logs":
            if not LOG_FILE.exists():
                return self._send_text("", status=200)
            return self._send_text(LOG_FILE.read_text(encoding="utf-8"), status=200)
        return self._send_json({"error": "not found"}, status=404)

    def do_POST(self):  # noqa: N802
        if self.path != "/log":
            return self._send_json({"error": "not found"}, status=404)

        try:
            body = self._read_json_body()
        except Exception:
            return self._send_json({"error": "invalid json"}, status=400)

        msg = body.get("message")
        if not isinstance(msg, str) or not msg.strip():
            return self._send_json({"error": "message must be non-empty string"}, status=400)

        _append_log_line(msg)
        return self._send_json({"written": True})

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
