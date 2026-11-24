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

## Iteration 2 — Optional Features & Developer Experience (Completed)
- [x] **Optional #2 — Social Login via Google OAuth2**: `SocialAccount` model, `/api/v1/auth/google/` real ID-token verification + guarded dev mock, and Customer SPA "Continue with Google" flow
- [x] Printable PDF QR boarding passes & itemized PDF invoices downloadable via API/SPA and attached automatically to Celery confirmation emails
- [x] Playwright end-to-end browser test suite (`e2e/`) covering Customer booking/payment/PDFs, Google OAuth2/Personal Cabinet, and Staff RBAC hierarchy in CI
- [x] CD Pipeline (`.github/workflows/cd.yml`) building and publishing versioned Docker images to GHCR

## Iteration 3 — Enterprise Multi-Environment Setup (`test`, `dev`, `staging`, `main`/`prod`) (Completed)
- [x] Dedicated Compose overrides: `docker-compose.dev.yml`, `docker-compose.test.yml`, `docker-compose.staging.yml`, `docker-compose.prod.yml`
- [x] Scoped environment templates: `.env.dev.example`, `.env.test.example`, `.env.staging.example`, `.env.prod.example`
- [x] Hardened non-root containers, `config/settings/staging.py`, Kubernetes-style `/health/live/` & `/health/ready/` probes, `bandit` SAST + `check --deploy` in CI
- [x] Branch promotion workflow (`feat/*` -> `dev` -> `staging` -> `main`) & GHCR multi-environment CD pipeline (`.github/workflows/cd.yml`) documented in [docs/ENVIRONMENTS.md](ENVIRONMENTS.md)

## Iteration 4 — 2026–2027 Production & Career-Differentiating Engineering
- [x] **Distributed Systems Reliability**: `Idempotency-Key` deduplication on booking/payment APIs, Transactional Outbox (`OutboxEvent`) + `transaction.on_commit` Celery relay + Dead-Letter Queue (DLQ) Supervisor replay, webhook `X-DjangoAir-Timestamp` 300s replay-window protection
- [x] **SRE-Grade Observability (Core)**: Structured JSON logging with `X-Request-ID` correlation, Prometheus `/api/v1/metrics/` (HTTP counters/latency histograms + domain counters), Kubernetes-style `/health/live/` & `/health/ready/` probes
- [x] **Architecture Decision Records (`docs/adr/`) & Load Benchmarks (`loadtest/`)**: 4 ADRs (`001`–`004`), `k6` script + concurrent Python benchmark with published RPS & p95 latency metrics, grouped Dependabot v2 config
- [ ] **Distributed Tracing & TypeScript Client Generation**: OpenTelemetry OTLP exporter (Jaeger/Tempo), OpenAPI 3.1 -> TypeScript Vue 3 client generation, `mypy` strict mode, `trivy` container CVE scan
- [ ] **AI-Native Airline Disruption & Rebooking Copilot**: Structured LLM tool-calling over DjangoAir REST APIs + RAG over baggage/fare rules + human-in-the-loop confirmation + automated eval suite
- [ ] **Live Cloud Deployment**: Terraform / Helm / Fly.io live demo deployment
