# QueryCraft Style Guide

This document records coding conventions and layout decisions for the QueryCraft monorepo.

## Frontend test file layout

- Tests are co-located with components: `Component.tsx` ↔ `Component.test.tsx`.
- Do NOT use `__tests__/` subdirectories.
- Rationale: improves discoverability + matches Wave 5 cleanup decisions.
- Exceptions: shared test utilities live in `frontend/tests/utils/`.
