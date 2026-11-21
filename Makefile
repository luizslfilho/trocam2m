SHELL := /bin/bash
COMPOSE := docker compose
RUN_API := $(COMPOSE) run --rm --no-deps api
RUN_FRONT := $(COMPOSE) --profile tools run --rm frontend-tools

.PHONY: env up down logs ps test lint fmt migrate seed

## Gera .env a partir do .env.example com senhas aleatórias (não sobrescreve um .env existente)
env: .env
.env:
	@cp .env.example .env
	@for v in POSTGRES_PASSWORD APP_DB_PASSWORD REDIS_PASSWORD; do \
	  sed -i "s/^$$v=$$/$$v=$$(openssl rand -hex 24)/" .env; \
	done
	@echo ".env criado com senhas aleatórias."

## Sobe o ambiente e espera todos os serviços ficarem saudáveis
up: .env
	$(COMPOSE) up -d --build --wait

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

## Testes do back-end com TimescaleDB e Redis reais
test: .env
	$(COMPOSE) up -d --wait timescaledb redis
	$(COMPOSE) run --rm api pytest

## ruff, mypy, ESLint e tsc --noEmit
lint: .env
	$(RUN_API) ruff check .
	$(RUN_API) ruff format --check .
	$(RUN_API) mypy app tests
	$(RUN_FRONT) npm run lint
	$(RUN_FRONT) npm run typecheck

fmt: .env
	$(RUN_API) ruff format .
	$(RUN_API) ruff check --fix .

migrate: .env
	$(COMPOSE) run --rm api alembic upgrade head

seed:
	@echo "seed: placeholder; o seed fictício chega na etapa 8."
