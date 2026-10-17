from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.responses import Response

from app.config import Settings, get_settings
from app.health import DependencyProbe, ReadinessProbe
from app.observability import configure_logging

logger = configure_logging()


def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request.state.request_id,
                "field_errors": {},
            }
        },
    )


def create_app(settings: Settings | None = None, probe: ReadinessProbe | None = None) -> FastAPI:
    configuration = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        dependencies = probe or DependencyProbe(configuration)
        app.state.probe = dependencies
        try:
            yield
        finally:
            if isinstance(dependencies, DependencyProbe):
                dependencies.close()

    app = FastAPI(
        title="SentinelAI local foundation",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = str(uuid4())
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            response = error_response(
                request, 500, "INTERNAL_ERROR", "Request could not be completed."
            )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        logger.info(
            "request completed",
            extra={
                "action": "http_request",
                "request_id": request.state.request_id,
                "status": response.status_code,
                "elapsed_ms": round((perf_counter() - started) * 1000),
            },
        )
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        return error_response(request, exc.status_code, code, "Request is not available.")

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _exc: RequestValidationError) -> JSONResponse:
        return error_response(request, 422, "VALIDATION_ERROR", "Request validation failed.")

    @app.get("/api/v1/health/live")
    def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/api/v1/health/ready", response_model=None)
    def ready(request: Request) -> dict[str, str] | JSONResponse:
        readiness: ReadinessProbe = request.app.state.probe
        if not readiness.ready():
            return error_response(
                request, 503, "DEPENDENCY_UNAVAILABLE", "Service is not ready. Try again shortly."
            )
        return {"status": "ready"}

    return app
