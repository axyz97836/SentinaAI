from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

import anyio
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.responses import Response

from app.auth.body_limit import AuthBodyLimitMiddleware
from app.auth.errors import AuthError, unavailable
from app.auth.routes import router as auth_router
from app.auth.service import AuthService
from app.config import Settings, get_settings
from app.health import DependencyProbe, ReadinessProbe
from app.ingestion.routes import router as ingestion_router
from app.ingestion.service import reconcile
from app.ingestion.storage import PrivateStorage
from app.investigations.routes import router as investigations_router
from app.ml.processing import reconcile_training
from app.ml.routes import router as models_router
from app.observability import configure_logging
from app.scoring.config_routes import router as configuration_router
from app.scoring.routes import router as scoring_router

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


def create_app(
    settings: Settings | None = None,
    probe: ReadinessProbe | None = None,
    auth: AuthService | None = None,
) -> FastAPI:
    configuration = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        dependencies = probe or DependencyProbe(configuration)
        app.state.probe = dependencies
        authentication = auth or AuthService(configuration)
        app.state.auth = authentication
        storage = PrivateStorage(configuration)
        app.state.storage = storage

        async def recover_ingestions() -> None:
            from app.worker import publish_ingestion, publish_training

            while True:
                try:
                    await anyio.to_thread.run_sync(
                        reconcile, authentication.sessions, storage, publish_ingestion
                    )
                    await anyio.to_thread.run_sync(
                        reconcile_training, authentication.sessions, storage, publish_training
                    )
                except Exception:
                    logger.warning(
                        "ingestion recovery unavailable",
                        extra={"action": "ingestion_recovery", "error_code": "UNAVAILABLE"},
                    )
                await anyio.sleep(15)

        try:
            async with anyio.create_task_group() as tasks:
                if configuration.app_env != "test" and auth is None:
                    tasks.start_soon(recover_ingestions)
                try:
                    yield
                finally:
                    tasks.cancel_scope.cancel()
        finally:
            storage.close()
            if auth is None:
                authentication.close()
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
    app.add_middleware(AuthBodyLimitMiddleware)
    app.include_router(auth_router)
    app.include_router(ingestion_router)
    app.include_router(models_router)
    app.include_router(scoring_router)
    app.include_router(configuration_router)
    app.include_router(investigations_router)

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
        if request.url.path in {"/api/v1/auth/login", "/api/v1/auth/logout"}:
            logger.info(
                "authentication outcome",
                extra={
                    "action": "auth_login" if request.url.path.endswith("login") else "auth_logout",
                    "request_id": request.state.request_id,
                    "status": response.status_code,
                },
            )
        return response

    @app.exception_handler(AuthError)
    async def auth_error(request: Request, exc: AuthError) -> JSONResponse:
        response = error_response(request, exc.status, exc.code, exc.message)
        if exc.retry_after is not None:
            response.headers["Retry-After"] = str(exc.retry_after)
        return response

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, _exc: SQLAlchemyError) -> JSONResponse:
        return await auth_error(request, unavailable())

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
