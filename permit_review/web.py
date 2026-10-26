"""Local web page for reviewing a folder of permit PDFs.

    python -m permit_review.web

Starts a small server on this computer only, and opens the page in your browser. You pick a
folder on the page; the browser sends each PDF here, this server has Claude review it, and the
page shows the results as they come in.
"""

import argparse
import json
import os
import tempfile
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import anthropic
from dotenv import load_dotenv

from permit_review import claude_client
from permit_review.review import review_pdf
from permit_review.scanner import inspect_pdf

# HTML/JS/CSS shipped next to this module. Paths are what the browser requests.
STATIC = Path(__file__).parent / "static"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}
MAX_UPLOAD_BYTES = 40 * 1024 * 1024  # reject huge uploads before writing them to disk


class Handler(BaseHTTPRequestHandler):
    """One request. ThreadingHTTPServer uses a new instance per connection.

    `client` and `port` are copied onto a subclass in make_server() so every
    request shares the same Anthropic client and origin checks.
    """

    # Set by serve(): the Anthropic client (None when no API key is configured) and the port.
    client = None
    port = 0

    def do_GET(self):
        """Serve the page, its assets, or a tiny status JSON the UI uses to warn about a missing key."""
        if not self._host_ok():
            return self._send_json(HTTPStatus.FORBIDDEN, {"error": "Forbidden"})
        path = urlparse(self.path).path
        if path == "/api/status":
            return self._send_json(HTTPStatus.OK, {"api_key_set": self.client is not None})
        if path in STATIC_FILES:
            name, content_type = STATIC_FILES[path]
            return self._send(HTTPStatus.OK, (STATIC / name).read_bytes(), content_type)
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self):
        """Review one uploaded PDF. The browser posts the raw file body to /api/review?name=..."""
        # Only this page may ask for reviews, so other websites can't spend your API credit.
        if not self._host_ok() or self.headers.get("Origin") not in self._allowed_origins():
            return self._send_json(HTTPStatus.FORBIDDEN, {"error": "Forbidden"})
        url = urlparse(self.path)
        if url.path != "/api/review":
            return self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
        if self.client is None:
            return self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "ANTHROPIC_API_KEY is not set."})

        name = parse_qs(url.query).get("name", ["upload.pdf"])[0]
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_UPLOAD_BYTES:
            return self._send_json(HTTPStatus.OK, {"file": name, "error": "PDF is too large (over 40 MB)."})

        # Write the upload to a temp file so inspect_pdf / Claude can read a Path, then delete it.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "upload.pdf"
            path.write_bytes(self.rfile.read(length))
            try:
                entry, _ = review_pdf(self.client, inspect_pdf(path), name)
            except anthropic.AuthenticationError:
                return self._send_json(
                    HTTPStatus.UNAUTHORIZED, {"error": "Your API key was rejected. Check ANTHROPIC_API_KEY in .env."}
                )
        self._send_json(HTTPStatus.OK, entry)

    def _allowed_origins(self):
        """Origins that may POST. Same host as this server, both localhost spellings."""
        return {f"http://localhost:{self.port}", f"http://127.0.0.1:{self.port}"}

    def _host_ok(self):
        """Reject Host headers that aren't this process (blocks some DNS-rebinding tricks)."""
        return self.headers.get("Host") in {f"localhost:{self.port}", f"127.0.0.1:{self.port}"}

    def _send_json(self, status, data):
        self._send(status, json.dumps(data).encode(), "application/json")

    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # keep the terminal quiet; startup already printed the URL


def make_server(port: int, client) -> ThreadingHTTPServer:
    """Bind 127.0.0.1 only: the page is meant for this machine, not the LAN."""
    handler = type("BoundHandler", (Handler,), {"client": client, "port": port})
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def main(argv=None) -> int:
    """Load the API key, start the server, and open a browser unless --no-browser."""
    p = argparse.ArgumentParser(prog="permit_review.web", description="Open the Permit Review page.")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true", help="Don't open the browser automatically")
    args = p.parse_args(argv)

    load_dotenv()
    client = claude_client.make_client() if os.environ.get("ANTHROPIC_API_KEY") else None
    if client is None:
        print("Warning: ANTHROPIC_API_KEY is not set, so reviews will fail. See the README.")

    server = make_server(args.port, client)
    url = f"http://localhost:{args.port}/"
    print(f"Permit Review is running at {url}  (press Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
