# Open Testimony - Development Commands
# Usage: make <target>

API_BASE_URL ?= http://localhost:18080/api

.PHONY: help test test-api test-flutter test-verbose up down rebuild migrate lint reset

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------- Testing ----------

test: test-api test-flutter ## Run all tests

test-api: ## Run API integration tests (requires Docker stack running)
	cd tests && API_BASE_URL=$(API_BASE_URL) python3 -m pytest -v --tb=short

test-verbose: ## Run API tests with full output
	cd tests && API_BASE_URL=$(API_BASE_URL) python3 -m pytest -v --tb=long -s

test-flutter: ## Run Flutter analyze
	cd mobile-app && flutter analyze

# ---------- Infrastructure ----------

up: ## Start all Docker services
	docker compose up -d

down: ## Stop all Docker services
	docker compose down

rebuild: ## Rebuild and restart API + web-ui containers
	docker compose up -d --build api web-ui && docker compose restart nginx

migrate: ## Run database migrations
	docker compose exec db psql -U user -d opentestimony -f /dev/stdin < api-server/migrations/001_add_annotations.sql
	docker compose exec db psql -U user -d opentestimony -f /dev/stdin < api-server/migrations/002_add_audit_log.sql
	docker compose exec db psql -U user -d opentestimony -f /dev/stdin < api-server/migrations/003_add_users.sql

# ---------- Setup ----------

install-test-deps: ## Install Python test dependencies
	pip3 install -r tests/requirements.txt

lint: test-flutter ## Alias for test-flutter

reset: ## Reset everything: delete all data, volumes, and restart fresh
	@echo "⚠️  This will DELETE all videos, databases, and object storage!"
	@echo "Press Ctrl+C to cancel, or wait 5 seconds to continue..."
	@sleep 5
	docker compose down -v
	docker compose up -d --build
	@echo "Waiting for services to start..."
	@sleep 8
	$(MAKE) migrate
	@echo "✅ Reset complete. Fresh stack running with empty database."
