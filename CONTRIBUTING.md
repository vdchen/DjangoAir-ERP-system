# Contributing to DjangoAir ERP

Thank you for contributing to **DjangoAir ERP**!

## Workflow
1. Branch off `main` (or `dev` once multi-environment promotion is enabled):
   ```bash
   git checkout -b feat/short-description
   ```
2. Keep changes focused, modular, and backed by automated tests.
3. Run quality checks before opening a PR:
   ```bash
   make lint
   make test
   ```
4. Open a Pull Request describing the motivation, architectural impact, and verification results.

## Coding Standards
- **Python / Django / Flask**: Follow PEP 8 enforced via `ruff`, keep domain logic in service modules (not fat views), and add `pytest` coverage for every endpoint and permission boundary.
- **Vue 3 / Bootstrap 5**: Keep Customer (`/`) and Staff (`/staff/`) SPAs cleanly decoupled.
- **Commits**: Use Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `ci:`).
