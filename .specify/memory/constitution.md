<!--
  ╔════════════════════════════════════════════════════════════════════╗
  ║                     SYNC IMPACT REPORT                           ║
  ╠════════════════════════════════════════════════════════════════════╣
  ║ Version change  : (none) → 1.0.0  (initial ratification)        ║
  ║                                                                  ║
  ║ Added principles:                                                ║
  ║   I.   Security and Data Protection                              ║
  ║   II.  Query Validation Before Execution                         ║
  ║   III. Only Validated Knowledge Persists                         ║
  ║   IV.  Hostile Input is a Security Event                         ║
  ║   V.   LLM-Agnostic Platform                                    ║
  ║   VI.  Language Decoupled from SQL Dialect                       ║
  ║   VII. Role-Appropriate Authentication                           ║
  ║   VIII.Centrally Brokered Database Access                        ║
  ║   IX.  Observability and Auditability                            ║
  ║   X.   Quotas Enforced Not Suggested                             ║
  ║   XI.  Architectural Modularity                                  ║
  ║   XII. API Contract as Single Source of Truth                    ║
  ║                                                                  ║
  ║ Added sections:                                                  ║
  ║   - Quality Gates                                                ║
  ║   - Scope Boundaries                                             ║
  ║                                                                  ║
  ║ Removed sections: (none — template placeholders replaced)        ║
  ║                                                                  ║
  ║ Templates requiring updates:                                     ║
  ║   ✅ .specify/templates/plan-template.md     (aligned)           ║
  ║   ✅ .specify/templates/spec-template.md     (aligned)           ║
  ║   ✅ .specify/templates/tasks-template.md    (aligned)           ║
  ║                                                                  ║
  ║ Follow-up TODOs: (none)                                          ║
  ╚════════════════════════════════════════════════════════════════════╝
-->

# QueryCraft Constitution

## Core Principles

### I. Security and Data Protection are Non-Negotiable

All user data, configurations, chat histories, and query results
MUST be encrypted at rest and in transit. Sensitive columns MUST be
masked according to the requesting user's role before data leaves
the database boundary. No feature may ship if it weakens encryption,
bypasses authorization, or exposes raw credentials.

**Rationale**: The platform operates on enterprise data inside KSA.
A single exposure event can trigger regulatory, legal, and
reputational consequences that are irrecoverable.

### II. Every Generated Query is Validated Before Execution

No SQL produced by a language model is ever executed against a
customer database without passing two gates:

1. **Automated validation** by an internal evaluator that checks
   semantic correctness and safety.
2. **Explicit human acceptance** of the rendered result by the
   requesting user.

Queries that fail either gate MUST NOT be executed against
production data and MUST NOT be retained in long-term memory.

**Rationale**: LLM-generated SQL is probabilistic. Dual-gate
validation prevents data corruption, unauthorized reads, and
accidental destructive operations.

### III. Only Validated Knowledge Persists

The retrieval memory used for few-shot grounding and user-facing
search of past queries MUST contain only queries that the user
explicitly accepted as correct. Rejected, regenerated,
auto-discarded, or evaluator-failed queries MUST NEVER be written
to retrieval memory.

**Rationale**: Polluting the retrieval store with bad examples
degrades future query quality and erodes user trust.

### IV. Hostile Input is a Security Event

Prompt injection, SQL injection, and platform-abuse attempts MUST
be detected, blocked, logged with full context, and surfaced to
administrators in real time. Repeat or high-severity offenders MUST
be auto-suspended pending admin review. Detection is part of the
trust boundary, not an optional add-on.

**Rationale**: An analytics platform accepting natural-language
input is a high-value injection target. Treating attacks as routine
errors leaves the organization exposed.

### V. The Platform is LLM-Agnostic

The language model MUST be a swappable component. The platform MUST
support, at minimum:

- Anthropic Claude
- OpenAI
- Google Gemini
- A self-hosted model running on the customer's own infrastructure
  (e.g., Ollama-compatible endpoint)

