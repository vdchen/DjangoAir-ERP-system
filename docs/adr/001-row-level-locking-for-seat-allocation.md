# ADR-001: Row-Level Locking (`SELECT FOR UPDATE`) for Seat Allocation

- **Status**: Accepted
- **Date**: 2026-11-24

## Context
Multiple customers can attempt to book the last remaining seats on a flight simultaneously. A naive read-then-insert check (`available >= requested` followed by `Ticket.objects.create`) suffers from a classic check-then-act race condition that causes overselling.

## Decision
Inside `apps.bookings.services.create_booking`, wrap seat validation and ticket creation in `transaction.atomic()` and acquire a PostgreSQL row-level write lock on the `Flight` row via `Flight.objects.select_for_update()`.

## Alternatives Considered
1. **Redis distributed lock (`SET NX EX`)**: Adds clock-skew/TTL expiry edge cases where a lock can expire while PostgreSQL is still committing.
2. **Optimistic concurrency (version column + retries)**: Works well for low contention, but requires retry loops on hot flights and still relies on database transactions.

## Consequences
- **Positive**: Zero overselling guaranteed directly by PostgreSQL ACID semantics with zero extra infrastructure.
- **Trade-off**: Concurrent bookings for the *same* flight serialize briefly (milliseconds); bookings for *different* flights remain fully parallel.
