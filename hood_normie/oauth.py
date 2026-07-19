"""OAuth 2.1/PKCE support for the Robinhood MCP server."""

import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import time
from typing import Mapping
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_ENDPOINT = "https://agent.robinhood.com/mcp/trading"
DEFAULT_TOKEN_FILE = ".robinhood-mcp-token.json"


class OAuthError(RuntimeError):
    pass


def json_request(
    url: str, *, data: Mapping[str, object] | None = None
) -> dict[str, object]:
    body = None if data is None else json.dumps(data).encode()
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    return _request(url, body, headers)


def form_request(url: str, data: Mapping[str, object]) -> dict[str, object]:
    body = urllib.parse.urlencode(data).encode()
    return _request(url, body, {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    })


def _request(
    url: str, body: bytes | None, headers: Mapping[str, str]
) -> dict[str, object]:
    request = urllib.request.Request(url, data=body, headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload: object = json.load(response)
            if not isinstance(payload, dict) or not all(
                isinstance(key, str) for key in payload
            ):
                raise OAuthError("OAuth response must be a JSON object")
            return payload
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise OAuthError(f"OAuth HTTP {error.code} from {url}: {detail}") from error
    except (urllib.error.URLError, json.JSONDecodeError) as error:
        raise OAuthError(f"OAuth request failed for {url}: {error}") from error


def discover(endpoint: str) -> tuple[dict[str, object], dict[str, object]]:
    """Discover protected-resource and authorization-server metadata."""
    parsed = urllib.parse.urlsplit(endpoint)
    resource_metadata_url = urllib.parse.urlunsplit((
        parsed.scheme, parsed.netloc,
        "/.well-known/oauth-protected-resource" + parsed.path, "", "",
    ))
    resource = json_request(resource_metadata_url)
    servers = resource.get("authorization_servers", [])
    if not isinstance(servers, list) or not servers or not isinstance(servers[0], str):
        raise OAuthError("protected-resource metadata has no authorization_servers")
    issuer = urllib.parse.urlsplit(servers[0])
    authorization_metadata_url = urllib.parse.urlunsplit((
        issuer.scheme, issuer.netloc,
        "/.well-known/oauth-authorization-server" + issuer.path, "", "",
    ))
    return resource, json_request(authorization_metadata_url)


def register_client(
    metadata: Mapping[str, object], redirect_uri: str
) -> dict[str, object]:
    endpoint = metadata.get("registration_endpoint")
    if not endpoint:
        raise OAuthError("authorization server does not advertise dynamic registration")
    return json_request(str(endpoint), data={
        "client_name": "hood-normie",
        "redirect_uris": [redirect_uri],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    })


def pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def authorization_url(
    metadata: Mapping[str, object], *, client_id: str, redirect_uri: str,
    resource: str, state: str, challenge: str, scope: str,
) -> str:
    endpoint = str(metadata["authorization_endpoint"])
    query = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "resource": resource,
        "scope": scope,
    })
    return endpoint + ("&" if "?" in endpoint else "?") + query


def exchange_code(
    metadata: Mapping[str, object], *, code: str, client_id: str,
    redirect_uri: str, verifier: str, resource: str,
) -> dict[str, object]:
    return form_request(str(metadata["token_endpoint"]), {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_verifier": verifier,
        "resource": resource,
    })


def save_token(path: str, token: Mapping[str, object], *, client_id: str,
               metadata: Mapping[str, object], resource: str) -> None:
    payload = dict(token)
    payload.update({
        "client_id": client_id,
        "token_endpoint": metadata["token_endpoint"],
        "resource": resource,
        "obtained_at": int(time.time()),
    })
    if "expires_in" in token:
        expires_in = token["expires_in"]
        if not isinstance(expires_in, (str, int, float)):
            raise OAuthError("token response contains an invalid expires_in")
        payload["expires_at"] = int(time.time()) + int(expires_in)
    target = Path(path)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2)
            stream.write("\n")
    finally:
        os.chmod(target, 0o600)


def load_access_token(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as stream:
            payload: object = json.load(stream)
    except FileNotFoundError as error:
        raise OAuthError(
            f"token file not found: {path}; run //examples:authenticate first"
        ) from error
    if not isinstance(payload, dict) or not all(isinstance(key, str) for key in payload):
        raise OAuthError(f"token file must contain a JSON object: {path}")
    token: dict[str, object] = payload
    expires_at = token.get("expires_at", 0)
    if not isinstance(expires_at, (int, float)):
        raise OAuthError(f"invalid expires_at in {path}")
    if expires_at <= time.time() + 60:
        refresh = token.get("refresh_token")
        if not refresh:
            raise OAuthError("access token expired and no refresh token was supplied")
        refreshed = form_request(str(token["token_endpoint"]), {
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": token["client_id"],
            "resource": token["resource"],
        })
        if "refresh_token" not in refreshed:
            refreshed["refresh_token"] = refresh
        client_id = token.get("client_id")
        resource = token.get("resource")
        if not isinstance(client_id, str) or not isinstance(resource, str):
            raise OAuthError(f"token file has invalid client metadata: {path}")
        save_token(path, refreshed, client_id=client_id,
                   metadata={"token_endpoint": token["token_endpoint"]},
                   resource=resource)
        token = refreshed
    access_token = token.get("access_token")
    if not access_token:
        raise OAuthError(f"no access_token in {path}")
    return str(access_token)
