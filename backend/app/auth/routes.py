from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.auth.crypto import PREAUTH_SECONDS
from app.auth.dependencies import Database, Identity, service, validate_csrf, validate_origin
from app.auth.errors import AuthError
from app.auth.service import Principal

router = APIRouter(prefix="/api/v1/auth")


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    email: str = Field(min_length=3, max_length=254)
    password: SecretStr = Field(min_length=1, max_length=256, repr=False)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not value.isascii() or value.count("@") != 1 or any(c.isspace() for c in value):
            raise ValueError("Invalid email")
        return value


def identity_data(principal: Principal) -> dict[str, object]:
    return {
        "user": {
            "id": str(principal.user_id),
            "email": principal.email,
            "display_name": principal.display_name,
        },
        "organization": {"id": str(principal.organization_id), "name": principal.organization_name},
        "role": principal.role,
    }


def cookie(response: Response, request: Request, name: str, value: str, lifetime: int) -> None:
    response.set_cookie(
        name,
        value,
        max_age=lifetime,
        expires=lifetime,
        path="/",
        httponly=True,
        secure=service(request).settings.auth_cookie_secure,
        samesite="lax",
    )


@router.get("/csrf")
def csrf_token(request: Request, response: Response, db: Database) -> dict[str, str]:
    auth = service(request)
    validate_origin(request, required=False)
    raw = request.cookies.get(auth.settings.session_cookie, "")
    if raw:
        try:
            auth.resolve(db, raw, touch=False)
            return {"csrf_token": auth.csrf.proof("session-header", raw)}
        except AuthError as error:
            if error.status != 401:
                raise
            cookie(response, request, auth.settings.session_cookie, "", 0)
    preauth = auth.csrf.issue_preauth(int(auth.clock().timestamp()))
    cookie(response, request, auth.settings.preauth_cookie, preauth, PREAUTH_SECONDS)
    return {"csrf_token": auth.csrf.proof("preauth-header", preauth)}


@router.post("/login")
def login(
    payload: LoginInput, request: Request, response: Response, db: Database
) -> dict[str, object]:
    auth = service(request)
    validate_csrf(request, login=True)
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise AuthError(415, "JSON_REQUIRED", "Use an application/json request.")
    # Uvicorn ignores forwarded headers; the socket peer is authoritative.
    auth.limiter.admit(request.client.host if request.client else "unknown", payload.email)
    principal, raw = auth.login(
        db,
        payload.email,
        payload.password.get_secret_value(),
        request.cookies.get(auth.settings.session_cookie, ""),
        request.state.request_id,
    )
    cookie(response, request, auth.settings.session_cookie, raw, auth.settings.auth_session_seconds)
    cookie(response, request, auth.settings.preauth_cookie, "", 0)
    return {**identity_data(principal), "csrf_token": auth.csrf.proof("session-header", raw)}


@router.get("/me")
def me(principal: Identity) -> dict[str, object]:
    return identity_data(principal)


@router.post("/logout", status_code=204, response_class=Response)
def logout(request: Request, response: Response, db: Database, principal: Identity) -> Response:
    auth = service(request)
    auth.logout(db, principal, request.state.request_id)
    cookie(response, request, auth.settings.session_cookie, "", 0)
    cookie(response, request, auth.settings.preauth_cookie, "", 0)
    response.status_code = 204
    return response
