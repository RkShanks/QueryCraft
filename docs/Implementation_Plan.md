# Implementation Plan — Text-to-SQL Analytics Platform

**Phasing principles**
- Each phase is a vertical slice (UI + API + storage + LLM where relevant), not a horizontal layer.
- Phases 1–3 establish a working product; Phases 4–8 add the enterprise features.
- Hard dependencies are noted explicitly. Within a phase, scope stays narrow on purpose.
- "Architecture supports this from day 1, but UX/features come later" is called out explicitly so nothing gets reworked later.

---

### Phase 1 — Core Query Loop (MVP)
**Goal:** A user can ask a question, the system generates SQL, validates it, runs it, and shows the result as a table. The user can accept/reject/regenerate, and accepted queries land in their history.

**In scope**
- Single local admin account (provisional auth — full SSO/RBAC comes in Phase 5).
- One source database type: PostgreSQL.
- One LLM provider (configurable: Claude *or* OpenAI *or* Gemini *or* self-hosted).
- English UI only — but i18n string layer and RTL-ready CSS architecture exist from day 1 so Phase 4 doesn't rework UI.
- Validation gate (evaluator pass/fail before execution).
- Accept / Reject / Regenerate flow. One auto-regenerate on reject, then ask user to refine.
- Per-user history list of accepted queries (simple list, text filter only).
- Result rendering: table only, no charts yet.

**Out of scope (deferred)**
Charts, MySQL/MSSQL, Arabic UI, SSO, RBAC, masking, quotas, audit log, dashboard, reports, semantic search.

**Depends on:** nothing.

---

### Phase 2 — Charts and Generative UI
**Goal:** Results are rendered as a chart automatically chosen by the system, with a table beside it and the SQL visible. The user can override the chart type.

**In scope**
- Auto chart selection based on result shape (categorical vs. time series vs. single metric, etc.).
- User override of chart type.
- Show chart + table + generated SQL together.
- Localized number/date formatting hooks ready (locale plumbing in place even though only English is enabled).

**Out of scope (deferred)**
Drill-down, dashboards, exporting charts, custom chart styling.

**Depends on:** Phase 1.

---

### Phase 3 — Multi-Dialect SQL and Multiple Source Databases
**Goal:** Admins can connect more than one source database (PostgreSQL, MySQL, MS SQL Server). Each query targets a chosen database; the SQL dialect always matches.

**In scope**
- Admin UI to add/edit/remove a database connection.
- Schema introspection per connection.
- Dialect-aware SQL generation (PostgreSQL, MySQL, MS SQL Server).
- User picks which connected database their question targets.

**Out of scope (deferred)**
Cross-database joins. Read replicas. Connection pooling tuning UI.

**Depends on:** Phase 1.

---

### Phase 4 — Arabic, RTL, and Cross-Language Querying
**Goal:** A user can ask questions in Arabic (or any natural language) and the platform produces SQL in the dialect of their target database. UI fully supports RTL.

**In scope**
- Arabic UI translations across every screen built in Phases 1–3.
- RTL layout activation when language is RTL.
- The LLM accepts questions in any language and outputs SQL/result narration appropriately.
- Localized error messages and validation feedback.

**Out of scope (deferred)**
Voice input. Right-to-left chart axis flipping (charts can stay LTR for v1).

**Depends on:** Phases 1, 2 (the UI surfaces it has to translate). Doesn't strictly need Phase 3, but ordering it after 3 means the multi-dialect work is already done when Arabic users start using non-PG databases.

---

### Phase 5 — SSO, RBAC, and Row/Column Security
**Goal:** End users sign in via enterprise SSO. Permissions are role-based. Users only see data their role permits; sensitive columns are masked.

**In scope**
- SAML and OIDC SSO for end users.
- Local accounts for admins only.
- Role definitions: name, attached permissions, mapped DB role.
- Map SSO group claims onto platform roles.
- Database-level row filters and column masking applied at query time.
- "Column was masked" indicator in results.
- Users with no role have no access.

**Out of scope (deferred)**
Per-user permission overrides (forbidden by Constitution). Just-in-time role provisioning workflows.

**Depends on:** Phases 1, 3. Replaces the provisional admin login from Phase 1.

---

### Phase 6 — Governance: Audit Log, Quotas, Injection Detection
**Goal:** Every relevant action is auditable. Roles have enforced quotas. Injection attempts are detected, blocked, and trigger auto-suspension on repeat.

**In scope**
- Tamper-evident audit log covering all user actions, query lifecycle events, role changes, logins, suspensions, quota events, admin changes. Retroactively covers actions from earlier phases.
- Token + query quotas at the role level. Daily and monthly windows. Approaching-limit alerts to user + admin. Hard cutoff on exhaustion.
- Prompt-injection and SQL-injection detection at the LLM and SQL boundaries.
- Auto-suspension on repeat or high-severity attempts.
- User notification on suspension. Suspended users blocked from sign-in.

**Out of scope (deferred)**
Audit log search UI (lives in Phase 7's dashboard). Cost-based quotas (token-based is sufficient for v1).

**Depends on:** Phase 5 (no governance without identity).

---

### Phase 7 — Admin Dashboard
**Goal:** Administrators have one place to see what's happening and to operate the platform.

**In scope**
- Aggregated metrics: active users, queries executed, accept/reject ratio, token consumption vs. quotas, system health, recent security events.
- User management: view, suspend, reinstate, view per-user chat history.
- Role management UI: create, edit, attach permissions, map SSO groups.
- Database connection management UI (was minimal in Phase 3 — fleshed out here).
- LLM provider selection UI (configuration switch only — supported in earlier phases via config; here it gets a UI).
- Audit log search and export.
- Security incident review.

**Out of scope (deferred)**
External BI tool integrations. Custom dashboard authoring.

**Depends on:** Phases 5, 6.

---

### Phase 8 — Scheduled Reports and Notifications
**Goal:** Admins can schedule recurring reports. Recipients get role-appropriate, localized content via email (and Telegram if configured).

**In scope**
- Scheduled reports: weekly, monthly. A report = a set of saved queries run on schedule.
- Email delivery (mandatory).
- Telegram delivery (optional, enabled if a bot token is configured).
- RBAC-aware content: each recipient sees only what their role permits, with masking.
- Localized to recipient's preferred language.
- Quota and security alerts also routed through this notification subsystem.

**Out of scope (deferred)**
WhatsApp delivery. Ad-hoc one-off reports. Slack/Teams.

**Depends on:** Phases 5, 6.

---

### Phase 9 (optional polish) — Semantic Search of Accepted Queries
**Goal:** Users find past accepted queries by meaning, not just text matching. Search is scoped by role.

**In scope**
- Vector-based semantic search over accepted queries.
- Cross-user search scoped by role visibility (a user sees accepted queries from peers whose role grants the same or broader data access).
- "Re-run on current data" button next to any retrieved query.

**Out of scope (deferred)**
Recommendation feed. Auto-suggest queries based on partial input (could be a Phase 10 if you want).

**Depends on:** Phases 5, 6.

---

## Suggested execution order
1, 2, 3, 4, 5, 6, 7, 8, (optional) 9.

You could swap Phases 3 and 4 if Arabic users are higher priority than MS SQL Server / MySQL support. Everything else has hard dependencies that lock the order.

---

Tell me which phase you want to start with and I'll write the `/speckit.specify` prompt for that phase. Most likely you want to begin with **Phase 1**.
