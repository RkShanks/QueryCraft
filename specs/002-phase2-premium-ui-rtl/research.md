# Phase 2 Research — Resolved Technical Unknowns

## R-001: Zustand for UI State

**Decision**: Use Zustand (`zustand@5`) for client-side UI state (sidebar collapsed, hovered session ID, prompt draft text).

**Rationale**: Zustand is already battle-tested with React 19 and offers built-in `persist` middleware (localStorage). Weighs ~2KB gzipped vs. Redux Toolkit ~12KB. TanStack Query already installed handles all server state; Zustand only manages local UI concerns.

**Alternatives considered**:
- Jotai: Atomic model is overkill for 3 boolean/string atoms.
- Redux Toolkit: Heavy; unnecessary when TanStack Query handles server state.
- React Context: Causes full re-renders; Zustand's selector-based subscriptions are more performant.

## R-002: Shiki for Syntax Highlighting

**Decision**: Use Shiki (`shiki@3`) for SQL syntax highlighting with a custom dark theme. Lazy-load via `React.lazy()` + dynamic `import()`.

**Rationale**: Shiki provides TextMate grammar-powered highlighting (same engine as VS Code), producing semantic HTML tokens. Unlike Prism/highlight.js, Shiki supports full theme customization via JSON theme files, enabling exact color mapping to the QueryCraft obsidian+neon palette.

**Alternatives considered**:
- Prism: Simpler but limited theme system; can't do per-token color mapping.
- highlight.js: Similar limitations; larger bundle.
- CodeMirror: Full editor, massively overkill for read-only code display.

## R-003: Fontsource for Self-Hosted Fonts

**Decision**: Use `@fontsource-variable/inter` and `@fontsource/jetbrains-mono` packages.

**Rationale**: Self-hosting via fontsource avoids Google Fonts CDN dependency, improves privacy compliance (no external requests), and provides tree-shakeable variable font weights. These packages are the standard approach in Vite+React projects.

**Alternatives considered**:
- Google Fonts CDN: External dependency; privacy concern for KSA deployment.
- Manual woff2 files: Works but fontsource handles subsetting and format variants automatically.

## R-004: lucide-react Icon Barrel

**Decision**: Use existing `lucide-react` dependency (already in package.json at ^1.14.0). Create a barrel export at `src/components/icons.ts` that re-exports ~13 named icons.

**Rationale**: lucide-react is already installed. A barrel file centralizes icon imports and documents exactly which icons the UI uses, making tree-shaking auditable and preventing ad-hoc icon sprawl.

**Icons required**: Plus, Sparkles, Copy, RefreshCw, ThumbsUp, ThumbsDown, Trash2, PanelLeftClose, PanelLeftOpen, Send, Download, Settings, X

## R-005: respx for HTTP-Level LLM Mocking

**Decision**: Use `respx` (already in dev dependencies at >=0.23.1) for Gemini contract tests.

**Rationale**: respx integrates natively with httpx (which the GeminiAdapter uses). It intercepts at the transport layer, meaning contract tests verify the exact HTTP request construction and response parsing without any network I/O. Already installed in pyproject.toml dev dependencies.

**Alternatives considered**:
- vcrpy: Cassette-based; good for recording real responses but harder to construct synthetic edge cases (429, malformed JSON).
- responses: For `requests` library, not httpx.
- httpretty: Socket-level mocking; more invasive and less precise.

## R-006: Tailwind v4 Custom Theme Extension

**Decision**: Extend the existing Tailwind v4 setup in `index.css` using `@theme` directive for custom colors, fonts, and keyframes. Tailwind v4 uses CSS-first configuration (no tailwind.config.js).

**Rationale**: The project already uses `@tailwindcss/vite` v4.2.4 and `tailwindcss` v4.2.4. Tailwind v4 uses `@theme` blocks in CSS rather than JS config files. Custom colors (obsidian, neon-cyan, neon-purple, neon-fuchsia) and gradient keyframes must be defined there.

## R-007: Session Model — Postgres Only

**Decision**: No Redis cache layer for sessions. Direct Postgres reads via async SQLAlchemy.

**Rationale**: Single-user scale means session list queries hit at most hundreds of rows. Postgres with asyncpg handles this in <5ms. Adding a Redis cache layer introduces cache invalidation complexity with zero performance benefit.

## R-008: Lifecycle Invariant Test Framework

**Decision**: Pure pytest fixtures with a custom invariant registry. No external dependencies beyond pytest and the existing Redis/DB test fixtures.

**Rationale**: The framework needs to observe state at test boundaries (Redis keys, DB row counts) and assert no leaks. A pytest plugin with `@pytest.fixture(autouse=True)` that snapshots state in `setup` and validates in `teardown` is the simplest pattern. Documenting 3 invariants (lock, feedback-state, session-touch) as composable fixtures allows selective opt-in.

## R-009: OpenAPI Contract Extension Strategy

**Decision**: Extend the FastAPI-generated OpenAPI spec by adding new routers for sessions, feedback, and admin settings endpoints. The OpenAPI spec is auto-generated from FastAPI route decorators and Pydantic models.

**Rationale**: The project uses FastAPI's built-in OpenAPI generation (no separate openapi.yaml file found). Frontend API client is generated from this via `@hey-api/openapi-ts`. New endpoints will be added to new routers (sessions, feedback) and existing routers (admin), then the frontend client will be regenerated.

## R-010: Migration 004 Strategy

**Decision**: Single Alembic migration `004_add_sessions_and_extend_accepted_queries.py` that:
1. Creates `sessions` table with cascade FK to `accepted_queries`
2. Adds `session_id`, `saved`, `feedback` columns to `accepted_queries`
3. Seeds default `llm_context_cap` in `app_config`

**Rationale**: One migration keeps the schema change atomic. The existing `app_config` table (key-value JSONB) already supports the context cap setting without schema changes — only a seed row is needed.
