.PHONY: up down logs migrate seed test test-backend test-flask lint build-frontend smoke

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=100

migrate:
	docker compose exec backend python manage.py migrate

seed:
	docker compose exec backend python manage.py seed_demo_data

lint:
	docker compose run --rm backend ruff check .

test-backend:
	docker compose run --rm -e DJANGO_SETTINGS_MODULE=config.settings.test backend pytest -v --cov=apps --cov-report=term-missing

test-flask:
	docker compose run --rm mobile_ws pytest -v
	docker compose run --rm webhook_mock pytest -v

test: test-backend test-flask

build-frontend:
	cd frontend && npm ci && npm run build

smoke:
	python3 scripts/e2e_smoke.py
