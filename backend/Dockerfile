FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258 AS dependencies
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements.txt \
    && useradd --create-home --uid 10001 sentinel

FROM dependencies AS runtime
COPY backend/app ./app
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
USER sentinel
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-server-header", "--no-proxy-headers"]

FROM dependencies AS test
COPY backend/requirements-dev.txt ./requirements-dev.txt
RUN pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements-dev.txt
COPY backend/app ./app
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
COPY backend/pyproject.toml ./pyproject.toml
COPY backend/tests ./tests
COPY infra/scripts/check-infra.py ./check_infra.py
USER sentinel
CMD ["pytest", "-p", "no:cacheprovider"]
