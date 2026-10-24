"""Auth for the addon's TCP socket.

Any local process can connect to 127.0.0.1, so the socket alone proves
nothing. On start the server writes a fresh random token to a file only this
user can read. The token itself never crosses the socket: each side proves it
knows it by signing fresh nonces, then signs every message with a session
key. The path and crypto are mirrored in src/blenderwright/connection.py and
tests keep the two in step.
"""

import hashlib
import hmac
import json
import os
import secrets
import sys

ENV_TOKEN_FILE = "BLENDERWRIGHT_TOKEN_FILE"


def token_path() -> str:
    """Where the token lives: the env override, else the user's config dir."""
    override = os.environ.get(ENV_TOKEN_FILE)
    if override:
        return override
    home = os.path.expanduser("~")
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
    elif sys.platform == "darwin":
        base = os.path.join(home, "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    return os.path.join(base, "blenderwright", "token")


def new_token() -> str:
    return secrets.token_hex(32)


def write_token(token: str) -> None:
    """Write the token readable by this user only, replacing any old file."""
    path = token_path()
    directory = os.path.dirname(path)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    if sys.platform != "win32":
        os.chmod(directory, 0o700)
    # A fresh 0600 file swapped in, so an old file's looser mode never applies
    tmp = f"{path}.{os.getpid()}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(token)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def clear_token() -> None:
    try:
        os.remove(token_path())
    except FileNotFoundError:
        pass


# Challenge-response handshake (protocol 2). Mirrored in
# src/blenderwright/connection.py; tests/test_handshake.py keeps them equal.
PROTOCOL_VERSION = 2


def proof(token: str, role: str, first_nonce: str, second_nonce: str) -> str:
    """HMAC proving knowledge of the token, bound to both nonces and a role."""
    message = f"blenderwright-{role}|{first_nonce}|{second_nonce}".encode("utf-8")
    return hmac.new(token.encode("utf-8"), message, hashlib.sha256).hexdigest()


def session_key(token: str, client_nonce: str, server_nonce: str) -> bytes:
    """Per-connection key for signing commands and replies."""
    message = f"blenderwright-session|{client_nonce}|{server_nonce}".encode("utf-8")
    return hmac.new(token.encode("utf-8"), message, hashlib.sha256).digest()


def message_mac(key: bytes, direction: str, seq: int, body: dict) -> str:
    """Signature over one message body, its direction and its sequence number."""
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    message = f"{direction}|{seq}|".encode("utf-8") + canonical.encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()
