# Open Testimony - Development Commands
# Usage: make <target>
#
# Two modes:
#   make dev     — Home dev: Docker infra + local bridge (macOS/MPS)
#   make cloud   — Cloud/prod: full Docker stack including bridge container
#
# Both modes use the same DB, MinIO, nginx, api, and web-ui containers.
# The difference is where the bridge (AI indexing) runs.

COMPOSE         := docker compose
COMPOSE_DEV     := $(COMPOSE) -f docker-compose.yml -f docker-compose.local-bridge.yml
BRIDGE_PID_FILE := .bridge.pid

.PHONY: help dev cloud down up-infra bridge bridge-stop \
        rebuild rebuild-web test test-unit test-api \
        migrate logs status reset

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ========== Modes ==========

dev: ## Start home dev mode (Docker infra + local bridge on macOS)
	@echo "\033[1m--- Home Dev Mode ---\033[0m"
	@echo "Starting Docker infra (no bridge container)..."
	$(COMPOSE_DEV) up -d
	@echo ""
	@echo "Starting local bridge on port 8003..."
	@$(MAKE) bridge
	@echo ""
	@echo "\033[1;32mDev mode ready.\033[0m"
	@echo "  Web UI:  http://localhost:18080"
	@echo "  Bridge:  http://localhost:8003"
	@echo "  Use 'make down' to stop everything."

cloud: ## Start cloud/prod mode (full Docker stack with bridge container)
	@echo "\033[1m--- Cloud Mode ---\033[0m"
	$(COMPOSE) up -d
	@echo ""
	@echo "\033[1;32mCloud mode ready.\033[0m All services running in Docker."

# ========== Infrastructure ==========

down: ## Stop everything (Docker services + local bridge)
	@$(MAKE) bridge-stop 2>/dev/null || true
	$(COMPOSE_DEV) down 2>/dev/null || $(COMPOSE) down

status: ## Show running services and local bridge status
	@echo "\033[1m--- Docker Services ---\033[0m"
	@$(COMPOSE) ps
	@echo ""
	@if [ -f $(BRIDGE_PID_FILE) ] && kill -0 $$(cat $(BRIDGE_PID_FILE)) 2>/dev/null; then \
		echo "\033[1;32mLocal bridge: running (PID $$(cat $(BRIDGE_PID_FILE)))\033[0m"; \
	else \
		echo "\033[33mLocal bridge: not running\033[0m"; \
	fi

logs: ## Tail logs from all Docker services
	$(COMPOSE) logs -f --tail=50

# ========== Local Bridge ==========

bridge: ## Start local bridge in background (macOS/MPS)
	@if [ -f $(BRIDGE_PID_FILE) ] && kill -0 $$(cat $(BRIDGE_PID_FILE)) 2>/dev/null; then \
		echo "Local bridge already running (PID $$(cat $(BRIDGE_PID_FILE)))"; \
	else \
		nohup bash bridge/run-local.sh > bridge/bridge.log 2>&1 & \
		echo $$! > $(BRIDGE_PID_FILE); \
		echo "Local bridge started (PID $$!, log: bridge/bridge.log)"; \
	fi

bridge-stop: ## Stop local bridge
	@if [ -f $(BRIDGE_PID_FILE) ]; then \
		PID=$$(cat $(BRIDGE_PID_FILE)); \
		if kill -0 $$PID 2>/dev/null; then \
			kill $$PID; \
			echo "Stopped local bridge (PID $$PID)"; \
		fi; \
		rm -f $(BRIDGE_PID_FILE); \
	fi
	@lsof -ti :8003 2>/dev/null | xargs kill -9 2>/dev/null || true

bridge-log: ## Tail the local bridge log
	@tail -f bridge/bridge.log

# ========== Build ==========

rebuild: ## Rebuild and restart API + web-ui (dev mode)
	$(COMPOSE_DEV) up -d --build api web-ui
	$(COMPOSE_DEV) restart nginx

rebuild-web: ## Rebuild just the web UI (dev mode)
	$(COMPOSE_DEV) build web-ui
	$(COMPOSE_DEV) up -d web-ui

rebuild-cloud: ## Rebuild all services (cloud mode)
	$(COMPOSE) up -d --build

# ========== Testing ==========

test: ## Run all unit tests (API + bridge, uses test DB)
	./scripts/run-tests.sh

test-api: ## Run API server tests only
	./scripts/run-tests.sh api

test-bridge: ## Run bridge tests only
	./scripts/run-tests.sh bridge

# ========== Database ==========

migrate: ## Run database migrations
	$(COMPOSE) exec db psql -U user -d opentestimony -f /dev/stdin < api-server/migrations/001_add_annotations.sql
	$(COMPOSE) exec db psql -U user -d opentestimony -f /dev/stdin < api-server/migrations/002_add_audit_log.sql
	$(COMPOSE) exec db psql -U user -d opentestimony -f /dev/stdin < api-server/migrations/003_add_users.sql
	$(COMPOSE) exec db psql -U user -d opentestimony -f /dev/stdin < api-server/migrations/004_add_search_indexes.sql
	$(COMPOSE) exec db psql -U user -d opentestimony -f /dev/stdin < api-server/migrations/005_add_pgvector.sql
	$(COMPOSE) exec db psql -U user -d opentestimony -f /dev/stdin < api-server/migrations/006_add_tags_table.sql
	$(COMPOSE) exec db psql -U user -d opentestimony -f /dev/stdin < api-server/migrations/007_upgrade_frame_embedding_dim.sql
	$(COMPOSE) exec db psql -U user -d opentestimony -f /dev/stdin < api-server/migrations/008_add_clip_embeddings.sql

# ========== Reset ==========

reset: ## Reset everything: delete all data, volumes, and restart fresh
	@echo "WARNING: This will DELETE all videos, databases, and object storage!"
	@echo "Press Ctrl+C to cancel, or wait 5 seconds to continue..."
	@sleep 5
	@$(MAKE) bridge-stop 2>/dev/null || true
	$(COMPOSE) down -v
	$(COMPOSE) up -d --build
	@echo "Waiting for services to start..."
	@sleep 8
	$(MAKE) migrate
	@echo "Reset complete. Fresh stack running with empty database."
