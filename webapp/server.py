"""Local web server for the hood-normie single-page app.

Serves the Vite bundle as static files and exposes the rebalance report as JSON.
Read-only, like everything else in this repo: it computes and reports, and has no
endpoint that could place an order.

The listener binds to the loopback interface only. The report contains account
numbers, balances, and positions, and there is no authentication in front of it,
so it must never be reachable from another machine.
"""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
import posixpath
import sys
import threading
from typing import Callable
from urllib.parse import unquote, urlparse

from examples.paths import workspace_path
from examples.rebalance.report import DEFAULT_ENDPOINT, Report, build_report
from hood_normie.oauth import DEFAULT_TOKEN_FILE, OAuthError
from webapp.api import report_json


DEFAULT_PORT = 8765
DEFAULT_CONFIG = "config.yaml"
INDEX = "index.html"

ReportBuilder = Callable[[], Report]


class Handler(BaseHTTPRequestHandler):
    """Static assets plus the JSON API. Only GET is supported."""

    server_version = "hood-normie"
    sys_version = ""

    static_root: str
    build: ReportBuilder
    # One live fetch at a time: concurrent refreshes would multiply Robinhood
    # requests for no benefit, since every caller wants the same snapshot.
    lock = threading.Lock()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/rebalance":
            self.serve_report()
        elif path.startswith("/api/"):
            self.send_json({"error": f"unknown endpoint {path}"}, status=404)
        else:
            self.serve_static(path)

    def serve_report(self) -> None:
        try:
            with self.lock:
                payload = report_json(self.build())
        except (ValueError, KeyError) as error:
            self.send_json({"error": str(error)}, status=400)
        except OAuthError as error:
            self.send_json(
                {"error": f"{error}. Re-authenticate with "
                          "`bazel run //examples:authenticate`."},
                status=401,
            )
        except OSError as error:
            self.send_json({"error": f"could not reach Robinhood: {error}"}, status=502)
        else:
            self.send_json(payload)

    def serve_static(self, path: str) -> None:
        target = self.resolve(path)
        if target is None:
            self.send_json({"error": "not found"}, status=404)
            return
        try:
            with open(target, "rb") as stream:
                body = stream.read()
        except OSError:
            self.send_json({"error": "not found"}, status=404)
            return
        content_type = mimetypes.guess_type(target)[0] or "application/octet-stream"
        self.respond(body, content_type)

    def resolve(self, path: str) -> str | None:
        """Map a URL path to a file inside the static root, or None."""
        relative = posixpath.normpath(unquote(path)).lstrip("/")
        candidate = os.path.realpath(os.path.join(self.static_root, relative))
        root = os.path.realpath(self.static_root)
        # normpath already collapses "..", but a symlink inside the bundle could
        # still point outside it.
        if not (candidate == root or candidate.startswith(root + os.sep)):
            return None
        if os.path.isfile(candidate):
            return candidate
        # Client-side routes such as /rebalance are not files: the app renders
        # them, so hand back the shell. Missing assets still 404.
        if os.path.splitext(relative)[1]:
            return None
        return os.path.join(root, INDEX)

    def send_json(self, payload: object, status: int = 200) -> None:
        self.respond(json.dumps(payload).encode(), "application/json", status)

    def respond(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # Live brokerage data: never let a proxy or the browser keep a copy.
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write(f"{self.address_string()} {format % args}\n")


def make_handler(static_root: str, build: ReportBuilder) -> type[Handler]:
    return type("BoundHandler", (Handler,), {
        "static_root": static_root, "build": staticmethod(build),
    })


def default_static_root() -> str:
    """Locate the Vite bundle in Bazel runfiles, falling back to the source tree."""
    runfiles = os.environ.get("RUNFILES_DIR")
    if runfiles:
        candidate = os.path.join(runfiles, "_main", "webapp", "frontend", "dist")
        if os.path.isdir(candidate):
            return candidate
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--config", default=DEFAULT_CONFIG,
                        help=f"target allocation YAML (default: {DEFAULT_CONFIG})")
    parser.add_argument("--token-file", default=DEFAULT_TOKEN_FILE)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--static", default=None,
                        help="directory of built SPA assets")
    parser.add_argument("--verbose", action="store_true",
                        help="print MCP JSON-RPC traffic to stderr")
    args = parser.parse_args()

    config_path = workspace_path(args.config)
    token_file = workspace_path(args.token_file)
    static_root = args.static or default_static_root()
    if not os.path.isfile(os.path.join(static_root, INDEX)):
        print(f"error: no {INDEX} in {static_root}; build //webapp/frontend:dist first",
              file=sys.stderr)
        return 2

    def build() -> Report:
        return build_report(
            config_path=config_path, token_file=token_file,
            endpoint=args.endpoint, verbose=args.verbose,
        )

    server = ThreadingHTTPServer(("127.0.0.1", args.port),
                                 make_handler(static_root, build))
    url = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"hood-normie serving {static_root}")
    print(f"open {url} — read-only, loopback only. Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
