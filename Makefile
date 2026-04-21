# SmartClinic — developer entry points.
#
# Every target is idempotent; targets that shell out to docker compose assume a
# working Docker daemon and a populated .env file (see .env.example).

SHELL := bash
.ONESHELL:
.DEFAULT_GOAL := help

COMPOSE ?= docker compose
UV      ?= uv
PYTEST  ?= $(UV) run pytest

# --- meta --------------------------------------------------------------------

.PHONY: help
help:  ## show this help
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n\nTargets:\n"} \
		/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

# --- environment -------------------------------------------------------------

.PHONY: env
env:  ## create .env from .env.example if missing
	@test -f .env || cp .env.example .env
	@echo ".env ready"

.PHONY: install
install:  ## sync uv workspace dependencies
	$(UV) sync --all-extras

# --- docker stack ------------------------------------------------------------

.PHONY: up
up: env  ## start the full production-like stack
	$(COMPOSE) up -d --build
	@echo
	@echo "Waiting for core services to become healthy..."
	$(COMPOSE) ps

.PHONY: down
down:  ## stop the stack (keeps volumes)
	$(COMPOSE) down

.PHONY: nuke
nuke:  ## stop the stack AND delete all named volumes (destructive)
	$(COMPOSE) down -v

.PHONY: ps
ps:  ## show container status
	$(COMPOSE) ps

.PHONY: logs
logs:  ## tail all container logs
	$(COMPOSE) logs -f --tail=200

.PHONY: rebuild
rebuild:  ## rebuild service images without cache
	$(COMPOSE) build --no-cache

# --- quality gates -----------------------------------------------------------

.PHONY: lint
lint:  ## ruff lint
	$(UV) run ruff check .

.PHONY: fmt
fmt:  ## ruff format
	$(UV) run ruff format .

.PHONY: typecheck
typecheck:  ## mypy strict on shared_kernel + services
	$(UV) run mypy libs/shared_kernel/src services

.PHONY: test
test:  ## run unit + integration tests
	$(PYTEST)

.PHONY: test-unit
test-unit:  ## unit tests only (skip docker-dependent tests)
	$(PYTEST) -m "not integration" -q

.PHONY: test-unit-cov
test-unit-cov:  ## unit tests with coverage report
	$(PYTEST) -m "not integration" --cov --cov-report=term-missing --cov-report=xml -q

.PHONY: fitness
fitness:  ## run architectural fitness-function tests
	$(PYTEST) -m fitness -q

.PHONY: coverage
coverage:  ## run tests with coverage report
	$(PYTEST) --cov --cov-report=term-missing --cov-report=xml

.PHONY: precommit
precommit:  ## install pre-commit hooks
	$(UV) run pre-commit install

# --- utilities ---------------------------------------------------------------

.PHONY: adr-new
adr-new:  ## create a new ADR: make adr-new TITLE="my decision"
	@test -n "$(TITLE)" || (echo "usage: make adr-new TITLE=\"...\"" && exit 2)
	@NEXT=$$(ls docs/adr/*.md 2>/dev/null | grep -oE '[0-9]{4}' | sort -n | tail -1); \
		NEXT=$$(printf '%04d' $$((10#$$NEXT + 1))); \
		SLUG=$$(echo "$(TITLE)" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]\+/-/g; s/^-//; s/-$$//'); \
		FILE="docs/adr/$${NEXT}-$${SLUG}.md"; \
		cp docs/adr/_template.md "$$FILE"; \
		sed -i "s/Title/$(TITLE)/; s/Status: .*/Status: Proposed/" "$$FILE"; \
		echo "created $$FILE"

# --- per-service shortcuts ---------------------------------------------------

SERVICES := clinical pharmacy laboratory billing saga_orchestrator

.PHONY: test-service
test-service:  ## run tests for one service: make test-service SVC=clinical
	@test -n "$(SVC)" || (echo "usage: make test-service SVC=<service_name>" && exit 2)
	$(PYTEST) services/$(SVC)/tests -m "not integration" -q

.PHONY: test-all-services
test-all-services:  ## run unit tests for every bounded context
	$(PYTEST) $(foreach s,$(SERVICES),services/$(s)/tests) -m "not integration" -q

.PHONY: logs-service
logs-service:  ## tail logs for one service: make logs-service SVC=clinical
	@test -n "$(SVC)" || (echo "usage: make logs-service SVC=<service_name>" && exit 2)
	$(COMPOSE) logs -f --tail=200 $(SVC)

.PHONY: shell
shell:  ## open a Python shell with the workspace packages available
	$(UV) run python

.PHONY: seed
seed:  ## run database seed scripts (idempotent)
	@echo "Seed not yet implemented — run make up to auto-create tables."

.PHONY: infra-up
infra-up: env  ## start only the infrastructure layer (no bounded-context services)
	$(COMPOSE) up -d postgres rabbitmq keycloak otel-collector jaeger prometheus loki grafana mailhog

.PHONY: infra-down
infra-down:  ## stop only the infrastructure layer
	$(COMPOSE) stop postgres rabbitmq keycloak otel-collector jaeger prometheus loki grafana mailhog

.PHONY: services-up
services-up:  ## start only the bounded-context services (requires infra-up first)
	$(COMPOSE) up -d clinical pharmacy laboratory billing saga_orchestrator

.PHONY: health
health:  ## check health of all running services
	@for port in 8003 8004 8005 8006 8007; do \
		echo -n "http://localhost:$${port}/health/live ... "; \
		curl -sf http://localhost:$${port}/health/live > /dev/null && echo "OK" || echo "FAIL"; \
	done

.PHONY: ci
ci: lint typecheck test-unit fitness  ## run the full local CI pipeline (no Docker)
