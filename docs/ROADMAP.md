# DjangoAir ERP — Prioritized Development Roadmap

## Iteration 1 — MVP & Priority Core (Current Milestone)
- [x] Architecture analysis, UML class/state/sequence diagrams, API specs, and roadmap docs
- [x] Repository hygiene (`.gitignore`, `.editorconfig`, `LICENSE`, `CONTRIBUTING.md`, PR template, `Makefile`, `README.md`)
- [x] Multi-service Docker Compose stack (PostgreSQL 16, Redis 7, Django 5, Celery 5, Flask Mobile WS, Flask Webhook Mock, Mailpit, Nginx)
- [x] Split environment settings structure (`config/settings/{base,dev,test,prod}.py`)
- [x] `accounts`: Email `User`, `CustomerProfile`, strict hierarchical Staff RBAC (`Gate Manager` < `Check-in Manager` < `Supervisor`), JWT auth
- [x] `fleet` & `flights`: `Airport`, `Airplane`, `SeatType`, `AirplaneSeatConfig`, `Flight`, `Option`, availability engine, `seed_demo_data`
- [x] `bookings`: Transactional seat locking, `Booking`, `Passenger`, `Ticket` (`ticket_code`), `TicketOption`, `Discount`, Personal Cabinet online check-in, Check-in Manager counter check-in + options + luggage fee, Gate Manager boarding
- [x] `payments` (**Optional #1**): Pluggable `EmulatedGatewayProvider`, deterministic test cards, invoices, balance top-ups & cancellation refunds
- [x] `notifications`: Celery async emails for tickets, itemized bill/invoice, auto-provisioned Personal Cabinet credentials, and flight cancellations
- [x] `integrations` + Flask Mocks: Redis Pub/Sub -> Flask-SocketIO Mobile WebSocket API + Celery HMAC-SHA256 -> Flask Webhook Mock
- [x] Two independent Webpack 5 + Vue 3 + Bootstrap 5 SPAs (`/` Customer UI & `/staff/` Staff UI)
- [x] Automated `pytest` suites (Django + both Flask services), `ruff` linting, Webpack build verification, and GitHub Actions CI (`.github/workflows/ci.yml`)

## Iteration 2 — Optional Features & Developer Experience
- [ ] **Optional #2 — Social Login via Google OAuth2**: `django-allauth` / OAuth2 token exchange, `SocialAccount` linking, dev mock fallback, and Customer SPA Google sign-in button
- [ ] Printable PDF tickets, invoices, and QR boarding passes attached to confirmation emails
- [ ] Frontend Vitest component tests + Playwright end-to-end browser tests in CI
- [ ] CD Pipeline (`.github/workflows/cd.yml`) building and publishing versioned Docker images to GHCR

## Iteration 3 — Enterprise Multi-Environment Setup (`test`, `dev`, `staging`, `main`/`prod`) (Completed)
- [x] Dedicated Compose overrides: `docker-compose.dev.yml`, `docker-compose.test.yml`, `docker-compose.staging.yml`, `docker-compose.prod.yml`
- [x] Scoped environment templates: `.env.dev.example`, `.env.test.example`, `.env.staging.example`, `.env.prod.example`
- [x] Hardened non-root containers, `config/settings/staging.py`, Kubernetes-style `/health/live/` & `/health/ready/` probes, `bandit` SAST + `check --deploy` in CI
- [x] Branch promotion workflow (`feat/*` -> `dev` -> `staging` -> `main`) & GHCR multi-environment CD pipeline (`.github/workflows/cd.yml`) documented in [docs/ENVIRONMENTS.md](ENVIRONMENTS.md)

## Iteration 4 — 2026–2027 Production & Career-Differentiating Engineering
- [ ] **Distributed Systems Reliability**: `Idempotency-Key` headers on booking/payment APIs, Transactional Outbox table for guaranteed Redis/Webhook emission, Celery Dead-Letter Queue (DLQ) + exponential backoff retries, webhook timestamp replay protection
- [ ] **SRE-Grade Observability**: OpenTelemetry tracing across Nginx -> Django -> PostgreSQL -> Celery -> Flask services, structured JSON logs with `X-Request-ID`, Prometheus `/metrics` + Grafana dashboards, `/health/live` & `/health/ready` probes
- [ ] **Contract-First Type Safety & Load Testing**: OpenAPI 3.1 -> TypeScript client generation for Vue 3, strict `mypy`, CI security scanning (`bandit`, `pip-audit`, `trivy`, `gitleaks`), and `k6`/`Locust` p95 latency benchmarks
- [ ] **AI-Native Airline Disruption & Rebooking Copilot**: Structured LLM tool-calling over DjangoAir REST APIs + RAG over baggage/fare rules + human-in-the-loop confirmation + automated eval suite
- [ ] **Architecture Decision Records (`docs/adr/`) & Cloud Deployment**: Documented trade-offs plus Terraform/Helm live cloud deployment
