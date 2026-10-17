COMPOSE = docker compose --progress plain --env-file .env -f infra/compose.yaml

.PHONY: env up down status backend-check infra-check outage-check frontend-check browser-check check

env:
	node infra/scripts/setup-env.mjs

up:
	$(COMPOSE) up -d --build --wait --wait-timeout 240

down:
	$(COMPOSE) down

status:
	$(COMPOSE) ps

backend-check:
	$(COMPOSE) --profile checks build backend-checks
	$(COMPOSE) --profile checks run --rm --no-deps backend-checks ruff check --no-cache .
	$(COMPOSE) --profile checks run --rm --no-deps backend-checks ruff format --no-cache --check .
	$(COMPOSE) --profile checks run --rm --no-deps backend-checks mypy --cache-dir=/tmp/mypy-cache app
	$(COMPOSE) --profile checks run --rm --no-deps backend-checks pytest -p no:cacheprovider

infra-check:
	$(COMPOSE) --profile checks run --rm --no-deps backend-checks python check_infra.py

outage-check:
	node infra/scripts/check-stack.mjs

frontend-check:
	$(COMPOSE) build frontend
	$(COMPOSE) run --rm --no-deps frontend npm run check

browser-check:
	cd frontend && npm test

check: backend-check frontend-check infra-check outage-check browser-check
