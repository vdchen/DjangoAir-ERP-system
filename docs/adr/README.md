# Architecture Decision Records (ADRs)

This directory captures the major architectural trade-offs made while designing and evolving **DjangoAir ERP**.

| ADR | Title | Status |
| :--- | :--- | :--- |
| [ADR-001](001-row-level-locking-for-seat-allocation.md) | Row-Level Locking (`SELECT FOR UPDATE`) for Seat Allocation | Accepted |
| [ADR-002](002-transactional-outbox-and-idempotency.md) | Transactional Outbox Pattern & API Idempotency Keys | Accepted |
| [ADR-003](003-ascending-staff-role-hierarchy.md) | Ascending Staff Role Hierarchy (`Gate < Check-in < Supervisor`) | Accepted |
| [ADR-004](004-dual-independent-spas-behind-nginx.md) | Dual Independent Vue 3 SPAs Behind a Unified Nginx Reverse Proxy | Accepted |
