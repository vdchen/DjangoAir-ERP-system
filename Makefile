.PHONY: up up-dev down logs migrate seed lint typecheck security test test-env test-backend test-flask test-frontend build-frontend validate-envs smoke e2e benchmark

up:
	docker compose up -d --build

up-dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

down:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down -v

logs:
	docker compose logs -f --tail=100

migrate:
	docker compose exec backend python manage.py migrate

seed:
	docker compose exec backend python manage.py seed_demo_data

lint:
	docker compose run --rm --no-deps backend ruff check .

typecheck:
	docker compose run --rm --no-deps backend mypy apps config

security:
	docker compose run --rm --no-deps backend bandit -r apps config -ll

test-env:
	docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm backend
	docker compose -f docker-compose.yml -f docker-compose.test.yml down -v

test-backend:
	docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test -e COVERAGE_FILE=/tmp/.coverage backend pytest -v --cov=apps --cov-report=term-missing --cov-fail-under=90

test-flask:
	docker compose run --rm --no-deps -e COVERAGE_FILE=/tmp/.coverage mobile_ws pytest -v --cov=app --cov-report=term-missing --cov-fail-under=70
	docker compose run --rm --no-deps -e COVERAGE_FILE=/tmp/.coverage webhook_mock pytest -v --cov=app --cov-report=term-missing --cov-fail-under=90

test-frontend:
	cd frontend && npm test

test: test-backend test-flask test-frontend

validate-envs:
	docker compose config -q
	docker compose -f docker-compose.yml -f docker-compose.dev.yml config -q
	docker compose -f docker-compose.yml -f docker-compose.test.yml config -q
	docker compose -f docker-compose.yml -f docker-compose.staging.yml config -q
	docker compose -f docker-compose.yml -f docker-compose.prod.yml config -q

build-frontend:
	cd frontend && npm ci && npm run build

smoke:
	python3 scripts/e2e_smoke.py

e2e:
	cd e2e && npm install && npx playwright install chromium && npx playwright test

benchmark:
	python3 loadtest/benchmark.py --requests 200 --concurrency 16
