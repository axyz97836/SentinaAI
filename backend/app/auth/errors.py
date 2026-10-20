class AuthError(Exception):
    def __init__(self, status: int, code: str, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after


def unauthorized() -> AuthError:
    return AuthError(401, "UNAUTHENTICATED", "Authentication is required.")


def unavailable() -> AuthError:
    return AuthError(503, "AUTH_UNAVAILABLE", "Authentication is temporarily unavailable.")
