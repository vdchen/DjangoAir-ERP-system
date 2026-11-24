# DjangoAir ERP System

**DjangoAir** is a containerized Airline Management ERP system uniting customer flight booking, an emulated payment gateway, Personal Cabinet self-service, role-governed airport staff operations, asynchronous Celery email notifications, a real-time Flask-SocketIO mobile WebSocket API, and an HMAC-signed third-party webhook integration.

## Documentation
- [Architecture & Module Decomposition](docs/ARCHITECTURE.md)
- [UML Class, State & Sequence Diagrams](docs/UML.md)
- [REST, WebSocket & Webhook API Contracts](docs/API.md)
- [Prioritized Development Roadmap](docs/ROADMAP.md)
- [Contributing Guidelines](CONTRIBUTING.md)

## Tech Stack
| Layer | Technology |
| :--- | :--- |
| **Core ERP Backend** | Python 3.12, Django 5.1, Django REST Framework, SimpleJWT, drf-spectacular |
| **Mock Microservices** | Flask 3, Flask-SocketIO (`gevent`), HMAC-SHA256 Webhook Verifier |
| **Database & Cache/Broker** | PostgreSQL 16, Redis 7 |
| **Async Workers** | Celery 5 + Mailpit (local SMTP inbox) |
| **Independent Web Interfaces** | Webpack 5, Vue 3, Bootstrap 5 (separate Customer `/` & Staff `/staff/` SPAs) |
| **Reverse Proxy & Runtime** | Nginx 1.27, Docker & Docker Compose, GitHub Actions CI |

## Quickstart (Docker Compose)

```bash
cp .env.example .env
docker compose up -d --build
```

On startup, the backend automatically runs PostgreSQL migrations and seeds demo airports, airplanes, flights, options, discounts, staff accounts, and webhook subscriptions.

### Service URLs
| Interface / Service | URL |
| :--- | :--- |
| **Customer Web Interface** (3-field search, booking, payment, Personal Cabinet) | `http://localhost:8080/` |
| **Staff Web Interface** (Gate Manager, Check-in Manager, Supervisor) | `http://localhost:8080/staff/` |
| **Interactive OpenAPI / Swagger Docs** | `http://localhost:8080/api/v1/docs/` |
| **Flask Mobile WebSocket Mock Client** | `http://localhost:8080/mobile-mock/` |
| **Flask Third-Party Webhook Inspector** | `http://localhost:8080/mock-webhook/` |
| **Mailpit Email Inbox** (inspect tickets, invoices & auto-provisioned credentials) | `http://localhost:8025/` |

## Seeded Demo Accounts & Test Cards

### Staff Hierarchy (Ascending Permissions)
| Level | Role | Email | Password | Capabilities |
| :---: | :--- | :--- | :--- | :--- |
| 1 | **Gate Manager** | `gate@djangoair.local` | `Gate123!` | Board checked-in passengers at gate using `ticket_code` |
| 2 | **Check-in Manager** | `checkin@djangoair.local` | `Checkin123!` | Counter check-in, attach options, collect luggage fee (+ L1) |
| 3 | **Supervisor** | `supervisor@djangoair.local` | `Supervisor123!` | Manage Gate/Check-in staff, create/cancel flights, manage options (+ L1 & L2) |

### Customer Demo Account & Promo Codes
- **Customer**: `alice@example.com` / `Customer123!` (pre-loaded with `$250.00` balance, 1 upcoming flight, and 1 previous flight)
- **Promo Codes**: `WELCOME10` (10% off), `FLY50` (`$50` off)

### Emulated Payment Gateway Test Cards
| Card Number | Simulated Outcome |
| :--- | :--- |
| `4242 4242 4242 4242` | Approved (`SUCCEEDED`) |
| `4000 0000 0000 0002` | Declined by issuer (`HTTP 402`) |
| `4000 0000 0000 9995` | Insufficient funds (`HTTP 402`) |

## Running Tests & Quality Checks

```bash
# Lint backend with ruff
make lint

# Run Django pytest suite (with PostgreSQL + coverage) and Flask pytest suites
make test

# Build both independent Webpack Vue 3 frontends
make build-frontend

# Run full end-to-end smoke check through Nginx against the running Docker stack
make smoke
```

## License
MIT — see [LICENSE](LICENSE).
