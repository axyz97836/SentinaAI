"""Purpose-separated, session-bound CSRF proofs; bearer tokens never leave cookies."""

import hashlib
import hmac
import re
import secrets

TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z")
PREAUTH_SECONDS = 600


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str | None:
    if not TOKEN.fullmatch(token):
        return None
    return hashlib.sha256(token.encode("ascii")).hexdigest()


class CSRF:
    def __init__(self, key: str) -> None:
        self.key = key.encode("utf-8")

    def proof(self, purpose: str, value: str) -> str:
        return hmac.new(self.key, f"{purpose}:{value}".encode(), hashlib.sha256).hexdigest()

    def issue_preauth(self, now: int) -> str:
        value = f"{now}.{new_token()}"
        return f"{value}.{self.proof('preauth-cookie', value)}"

    def valid_preauth(self, value: str, now: int) -> bool:
        if len(value) > 128:
            return False
        parts = value.split(".")
        if len(parts) != 3 or not parts[0].isascii() or not parts[0].isdigit():
            return False
        timestamp, nonce, signature = parts
        if not TOKEN.fullmatch(nonce) or not -5 <= now - int(timestamp) <= PREAUTH_SECONDS:
            return False
        return self.matches(signature, self.proof("preauth-cookie", f"{timestamp}.{nonce}"))

    @staticmethod
    def matches(provided: str, expected: str) -> bool:
        return bool(re.fullmatch(r"[a-f0-9]{64}", provided)) and hmac.compare_digest(
            provided, expected
        )