Switching providers MUST NOT require code changes, schema
migrations, or downtime beyond a configuration reload.

**Rationale**: Model pricing, performance, and data-residency
policies shift rapidly. Vendor lock-in is an operational and
compliance risk.

### VI. Language is Decoupled from SQL Dialect

The platform MUST accept user questions in any natural language,
with first-class support for Arabic and English including full
right-to-left UI behavior. The platform MUST generate SQL in the
dialect of the connected database (MySQL, PostgreSQL, or MS SQL
Server). Users MUST NEVER be required to translate or rephrase
their question to match the database language or dialect.

**Rationale**: Enterprise users in KSA work in Arabic and English.
Forcing a language or dialect barrier between the user and their
data undermines the core value proposition of natural-language
analytics.

### VII. Authentication is Role-Appropriate

Administrators authenticate via local accounts managed inside the
platform. End users authenticate via enterprise SSO (SAML or OIDC).
Local end-user accounts are not supported in production. Every
authenticated identity MUST carry a role used for downstream
authorization decisions.

**Rationale**: SSO integration reduces credential sprawl. Splitting
admin and end-user auth paths maps to the distinct trust levels of
each population.

### VIII. Database Access is Centrally Brokered

Administrators connect each source database to the platform once,
using a service account. End users MUST NOT supply or see raw
database credentials. The platform itself maps each authenticated
user to a database role and enforces row-level and column-level
security on top of that role.

**Rationale**: Centralizing credential management prevents
credential leakage, ensures consistent access policies, and makes
access auditable.

### IX. Observability and Auditability are Built In

Every user action, generated query, validation outcome, security
event, administrative change, login attempt, and quota event MUST
be written to a tamper-evident audit log. The audit log is the
source of truth for compliance reviews and incident investigation.
Logs MUST be retained for at least 24 months.

**Rationale**: Without a tamper-evident audit trail, the
organization cannot demonstrate compliance, investigate incidents,
or attribute actions to identities.

### X. Quotas are Enforced, Not Suggested

Token, query, and cost quotas MUST be enforced at the API boundary.
When a quota is exhausted, further requests for the affected scope
MUST be rejected with a clear error — not throttled, not silently
queued. Approaching-limit alerts MUST be delivered to both the user
and an administrator before the limit is reached.

**Rationale**: LLM API costs scale with usage. Unenforced quotas
lead to budget overruns and unequal resource consumption across
the organization.

### XI. Architectural Modularity

The platform MUST be structured so that data sources, LLM
providers, notification channels, chart renderers, and analytics
modules can be added or replaced without modifying unrelated
components. Backend and frontend are developed as separately
deployable units that communicate only through a versioned API.

**Rationale**: A modular architecture reduces the blast radius of
changes, accelerates feature delivery, and supports the LLM-agnostic
and dialect-agnostic requirements.

### XII. The API Contract is the Single Source of Truth

The OpenAPI specification produced during the planning phase is
binding. Frontend and backend MUST conform to it. Any deviation
requires a new contract version reviewed and accepted before
implementation; ad-hoc divergence is a defect.

**Rationale**: A shared, versioned contract eliminates integration
drift, enables parallel frontend/backend development, and provides
machine-readable documentation.

## Quality Gates

A change MUST NOT be merged unless all of the following hold:

1. New or modified endpoints are reflected in the OpenAPI contract
   and pass contract tests.
2. Any new SQL-generation path is covered by the evaluator
   validation step (Principle II).
3. Any new security-relevant action emits an audit-log entry
   (Principle IX).
4. Any new data-access path enforces RBAC, row-level security,
   and column masking (Principles I, VIII).
5. Any new user-facing text or query path is verified to work with
   both English and Arabic input, including RTL rendering where
   applicable (Principle VI).

## Scope Boundaries

### In Scope

- Single-organization deployment on infrastructure in Saudi Arabia.
- Expected user base of 100 to 1,000 users per deployment.

### Out of Scope (v1)

- Multi-tenant SaaS hosting across multiple customer organizations
  on a shared instance.
