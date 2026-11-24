.PHONY: up up-dev down logs migrate seed lint security test test-env test-backend test-flask build-frontend validate-envs smoke

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

security:
	docker compose run --rm --no-deps backend bandit -r apps config -ll

test-env:
	docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm backend
	docker compose -f docker-compose.yml -f docker-compose.test.yml down -v

test-backend:
	docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test backend pytest -v --cov=apps --cov-report=term-missing

test-flask:
	docker compose run --rm --no-deps mobile_ws pytest -v
	docker compose run --rm --no-deps webhook_mock pytest -v

test: test-backend test-flask

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
