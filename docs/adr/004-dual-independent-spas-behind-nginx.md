# ADR-004: Dual Independent Vue 3 SPAs Behind a Unified Nginx Reverse Proxy

- **Status**: Accepted
- **Date**: 2026-11-24

## Context
DjangoAir requires two independent web interfaces—one minimal customer booking/cabinet interface and one role-governed staff operations interface—plus REST, WebSocket, and third-party webhook mock endpoints.

## Decision
Use Webpack 5's multi-compiler configuration (`frontend/webpack.config.js`) to emit two completely separate bundles (`dist/customer/` and `dist/staff/`) with isolated JWT `localStorage` namespaces (`djangoair_customer_token` vs. `djangoair_staff_token`), served through a single Nginx origin (`/` and `/staff/`).

## Alternatives Considered
1. **Separate subdomains (`staff.djangoair.local`)**: Requires `/etc/hosts` or local DNS setup for contributors and complicates cookie/CORS configuration in Docker CI.
2. **Single monolithic SPA**: Violates interface independence and bundles staff management code into the public customer payload.

## Consequences
- **Positive**: Zero-config local Docker & CI execution, isolated authentication sessions (a developer can be logged in as a Customer in one tab and Supervisor in another simultaneously), and minimal bundle size for customers.
- **Trade-off**: Both SPAs live in a shared `frontend/` workspace and rebuild together in the multi-stage Nginx image.
