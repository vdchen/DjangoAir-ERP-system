# DjangoAir ERP System

**DjangoAir** is a containerized Airline Management ERP system uniting customer flight booking, an emulated payment gateway, Personal Cabinet self-service, role-governed airport staff operations, asynchronous Celery email notifications, a real-time Flask-SocketIO mobile WebSocket API, and an HMAC-signed third-party webhook integration.

## Documentation
- [Architecture & Module Decomposition](docs/ARCHITECTURE.md)
- [Architecture Decision Records (ADRs)](docs/adr/README.md)
- [UML Class, State & Sequence Diagrams](docs/UML.md)
- [REST, WebSocket & Webhook API Contracts](docs/API.md)
- [Enterprise Multi-Environment & Branch Promotion Guide](docs/ENVIRONMENTS.md)
- [Prioritized Development Roadmap](docs/ROADMAP.md)
- [Contributing Guidelines](CONTRIBUTING.md)

## Tech Stack
| Layer | Technology |
| :--- | :--- |
| **Core ERP Backend** | Python 3.12, Django 5.2 LTS, Django REST Framework, SimpleJWT, drf-spectacular, ReportLab, Prometheus Client |
| **Mock Microservices** | Flask 3, Flask-SocketIO (`gevent`), HMAC-SHA256 + Replay-Window Webhook Verifier |
| **Database & Cache/Broker** | PostgreSQL 16, Redis 7 |
| **Async Workers & Reliability** | Celery 5, Transactional Outbox + DLQ Replay, `Idempotency-Key` Deduplication, Mailpit |
| **Independent Web Interfaces** | Webpack 5, Vue 3, Bootstrap 5 (separate Customer `/` & Staff `/staff/` SPAs) |
| **Reverse Proxy, Testing & CI/CD** | Nginx 1.27, Docker Compose (`dev`/`test`/`staging`/`prod`), Pytest, Playwright E2E, GitHub Actions + GHCR |

## Quickstart (Docker Compose)

```bash
cp .env.example .env
docker compose up -d --build
```

On startup, the backend automatically runs PostgreSQL migrations and seeds demo airports, airplanes, flights, options, discounts, staff accounts, and webhook subscriptions.

### Service URLs
| Interface / Service | URL |
| :--- | :--- |
| **Customer Web Interface** (3-field search, booking, payment, Personal Cabinet, Google OAuth2, PDFs) | `http://localhost:8080/` |
| **Staff Web Interface** (Gate Manager, Check-in Manager, Supervisor) | `http://localhost:8080/staff/` |
| **Interactive OpenAPI / Swagger Docs** | `http://localhost:8080/api/v1/docs/` |
| **Prometheus Metrics Endpoint** | `http://localhost:8080/api/v1/metrics/` |
| **Flask Mobile WebSocket Mock Client** | `http://localhost:8080/mobile-mock/` |
| **Flask Third-Party Webhook Inspector** | `http://localhost:8080/mock-webhook/` |
| **Mailpit Email Inbox** (inspect tickets, PDF attachments & auto-provisioned credentials) | `http://localhost:8025/` |

## Seeded Demo Accounts & Test Cards

### Staff Hierarchy (Ascending Permissions)
| Level | Role | Email | Password | Capabilities |
| :---: | :--- | :--- | :--- | :--- |
| 1 | **Gate Manager** | `gate@djangoair.local` | `Gate123!` | Board checked-in passengers at gate using `ticket_code` |
| 2 | **Check-in Manager** | `checkin@djangoair.local` | `Checkin123!` | Counter check-in, attach options, collect luggage fee (+ L1) |
| 3 | **Supervisor** | `supervisor@djangoair.local` | `Supervisor123!` | Manage Gate/Check-in staff, create/cancel flights, manage options, replay Outbox DLQ (+ L1 & L2) |

### Customer Demo Account & Promo Codes
- **Customer**: `alice@example.com` / `Customer123!` (pre-loaded with `$250.00` balance, 1 upcoming flight, and 1 previous flight)
- **Google OAuth2 (Dev Mode)**: Click **Continue with Google** in Personal Cabinet (dev mock enabled in `dev`/`test`, strictly disabled in `staging`/`prod`)
- **Promo Codes**: `WELCOME10` (10% off), `FLY50` (`$50` off)

### Emulated Payment Gateway Test Cards
| Card Number | Simulated Outcome |
| :--- | :--- |
| `4242 4242 4242 4242` | Approved (`SUCCEEDED`) |
| `4000 0000 0000 0002` | Declined by issuer (`HTTP 402`) |
| `4000 0000 0000 9995` | Insufficient funds (`HTTP 402`) |

## Performance Benchmarks (Docker Compose, 3 Gunicorn Workers, Concurrency = 16)

Measured via `make benchmark` (`200` requests/endpoint through Nginx -> Gunicorn -> PostgreSQL 16, `0%` error rate):

| Endpoint | Throughput (RPS) | p50 Latency | p95 Latency | p99 Latency | Errors |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `GET /api/v1/fleet/airports/` | **276.4** | 56.1 ms | **64.0 ms** | 65.9 ms | 0 |
| `GET /api/v1/health/live/` | **227.4** | 29.8 ms | 474.6 ms | 502.5 ms | 0 |
| `GET /api/v1/flights/search/` | **52.8** | 290.5 ms | **373.8 ms** | 413.5 ms | 0 |

## Running Tests & Quality Checks

```bash
# Lint & SAST security scan (ruff + bandit)
make lint
make security

# Run isolated test environment (ephemeral tmpfs PostgreSQL + Redis + coverage)
make test-env

# Validate all 5 Docker Compose environment configs (base, dev, test, staging, prod)
make validate-envs

# Run Playwright Chromium E2E browser suite against running Docker stack
make e2e

# Run HTTP concurrency latency & RPS benchmark (or k6 run loadtest/k6_smoke.js)
make benchmark

# Run full end-to-end smoke check through Nginx
make smoke
```

See [docs/ENVIRONMENTS.md](docs/ENVIRONMENTS.md) for the full `test` / `dev` / `staging` / `prod` (`main`) matrix, branch promotion workflow, and GHCR CD pipeline details.

## License
MIT — see [LICENSE](LICENSE).
