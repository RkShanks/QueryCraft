# Phase 2 API Contracts

All new endpoints added to the FastAPI application. The OpenAPI spec is auto-generated from route decorators and Pydantic models. Frontend client is regenerated via `npm run gen:api`.

## Sessions Router (`/api/v1/sessions`)

### POST /api/v1/sessions — Create Session (FR-031)

**Request**: Empty body (session is auto-associated with authenticated user).

**Response 201**:
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "preview_text": null,
  "created_at": "2026-05-12T12:00:00Z",
  "last_activity_at": "2026-05-12T12:00:00Z"
}
```

**Errors**: 401 Unauthorized

---

### GET /api/v1/sessions — List Sessions (FR-032, FR-034)

**Response 200**:
```json
{
  "sessions": [
    {
      "id": "uuid",
      "preview_text": "What are the top 10 customers by...",
      "created_at": "2026-05-12T12:00:00Z",
      "last_activity_at": "2026-05-12T14:30:00Z"
    }
  ]
}
```

Returns all sessions for the authenticated user, ordered by `last_activity_at DESC`. Frontend handles chronological grouping (Today / Previous 7 Days / Older).

**Errors**: 401 Unauthorized

---

### GET /api/v1/sessions/:id — Get Session Detail (FR-032)

**Response 200**:
```json
{
  "id": "uuid",
  "preview_text": "What are the top 10...",
  "created_at": "2026-05-12T12:00:00Z",
  "last_activity_at": "2026-05-12T14:30:00Z",
  "attempts": [
    {
      "id": "uuid",
      "question_text": "What are the top 10 customers by revenue?",
      "generated_sql": "SELECT ...",
      "feedback": 1,
      "saved": true,
      "accepted_at": "2026-05-12T12:01:00Z"
    }
  ]
}
```

Returns the session with its full conversation history (accepted_queries ordered by accepted_at ASC).

**Errors**: 401 Unauthorized, 404 Not Found

---

### DELETE /api/v1/sessions/:id — Delete Session (FR-033, FR-044, FR-058)

**Response 204**: No content.

Cascade deletes all associated accepted_queries, feedback records. If an in-flight query exists for this session, the backend cancels it (deletes the processing lock and ephemeral attempt from Redis) before deleting the session.

**Errors**: 401 Unauthorized, 404 Not Found

---

## Feedback Router (`/api/v1/feedback`)

### PATCH /api/v1/feedback/:attempt_id — Update Feedback (FR-036, FR-039)

**Request**:
```json
{
  "feedback": 1,
  "saved": true
}
```

| Field | Type | Constraints |
|-------|------|-------------|
| `feedback` | `integer` | Required. Must be `1` or `-1`. |
| `saved` | `boolean` | Optional. If `feedback=1`, defaults to `true`. |

**Response 200**:
```json
{
  "id": "uuid",
  "feedback": 1,
  "saved": true
}
```

**Errors**: 401 Unauthorized, 404 Not Found, 422 Invalid feedback value

---

## Admin Settings Router (extends `/api/v1/admin`)

### GET /api/v1/admin/settings — Read Settings (FR-046)

**Request**: Requires `X-Admin-Key` header.

**Response 200**:
```json
{
  "llm_context_cap": 3
}
```

**Errors**: 401 Unauthorized, 403 Forbidden

---

### PATCH /api/v1/admin/settings — Update Settings (FR-040, FR-046)

**Request**: Requires `X-Admin-Key` header.

```json
{
  "llm_context_cap": 5
}
```

| Field | Type | Constraints |
|-------|------|-------------|
| `llm_context_cap` | `integer` | Required. Range 0–10 (FR-040). |

**Response 200**:
```json
{
  "llm_context_cap": 5,
  "updated_at": "2026-05-12T12:00:00Z"
}
```

**Errors**: 401 Unauthorized, 403 Forbidden, 422 Validation (out of range)

---

## Extended Endpoint: POST /api/v1/query/submit (FR-035)

**Request** (extended):
```json
{
  "question": "What are the top customers?",
  "session_id": "uuid"
}
```

New optional field `session_id`. When provided:
1. The system loads the last N **completed** (accepted/rejected) attempts from the session (where N = `llm_context_cap`), excluding pending/in-flight attempts.
2. These are passed to the prompt builder as conversational history.
3. On success, the attempt is associated with the session and `session.last_activity_at` is updated.
4. If this is the first message in the session, `session.preview_text` is set to the first 60 chars of the question + ellipsis.

When `session_id` is omitted, behavior is unchanged from Phase 1.

**Implicit feedback on follow-up** (FR-036a): When `session_id` is provided and the prior attempt in the session has `feedback=NULL`, the prior attempt receives `feedback=+1` and `saved=true`.

---

## Pydantic Schema Additions

### New Schemas

```python
# backend/src/app/schemas/session.py
class CreateSessionResponse(BaseModel):
    id: str
    user_id: str
    preview_text: str | None
    created_at: str
    last_activity_at: str

class SessionSummary(BaseModel):
    id: str
    preview_text: str | None
    created_at: str
    last_activity_at: str

class AttemptSummary(BaseModel):
    id: str
    question_text: str
    generated_sql: str
    feedback: int | None
    saved: bool
    accepted_at: str

class SessionDetail(BaseModel):
    id: str
    preview_text: str | None
    created_at: str
    last_activity_at: str
    attempts: list[AttemptSummary]

class SessionListResponse(BaseModel):
    sessions: list[SessionSummary]

# backend/src/app/schemas/feedback.py
class UpdateFeedbackRequest(BaseModel):
    feedback: int = Field(..., ge=-1, le=1)
    saved: bool | None = None

class FeedbackResponse(BaseModel):
    id: str
    feedback: int
    saved: bool

# backend/src/app/schemas/admin.py
class AdminSettingsResponse(BaseModel):
    llm_context_cap: int

class UpdateAdminSettingsRequest(BaseModel):
    llm_context_cap: int = Field(..., ge=0, le=10)

class UpdateAdminSettingsResponse(BaseModel):
    llm_context_cap: int
    updated_at: str
```

### Extended Schema

```python
# backend/src/app/schemas/query.py — SubmitQuestionRequest
class SubmitQuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None  # NEW: optional session association
```