- Cross-region data residency controls beyond the KSA deployment
  region.

## Architectural Invariants

The following invariants are enforced by code structure and tests.
They are non-negotiable and may not be relaxed without a
constitutional amendment.

### Invariant 3 — No Concurrent Submissions

A single user session MUST never have more than one query in flight.
The QueryService acquires a per-session processing lock at the start
of POST /query/submit and releases it on accept, reject, regenerate,
or attempt expiry. Any submission attempted while the lock is held
MUST return 409 Conflict with `error: "session_busy"`. Verified by
integration tests asserting that a second submission within the same
session returns 409.

### Invariant 4 — Byte-Equal Duplicate Detection

On regeneration after a rejection, if the LLM returns SQL that is
byte-equal to the rejected attempt's SQL, the QueryService MUST treat
it as a failed regeneration: a refine prompt is emitted, no further
evaluator or executor work is performed, and the rejection counter
advances toward the two-rejection cap. This protects against
degenerate LLM behaviour and ensures the user reaches a refine prompt
instead of an infinite identical loop. Verified by mocking an LLM
that returns identical SQL on retry.

## Governance

This constitution supersedes all other process documents. Any
proposed exception MUST be raised as an explicit amendment to this
file, reviewed, and accepted before the deviating work begins.
Implementation work that contradicts this constitution is, by
definition, a defect.

### Amendment Procedure

1. Author drafts the amendment as a diff to this file.
2. The amendment MUST reference the principle(s) affected and
   provide a written rationale.
3. The amendment MUST be reviewed and approved by the project owner.
4. Once approved, this file is updated and the version is
   incremented per the versioning policy below.

### Versioning Policy

- **MAJOR** increment: a principle is removed, redefined in a
  backward-incompatible way, or a quality gate is relaxed.
- **MINOR** increment: a new principle or section is added, or
  existing guidance is materially expanded.
- **PATCH** increment: clarifications, wording improvements, or
  non-semantic refinements.

### Compliance Review

- Every pull request MUST include a Constitution Check confirming
  that no principle is violated.
- Quarterly compliance reviews MUST audit a sample of merged
  changes against the quality gates.

## §11 Phased Rollout

Principles IV (Hostile Input), VI (Arabic+RTL), VII (Role-Appropriate Authentication), IX (Tamper-evident Audit Log), and X (Quotas) MUST be in place before public production launch. Pre-production phases MAY ship without these principles fully active when:

1. The deferral is explicitly recorded in `plan.md` with a target phase, and
2. The deferral does not affect the integrity of data already in scope (e.g., Audit Log absence in Phase 1 is acceptable because Phase 1 has no PII / no auth boundary; it would NOT be acceptable in Phase 5 once multi-user lands).

### Phased commitment table

| Principle | Required by phase | Trigger |
|---|---|---|
| IV — Hostile Input detection | Phase 6 | Public beta or first external user |
| VI — Arabic + RTL | Phase 4 | First non-English user persona |
| VII — Role-Appropriate Authentication (SSO + RBAC) | Phase 5 | First multi-user feature OR first SSO requirement |
| IX — Tamper-evident Audit Log (24-month) | Phase 5 | First multi-user feature OR first persisted PII |
| X — Token/Query/Cost quotas | Phase 5 | First multi-tenant boundary OR first paid user |

Operating in production WITHOUT a principle past its trigger is a constitutional violation, not technical debt. Each phase's `plan.md` MUST verify all triggered principles are active before declaring the phase complete.

---

## Changelog

- **v1.1.1** (2026-05-06) — Added Principle VII to §11 phased commitment table; resolves /speckit.analyze A3 (deferral was previously unauthorized).
- **v1.1.0** (2026-05-06) — Added §11 Phased Rollout; permits Principles IV, VI, IX, X to defer per the phased plan in plan.md, with explicit trigger conditions for each phase.
- **v1.0.0** (initial) — Original ten principles.

**Version**: 1.1.1 | **Ratified**: 2026-05-02 | **Last Amended**: 2026-05-06
