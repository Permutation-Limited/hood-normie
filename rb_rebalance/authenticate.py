"""Interactive Robinhood MCP OAuth authentication helper."""

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import secrets
import threading
import urllib.parse
import webbrowser

from rb_rebalance.oauth import (
    DEFAULT_ENDPOINT, DEFAULT_TOKEN_FILE, OAuthError, authorization_url,
    discover, exchange_code, pkce_pair, register_client, save_token,
)
from rb_rebalance.paths import workspace_path


class CallbackHandler(BaseHTTPRequestHandler):
    result: dict[str, str] = {}
    event = threading.Event()

    def do_GET(self) -> None:
        values = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        type(self).result = {key: items[0] for key, items in values.items() if items}
        type(self).event.set()
        success = "code" in type(self).result
        message = ("Robinhood authorization complete. You may close this tab."
                   if success else "Robinhood authorization failed. Return to the terminal.")
        body = message.encode()
        self.send_response(200 if success else 400)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Authenticate rb-rebalance with Robinhood MCP")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--token-file", default=DEFAULT_TOKEN_FILE)
    parser.add_argument("--timeout", type=int, default=300,
                        help="seconds to wait for browser authorization")
    args = parser.parse_args()
    args.token_file = workspace_path(args.token_file)

    server = HTTPServer(("127.0.0.1", 0), CallbackHandler)
    redirect_uri = f"http://127.0.0.1:{server.server_port}/callback"
    resource_metadata, authorization_metadata = discover(args.endpoint)
    registration = register_client(authorization_metadata, redirect_uri)
    client_id = str(registration["client_id"])
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(32)
    scopes = resource_metadata.get("scopes_supported", ["internal"])
    url = authorization_url(
        authorization_metadata, client_id=client_id, redirect_uri=redirect_uri,
        resource=str(resource_metadata.get("resource", args.endpoint)), state=state,
        challenge=challenge, scope=" ".join(scopes),
    )

    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    print("Opening Robinhood authorization in your browser.")
    print(f"If it does not open, visit:\n\n{url}\n")
    webbrowser.open(url)
    if not CallbackHandler.event.wait(args.timeout):
        server.server_close()
        raise OAuthError("timed out waiting for Robinhood authorization")
    server.server_close()
    result = CallbackHandler.result
    if result.get("state") != state:
        raise OAuthError("OAuth callback state mismatch")
    if "error" in result:
        raise OAuthError(f"Robinhood denied authorization: {result['error']}")
    if "code" not in result:
        raise OAuthError("OAuth callback did not contain an authorization code")
    resource = str(resource_metadata.get("resource", args.endpoint))
    token = exchange_code(
        authorization_metadata, code=result["code"], client_id=client_id,
        redirect_uri=redirect_uri, verifier=verifier, resource=resource,
    )
    save_token(args.token_file, token, client_id=client_id,
               metadata=authorization_metadata, resource=resource)
    print(f"Authorization complete. Token saved securely to {args.token_file}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OAuthError, KeyError) as error:
        print(f"error: {error}")
        raise SystemExit(1)
