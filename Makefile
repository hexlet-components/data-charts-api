PORT ?= 4000

install:
	uv sync

dev:
	uv run fastapi dev app/server.py --host 0.0.0.0 --port $(PORT)

run:
	uv run uvicorn --workers 1 --host 0.0.0.0 --port $(PORT) app.server:app

compose-setup:
	docker compose run --rm app make install

compose-build:
	docker compose build

compose:
	docker compose up

compose-bash:
	docker compose run --rm app bash

test:
	uv run pytest

lint:
	uv run ruff check .

check: lint
