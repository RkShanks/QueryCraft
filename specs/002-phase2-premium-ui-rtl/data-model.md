# Phase 2 Data Model

## Entity Relationship Diagram

```mermaid
erDiagram
    users ||--o{ sessions : "owns"
    sessions ||--o{ accepted_queries : "contains"
    database_connections ||--o{ accepted_queries : "targets"
    app_config {
        string key PK
        jsonb value
        timestamptz updated_at
    }

    users {
        uuid id PK
        string username UK
        string display_name
        string password_hash
        timestamptz created_at
    }

    sessions {
        uuid id PK
        uuid user_id FK
        string preview_text "first msg truncated 60 chars"
        timestamptz created_at
        timestamptz last_activity_at
    }

    accepted_queries {
        uuid id PK
        uuid user_id FK
        uuid database_connection_id FK
        uuid session_id FK "NEW — nullable for Phase 1 orphans"
        string question_text
        string generated_sql
        string llm_provider
        string attempt_id
        boolean saved "NEW — default false"
        integer feedback "NEW — nullable, +1 or -1"
        timestamptz accepted_at
    }

    database_connections {
        uuid id PK
        string name UK
        string host
        integer port
        string database_name
        string username
        string encrypted_password
        string ssl_mode
    }
```

## New Entity: Session

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | `UUID` | PK, `gen_random_uuid()` | |
| `user_id` | `UUID` | FK → `users.id`, NOT NULL | |
| `preview_text` | `VARCHAR(63)` | NULL | First user message, hard-truncated to 60 chars + "..." (ADR-2). NULL until first message submitted. |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, `now()` | |
| `last_activity_at` | `TIMESTAMPTZ` | NOT NULL, `now()` | Updated on each new query submission in the session. Used for chronological grouping. |

**Cascade**: `ON DELETE CASCADE` from sessions to accepted_queries.

**Indexes**:
- `ix_sessions_user_id_last_activity` on `(user_id, last_activity_at DESC)` — sidebar listing query.

## Extended Entity: AcceptedQuery

New columns added to existing `accepted_queries` table:

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `session_id` | `UUID` | FK → `sessions.id` ON DELETE CASCADE, NULLABLE | Nullable for backward compatibility with Phase 1 orphan rows. |
| `saved` | `BOOLEAN` | NOT NULL, DEFAULT `false` | Set to `true` when user clicks ThumbsUp or implicit +1 on follow-up. |
| `feedback` | `SMALLINT` | NULLABLE | `+1` = positive, `-1` = negative. NULL = no signal yet. |

## Extended Entity: AppConfig

New seed row (uses existing key-value table):

| Key | Default Value | Validation | Notes |
|-----|---------------|------------|-------|
| `llm_context_cap` | `3` | Integer 0–10 | Admin-configurable via settings endpoints. |

## State Transitions

### Session Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Created : User clicks "New Chat"
    Created --> Active : First message submitted
    Active --> Active : Follow-up submitted (last_activity_at updated)
    Active --> PendingDelete : User clicks trash
    PendingDelete --> [*] : 5s undo timer expires (cascade delete)
    PendingDelete --> Active : User clicks Undo
```

### Feedback Signal Lifecycle (per AcceptedQuery)

```mermaid
stateDiagram-v2
    [*] --> NoSignal : feedback=NULL
    NoSignal --> PositiveImplicit : Follow-up submitted (FR-036a)
    NoSignal --> PositiveExplicit : ThumbsUp clicked (FR-036e)
    NoSignal --> NegativeExplicit : ThumbsDown clicked (FR-036f)
    NoSignal --> NegativeRegenerate : Regenerate clicked (FR-036d)
    PositiveImplicit --> PositiveExplicit : ThumbsUp overrides
    PositiveImplicit --> NegativeExplicit : ThumbsDown overrides
    NegativeExplicit --> PositiveExplicit : ThumbsUp overrides
    PositiveExplicit --> NegativeExplicit : ThumbsDown overrides

    note right of PositiveImplicit : saved=true, feedback=+1
    note right of PositiveExplicit : saved=true, feedback=+1
    note right of NegativeExplicit : feedback=-1
    note right of NegativeRegenerate : feedback=-1, new attempt created
```

## Migration Plan

**File**: `backend/alembic/versions/004_add_sessions_and_extend_accepted_queries.py`

Operations (in order):
1. `CREATE TABLE sessions (...)` with FK to users, cascade semantics
2. `CREATE INDEX ix_sessions_user_id_last_activity ON sessions (user_id, last_activity_at DESC)`
3. `ALTER TABLE accepted_queries ADD COLUMN session_id UUID REFERENCES sessions(id) ON DELETE CASCADE`
4. `ALTER TABLE accepted_queries ADD COLUMN saved BOOLEAN NOT NULL DEFAULT false`
5. `ALTER TABLE accepted_queries ADD COLUMN feedback SMALLINT`
6. `CREATE INDEX ix_accepted_queries_session_id ON accepted_queries (session_id)`
7. `INSERT INTO app_config (key, value) VALUES ('llm_context_cap', '3') ON CONFLICT DO NOTHING`

Downgrade reverses in opposite order.
