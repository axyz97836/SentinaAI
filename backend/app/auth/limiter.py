"""Atomic fixed-window attempt budgets. All keys expire; no raw identifiers in Redis."""

from typing import cast

from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

from app.auth.crypto import CSRF
from app.auth.errors import AuthError, unavailable
from app.config import Settings

# Admission and both counters are one atomic operation. Counting all attempts also
# bounds successful-login abuse and expensive Argon2 work; success cannot reset it.
ADMIT = """
for i = 1, 2 do
    if tonumber(redis.call('GET', KEYS[i]) or '0') >= tonumber(ARGV[i]) then
        return math.max(1, redis.call('TTL', KEYS[i]))
    end
end
for i = 1, 2 do
    if redis.call('INCR', KEYS[i]) == 1 then redis.call('EXPIRE', KEYS[i], ARGV[3]) end
end
return 0
"""


class LoginLimiter:
    def __init__(self, settings: Settings, csrf: CSRF, namespace: str = "sentinel:login"):
        self.settings = settings
        self.csrf = csrf
        self.namespace = namespace
        self.client: Redis = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password.get_secret_value(),
            db=1,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry=Retry(NoBackoff(), 0),
        )

    def admit(self, peer: str, email: str) -> None:
        keys = [
            f"{self.namespace}:ip:{self.csrf.proof('rate-ip', peer)}",
            f"{self.namespace}:account:{self.csrf.proof('rate-account', email)}",
        ]
        try:
            result = self.client.eval(
                ADMIT,
                2,
                *keys,
                str(self.settings.auth_login_ip_limit),
                str(self.settings.auth_login_account_limit),
                str(self.settings.auth_login_window_seconds),
            )
            # redis-py's shared sync/async annotation includes Awaitable; this
            # client is exclusively synchronous and Lua returns an integer.
            retry_after = int(cast(int, result))
        except RedisError:
            raise unavailable() from None
        if retry_after:
            raise AuthError(429, "LOGIN_LIMITED", "Try again later.", retry_after)

    def close(self) -> None:
        self.client.close()
