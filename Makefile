.PHONY: test test-backend test-local db-up db-down

## Run every test suite unattended (the documented test command).
test: test-backend

## Backend tests inside Docker against the compose Postgres.
test-backend:
	docker compose --profile test run --rm --build backend-tests

## Backend tests on the host (needs uv); starts only the database container.
test-local: db-up
	cd backend && uv run pytest

db-up:
	docker compose up -d --wait db

db-down:
	docker compose down
