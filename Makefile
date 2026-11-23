.PHONY: setup mysql migrate backend frontend mcp dev test lint clean

setup:
	uv sync
	pnpm install

mysql:
	docker compose up -d mysql

migrate:
	uv run --package opslens-api alembic -c backend/alembic.ini upgrade head

backend:
	uv run --package opslens-api uvicorn opslens.main:app --reload --host 127.0.0.1 --port 8000

frontend:
	pnpm --dir frontend dev

mcp:
	uv run --package aws-ops-mcp aws-ops-mcp

dev:
	./scripts/dev.sh

test:
	uv run pytest
	pnpm --dir frontend build

lint:
	uv run ruff check backend mcp-server
	pnpm --dir frontend lint

clean:
	rm -rf frontend/dist .pytest_cache .ruff_cache
