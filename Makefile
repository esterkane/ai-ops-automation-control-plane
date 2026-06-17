# ai-ops-automation-control-plane :: developer shortcuts
# Usage: make up | make down | make logs | make seed

COMPOSE = docker compose

.PHONY: help up down logs seed ps restart test fmt

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-10s %s\n", $$1, $$2}'

up: ## Build and start the full stack (detached)
	@if [ ! -f .env ]; then echo ".env missing — run: cp .env.example .env"; exit 1; fi
	$(COMPOSE) up --build -d
	@echo ""
	@echo "n8n      -> http://localhost:5678  (basic auth: see .env)"
	@echo "tools    -> http://localhost:8088  (docs: http://localhost:8088/docs)"
	@echo "postgres -> localhost:55432        (db/user: see .env)"

down: ## Stop and remove containers (keeps volumes)
	$(COMPOSE) down

logs: ## Tail logs from all services
	$(COMPOSE) logs -f --tail=100

ps: ## Show service status
	$(COMPOSE) ps

restart: ## Restart all services
	$(COMPOSE) restart

seed: ## Load seed knowledge base + sample data into the tools service
	$(COMPOSE) exec tools python -m app.seed

test: ## Run the tools service test suite
	$(COMPOSE) exec tools pytest -q

fmt: ## Lint + type-check the tools service
	$(COMPOSE) exec tools sh -c "ruff check . && mypy app"
