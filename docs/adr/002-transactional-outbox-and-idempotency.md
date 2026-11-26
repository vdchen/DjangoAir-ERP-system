# ADR-002: Transactional Outbox Pattern & API Idempotency Keys

- **Status**: Accepted
- **Date**: 2026-11-24

## Context
Two failure modes plague distributed booking & payment backends:
1. **Dual-write drift**: Writing to PostgreSQL and immediately publishing to Redis/Celery can publish ghost events if the DB transaction later rolls back, or lose events if Redis is transiently unreachable.
2. **Client retry duplication**: Mobile/browser timeouts during `POST /api/v1/bookings/` or `POST /api/v1/payments/charge/` cause retries that risk duplicate bookings or double charges.

## Decision
1. **Transactional Outbox (`OutboxEvent`)**: `publish_domain_event` writes an `OutboxEvent(status=PENDING)` row inside the same PostgreSQL transaction as the domain mutation and schedules `relay_outbox_event` inside `transaction.on_commit(...)`. Failed deliveries increment `attempts`, transition to `DEAD_LETTER` after `max_attempts`, and can be replayed by a Supervisor via `/api/v1/integrations/outbox/<id>/replay/`.
2. **Idempotency Keys (`IdempotencyRecord`)**: Mutating booking and payment endpoints accept an `Idempotency-Key` header, store a SHA-256 hash of the canonical request payload, replay identical retries (`X-Idempotent-Replayed: true`), and reject mismatched payloads with `HTTP 409 Conflict`.

## Consequences
- **Positive**: Atomic DB-to-event consistency, zero ghost events, safe client retries, and full auditability of dead-lettered partner webhooks.
- **Trade-off**: Adds one lightweight DB insert per domain event and periodic outbox table retention pruning in long-running production clusters.
