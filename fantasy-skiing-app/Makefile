.PHONY: up down rebuild api-logs web-logs db-shell test-api

# Start all services
up:
	docker compose up -d

# Stop all services
down:
	docker compose down

# Rebuild and restart
rebuild:
	docker compose build --no-cache api web
	docker compose up -d

# View API logs
api-logs:
	docker compose logs -f api

# View web dashboard logs
web-logs:
	docker compose logs -f web

# Database shell
db-shell:
	docker compose exec db psql -U fantasy -d fantasy_skiing

# Run API directly (development without Docker)
api-dev:
	cd api-server && uvicorn main:app --host 0.0.0.0 --port 8001 --reload

# Run web dashboard directly (development without Docker)
web-dev:
	cd web-dashboard && npm start

# Reset database
reset:
	docker compose down -v
	docker compose up -d
