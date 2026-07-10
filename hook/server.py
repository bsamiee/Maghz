"""Doppler-webhook redeploy consumer: HMAC-verified change events become durable NDJSON receipts.

Container-standalone stdlib server: POST /hooks/doppler verifies `X-Doppler-Signature`
(sha256 HMAC over the raw body, timing-safe) and appends one receipt row; GET /healthz
reports liveness plus the receipt count. An unset secret rejects every event — the
consumer fails closed, never open.
"""

from datetime import datetime, UTC
import hashlib
import hmac
import http.server
import json
import os
from pathlib import Path
from typing import override


SECRET = os.environ.get("MAGHZ_HOOK_SECRET", "").encode()
PORT = int(os.environ.get("MAGHZ_HOOK_PORT", "9000"))
RECEIPTS = Path(os.environ.get("MAGHZ_HOOK_RECEIPTS", "/data/receipts.ndjson"))
HOOK_PATH = "/hooks/doppler"
MAX_BODY = 200 * 1024


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "maghz-hook"
    protocol_version = "HTTP/1.1"

    def _reply(self, code: int, body: bytes = b"") -> None:
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        if body:
            self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path != "/healthz":
            return self._reply(404)
        count = sum(1 for _ in RECEIPTS.open(encoding="utf-8")) if RECEIPTS.exists() else 0
        return self._reply(200, json.dumps({"status": "ok", "receipts": count}).encode())

    def do_POST(self) -> None:
        if self.path != HOOK_PATH:
            return self._reply(404)
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= MAX_BODY:
            return self._reply(413)
        body = self.rfile.read(length)
        expected = "sha256=" + hmac.new(SECRET, body, hashlib.sha256).hexdigest()
        if not (SECRET and hmac.compare_digest(self.headers.get("X-Doppler-Signature", ""), expected)):
            return self._reply(401)
        RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
        receipt = {"ts": datetime.now(UTC).isoformat(), "event": "doppler.secrets.update", "bytes": len(body)}
        with RECEIPTS.open("a", encoding="utf-8") as ledger:
            ledger.write(json.dumps(receipt) + "\n")
        return self._reply(204)

    @override
    def log_message(self, format: str, *args: object) -> None:
        """Receipts are the ledger; per-request access logs are noise."""


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()  # noqa: S104 - container-internal bind; the host port mapping owns exposure
