import json
import os
import time
from dataclasses import asdict
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .engine import IncidentEngine

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
ENGINE = IncidentEngine()
STARTED = time.time()
STATS = {"analyses": 0, "feedback": 0}

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def _json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.send_header("x-content-type-options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/healthz": return self._json({"status": "ok", "model": "ready"})
        if self.path == "/api/metrics": return self._json({**STATS, "uptimeSeconds": round(time.time() - STARTED), "classes": list(ENGINE.model.classes_)})
        return super().do_GET()

    def do_POST(self):
        try:
            length = int(self.headers.get("content-length", 0))
            if length > 8192: return self._json({"error": "Request too large"}, 413)
            body = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/api/analyze":
                result = ENGINE.analyze(body.get("text", ""))
                STATS["analyses"] += 1
                return self._json(asdict(result))
            if self.path == "/api/feedback":
                if body.get("correct") not in (True, False): raise ValueError("Feedback must be true or false")
                STATS["feedback"] += 1
                return self._json({"recorded": True})
            return self._json({"error": "Not found"}, 404)
        except (ValueError, json.JSONDecodeError) as error:
            return self._json({"error": str(error)}, 400)

    def log_message(self, fmt, *args):
        print(json.dumps({"event": "http", "message": fmt % args}))

def main():
    port = int(os.environ.get("PORT", "8090"))
    print(f"SignalDesk listening on http://0.0.0.0:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()

if __name__ == "__main__": main()

