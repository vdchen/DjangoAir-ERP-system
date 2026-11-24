# ADR-003: Ascending Staff Role Hierarchy (`Gate < Check-in < Supervisor`)

- **Status**: Accepted
- **Date**: 2026-11-24

## Context
The airline ERP specification defines an ascending operational hierarchy where each higher tier inherits every capability of lower tiers:
- Level 1: **Gate Manager** — board checked-in passengers using `ticket_code`.
- Level 2: **Check-in Manager** — check in passengers, attach options, collect luggage fees (+ Level 1).
- Level 3: **Supervisor** — add/remove Gate & Check-in Managers, create/cancel flights, add/remove options (+ Level 1 & Level 2).

## Decision
Model staff roles as an ordered numeric rank (`STAFF_ROLE_RANK = {GATE_MANAGER: 1, CHECKIN_MANAGER: 2, SUPERVISOR: 3}`) with `User.has_min_staff_role(min_role)` and explicit DRF permission classes (`IsGateManagerOrAbove`, `IsCheckInManagerOrAbove`, `IsSupervisor`) enforced server-side on every endpoint, mirrored by UI tab gating in the Staff SPA.

## Consequences
- **Positive**: Eliminates duplicated permission checks across views, prevents privilege drift when adding new endpoints, and makes the RBAC matrix trivially testable.
- **Trade-off**: If non-hierarchical roles (e.g., read-only Finance Auditor) are introduced later, they should be modeled as orthogonal Django permission groups alongside the operational rank.
