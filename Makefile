.PHONY: up down test test-backend test-e2e test-local rules-report reset db-up

APP_NOW ?= 2026-11-11T15:00:00Z

## Start the whole stack with seed data loaded.
up:
	docker compose up --build

down:
	docker compose down

## Run every test suite unattended (the documented test command).
test: test-backend test-e2e

## Backend tests inside Docker against the compose Postgres.
test-backend:
	docker compose --profile test run --rm --build backend-tests

## Two-browser Playwright test against the full stack (started if needed).
test-e2e:
	docker compose up -d --build --wait frontend
	docker compose --profile test run --rm --build e2e

## Backend tests on the host (needs uv); starts only the database container.
test-local: db-up
	cd backend && uv run pytest

## Print the rules report (JSON) for a freshly seeded database at APP_NOW.
## Uses a throwaway database, so the app's data is untouched.
## Another date: make rules-report APP_NOW=2026-11-16T15:00:00Z
rules-report: db-up
	@docker compose run --rm --no-deps -e APP_NOW=$(APP_NOW) backend python -m app.cli rules-report --fresh

## Reset the app database to the seed (drops everything users added) and restart the API,
## so the app clock starts again at APP_NOW.
reset: db-up
	docker compose run --rm --no-deps backend python -m app.cli reset
	docker compose restart backend

db-up:
	docker compose up -d --wait db
