COMPOSE ?= docker compose
PROJECT ?= saas-futebol

.PHONY: help build up down restart logs shell bash migrate makemigrations createsuperuser test ps clean seed-demo

help:
	@echo "Comandos disponíveis:"
	@echo "  make build            # build das imagens"
	@echo "  make up               # sobe os serviços"
	@echo "  make down             # para os serviços"
	@echo "  make restart          # rebuild + up"
	@echo "  make logs             # logs do web"
	@echo "  make shell            # shell dentro do container web"
	@echo "  make bash             # bash dentro do container web"
	@echo "  make migrate          # roda migrations"
	@echo "  make makemigrations   # cria migrations"
	@echo "  make createsuperuser   # cria superuser interativo"
	@echo "  make test             # roda testes"
	@echo "  make seed-demo        # cria o tenant demo local"
	@echo "  make sync-ai-sources  # sincroniza as fontes de IA uma vez"
	@echo "  make watch-ai-sources # sobe o watcher automático de fontes"
	@echo "  make ps               # status dos containers"
	@echo "  make clean            # remove containers e volumes"

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) up -d --build

logs:
	$(COMPOSE) logs -f web

shell:
	$(COMPOSE) run --rm web python src/manage.py shell

bash:
	$(COMPOSE) run --rm web bash

migrate:
	$(COMPOSE) run --rm web python src/manage.py migrate

makemigrations:
	$(COMPOSE) run --rm web python src/manage.py makemigrations

createsuperuser:
	$(COMPOSE) run --rm web python src/manage.py createsuperuser

test:
	$(COMPOSE) run --rm web python src/manage.py test futebol.tests

seed-demo:
	$(COMPOSE) up -d web db
	$(COMPOSE) exec -T web python src/manage.py seed_futebol_demo

sync-ai-sources:
	$(COMPOSE) run --rm ai-sync python scripts/watch_ai_sources.py --project-root /app --vault-root /vault --interval 300 --seed-agent --once

watch-ai-sources:
	$(COMPOSE) up -d ai-sync

ps:
	$(COMPOSE) ps

clean:
	$(COMPOSE) down -v --remove-orphans
