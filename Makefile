COMPOSE = docker compose --progress plain --env-file .env -f infra/compose.yaml
DATABASE_COMPOSE = $(COMPOSE) -f infra/compose.database.yaml --profile database

.PHONY: env auth-env auth-cleanup up down status backend-check infra-check outage-check ingestion-check frontend-check browser-check check database-setup migrate seed database-check

env:
	node infra/scripts/setup-env.mjs
	node infra/scripts/setup-auth-env.mjs

auth-env:
	node infra/scripts/setup-auth-env.mjs

up: auth-env
	$(COMPOSE) up -d --build --wait --wait-timeout 240

down:
	$(COMPOSE) down

status:
	$(COMPOSE) ps

auth-cleanup:
	$(COMPOSE) exec -T api python -m app.auth.cleanup

backend-check:
	$(COMPOSE) --profile checks build backend-checks
	$(COMPOSE) --profile checks run --rm --no-deps backend-checks ruff check --no-cache .
	$(COMPOSE) --profile checks run --rm --no-deps backend-checks ruff format --no-cache --check .
	$(COMPOSE) --profile checks run --rm --no-deps backend-checks mypy --cache-dir=/tmp/mypy-cache app
	$(COMPOSE) --profile checks run --rm --no-deps backend-checks pytest -p no:cacheprovider -m "not database"

infra-check:
	$(COMPOSE) --profile checks run --rm --no-deps backend-checks python check_infra.py

outage-check:
	node infra/scripts/check-stack.mjs

ingestion-check:
	node infra/scripts/check-ingestion.mjs

.PHONY: model-check
model-check:
	node infra/scripts/check-ingestion.mjs --models

frontend-check:
	$(COMPOSE) build frontend
	$(COMPOSE) run --rm --no-deps frontend npm run check

browser-check:
	cd frontend && npm test

database-setup:
	node infra/scripts/setup-database.mjs

migrate: database-setup
	$(DATABASE_COMPOSE) run --rm --no-deps --build migration

seed: migrate
	$(COMPOSE) run --rm --no-deps --build --user "$$(id -u):$$(id -g)" -v "$(CURDIR)/.local/demo:/run/demo" api python -m app.seed

database-check:
	node infra/scripts/check-database.mjs

check: backend-check frontend-check database-check infra-check outage-check ingestion-check model-check browser-check
