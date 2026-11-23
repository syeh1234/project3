"""Serve the local FigureLab gallery and its JSONL/image API.

Run with: python webapp.py
The server binds to localhost by default; it is intended for local prototyping.
"""

import argparse
import json
import mimetypes
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from config import CHARACTERIZED_JSONL, DATA_DIR, FIGURES_JSONL, PROJECT_ROOT
from utils import read_jsonl


WEB_DIR = PROJECT_ROOT / "web"


def _records():
    source = CHARACTERIZED_JSONL if CHARACTERIZED_JSONL.exists() else FIGURES_JSONL
    if not source.exists():
        return []
    rows = read_jsonl(source)
    result = []
    for row in rows:
        record = dict(row)
        paths = record.get("image_paths") or []
        if not paths and record.get("primary_image_path"):
            paths = [record["primary_image_path"]]
        image_path = paths[0] if paths else ""
        record["image_url"] = (
            "/api/image?path=" + image_path if image_path else ""
        )
        result.append(record)
    return result


class FigureLabHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            return self._json({"ok": True, "data_dir": str(DATA_DIR)})
        if parsed.path == "/api/figures":
            records = _records()
            return self._json({
                "figures": records,
                "count": len(records),
                "source": (
                    "characterized"
                    if CHARACTERIZED_JSONL.exists()
                    else "extracted"
                ),
            })
        if parsed.path == "/api/image":
            params = parse_qs(parsed.query)
            value = params.get("path", [""])[0]
            return self._image(value)
        return super().do_GET()

    def _json(self, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _image(self, value):
        if not value:
            self.send_error(404, "No image path supplied")
            return
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = PROJECT_ROOT / candidate
        try:
            resolved = candidate.resolve()
            resolved.relative_to(DATA_DIR.resolve())
        except (ValueError, OSError):
            self.send_error(403, "Image path is outside the data directory")
            return
        if not resolved.is_file():
            self.send_error(404, "Image file not found")
            return
        content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        try:
            body = resolved.read_bytes()
        except OSError:
            self.send_error(404, "Unable to read image")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("[FigureLab] " + fmt % args)


def main():
    parser = argparse.ArgumentParser(description="Run the local FigureLab gallery.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if not WEB_DIR.exists():
        raise SystemExit(f"Frontend folder not found: {WEB_DIR}")
    server = ThreadingHTTPServer((args.host, args.port), FigureLabHandler)
    print(f"FigureLab is running at http://{args.host}:{args.port}")
    print(f"Reading figure data from: {CHARACTERIZED_JSONL}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping FigureLab.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
