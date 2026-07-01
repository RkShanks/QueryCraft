import { http, HttpResponse, delay } from 'msw';
import type {
  UserProfile,
  QueryResult,
  AcceptedQuerySummary,
  HistoryListResponse,
  EvaluatorRejection,
  RefinePrompt,
  ErrorResponse,
  SessionListResponse,
  SessionDetail,
  FeedbackResponse,
  AdminSettingsResponse,
  UpdateAdminSettingsResponse,
} from '../api/generated/types.gen';

/** Scenario for /query/submit responses. */
export type QuerySubmitScenario =
  | 'result'
  | 'evaluator_rejected'
  | 'timeout'
  | 'concurrent'
  | 'llm_unavailable';

/** Scenario for /query/reject and /query/regenerate responses. */
export type QueryRetryScenario =
  | 'result'
  | 'refine'
  | 'attempt_invalid'
  | 'concurrent';

let submitScenario: QuerySubmitScenario = 'result';
let rejectScenario: QueryRetryScenario = 'result';
let regenerateScenario: QueryRetryScenario = 'result';

export function setSubmitScenario(scenario: QuerySubmitScenario) {
  submitScenario = scenario;
}

export function setRejectScenario(scenario: QueryRetryScenario) {
  rejectScenario = scenario;
}

export function setRegenerateScenario(scenario: QueryRetryScenario) {
  regenerateScenario = scenario;
}

export function resetQueryScenarios() {
  submitScenario = 'result';
  rejectScenario = 'result';
  regenerateScenario = 'result';
}

const defaultResult: QueryResult = {
  kind: 'result',
  attempt_id: 'a1b2c3d4-5e6f-4a5b-8c7d-9e0f1a2b3c4d',
  session_id: '550e8400-e29b-41d4-a716-446655440003',
  question: 'How many users?',
  generated_sql: 'SELECT COUNT(*) FROM users;',
  columns: [{ name: 'count', type: 'bigint' }],
  rows: [[42]],
  row_count: 1,
  attempt_number: 1,
  is_last_auto_retry: false,
  accepted_query_id: 'f9e8d7c6-b5a4-4c3b-2a1d-0e9f8d7c6b5a',
};

const retryResult: QueryResult = {
  kind: 'result',
  attempt_id: 'b2c3d4e5-6f7a-4b5c-8d9e-0f1a2b3c4d5e',
  question: 'How many users?',
  generated_sql: 'SELECT COUNT(*) FROM users WHERE active = true;',
  columns: [{ name: 'count', type: 'bigint' }],
  rows: [[35]],
  row_count: 1,
  attempt_number: 2,
  is_last_auto_retry: true,
};

const refinePrompt: RefinePrompt = {
  kind: 'refine',
  message_key: 'query.refine.message',
  should_refine: true,
};

/** MSW handlers for API mocking in tests. */
export const handlers = [
  // ─────────────────────────── Auth ───────────────────────────
  http.post('/api/v1/auth/sign-in', async () => {
    await delay(10);
    const user: UserProfile = {
      id: 'd290f1ee-6c54-4b01-90e6-d701748f0851',
      username: 'admin',
      display_name: 'Admin User',
      role: 'admin',
    };
    return HttpResponse.json(user, { status: 200 });
  }),

  http.post('/api/v1/auth/sign-out', async () => {
    await delay(10);
    return new HttpResponse(null, { status: 204 });
  }),

  http.get('/api/v1/auth/me', async () => {
    await delay(10);
    const user: UserProfile = {
      id: 'd290f1ee-6c54-4b01-90e6-d701748f0851',
      username: 'admin',
      display_name: 'Admin User',
      role: 'admin',
    };
    return HttpResponse.json(user, { status: 200 });
  }),

  // ─────────────────────────── Query ───────────────────────────
  http.post('/api/v1/query/submit', async ({ request }) => {
    await delay(10);
    const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
    const sessionId = body.session_id as string | undefined | null;
    const result: QueryResult = {
      ...defaultResult,
      session_id: sessionId ?? defaultResult.session_id,
    };
    switch (submitScenario) {
      case 'evaluator_rejected': {
        const rejectBody: EvaluatorRejection = {
          message_key: 'query.evaluator.rejected',
          violations: [
            {
              rule: 'UnsafePattern',
              message_key: 'evaluator.violation.unsafePattern',
              message_params: { pattern: 'pg_sleep' },
            },
          ],
        };
        return HttpResponse.json(rejectBody, { status: 422 });
      }
      case 'timeout': {
        const errorBody: ErrorResponse = {
          error: 'timeout',
          message_key: 'error.timeout',
        };
        return HttpResponse.json(errorBody, { status: 504 });
      }
      case 'concurrent': {
        const errorBody: ErrorResponse = {
          error: 'concurrent',
          message_key: 'error.concurrent',
        };
        return HttpResponse.json(errorBody, { status: 409 });
      }
      case 'llm_unavailable': {
        const errorBody: ErrorResponse = {
          error: 'llm_unavailable',
          message_key: 'error.llmUnavailable',
        };
        return HttpResponse.json(errorBody, { status: 502 });
      }
      case 'result':
      default:
        return HttpResponse.json(result, { status: 200 });
    }
  }),

  http.post('/api/v1/query/reject', async () => {
    await delay(10);
    switch (rejectScenario) {
      case 'refine':
        return HttpResponse.json(refinePrompt, { status: 200 });
      case 'attempt_invalid': {
        const body: ErrorResponse = {
          error: 'attempt_invalid',
          message_key: 'error.attemptInvalid',
        };
        return HttpResponse.json(body, { status: 400 });
      }
      case 'concurrent': {
        const body: ErrorResponse = {
          error: 'concurrent',
          message_key: 'error.concurrent',
        };
        return HttpResponse.json(body, { status: 409 });
      }
      case 'result':
      default:
        return HttpResponse.json(retryResult, { status: 200 });
    }
  }),

  http.post('/api/v1/query/regenerate', async () => {
    await delay(10);
    switch (regenerateScenario) {
      case 'refine':
        return HttpResponse.json(refinePrompt, { status: 200 });
      case 'attempt_invalid': {
        const body: ErrorResponse = {
          error: 'attempt_invalid',
          message_key: 'error.attemptInvalid',
        };
        return HttpResponse.json(body, { status: 400 });
      }
      case 'concurrent': {
        const body: ErrorResponse = {
          error: 'concurrent',
          message_key: 'error.concurrent',
        };
        return HttpResponse.json(body, { status: 409 });
      }
      case 'result':
      default:
        return HttpResponse.json(retryResult, { status: 200 });
    }
  }),

  http.post('/api/v1/query/accept', async () => {
    await delay(10);
    const summary: AcceptedQuerySummary = {
      id: 'f9e8d7c6-b5a4-4c3b-2a1d-0e9f8d7c6b5a',
      question_text: 'How many users?',
      generated_sql: 'SELECT COUNT(*) FROM users;',
      accepted_at: new Date().toISOString(),
    };
    return HttpResponse.json(summary, { status: 201 });
  }),

  // ─────────────────────────── History ───────────────────────────
  http.get('/api/v1/history', async () => {
    await delay(10);
    const history: HistoryListResponse = {
      items: [
        {
          id: 'f9e8d7c6-b5a4-4c3b-2a1d-0e9f8d7c6b5a',
          question_text: 'How many users?',
          generated_sql: 'SELECT COUNT(*) FROM users;',
          accepted_at: new Date().toISOString(),
        },
      ],
      total: 1,
      next_cursor: null,
    };
    return HttpResponse.json(history, { status: 200 });
  }),

  // ─────────────────────────── Connections ───────────────────────────
  http.get('/api/v1/connections', async () => {
    await delay(10);
    return HttpResponse.json(
      {
        connections: [
          {
            id: 'default-pg-connection',
            display_name: 'PostgreSQL DB',
            database_type: 'postgresql',
          },
        ],
      },
      { status: 200 }
    );
  }),

  // ─────────────────────────── Session Connection ───────────────────────────
  http.patch('/api/v1/sessions/:sessionId/connection', async ({ params }) => {
    await delay(10);
    return HttpResponse.json(
      {
        id: params.sessionId as string,
        connection_id: 'default-pg-connection',
        preview_text: 'Session detail',
        created_at: new Date().toISOString(),
        last_activity_at: new Date().toISOString(),
      },
      { status: 200 }
    );
  }),

  // ─────────────────────────── Sessions ───────────────────────────
  http.post('/api/v1/sessions', async () => {
    await delay(10);
    const session = {
      id: '550e8400-e29b-41d4-a716-446655440001',
      preview_text: 'New session',
      created_at: new Date().toISOString(),
    };
    return HttpResponse.json(session, { status: 201 });
  }),

  http.get('/api/v1/sessions', async () => {
    await delay(10);
    const sessions: SessionListResponse = {
      items: [
        {
          id: '550e8400-e29b-41d4-a716-446655440001',
          preview_text: 'New session',
          created_at: new Date().toISOString(),
          last_activity_at: new Date().toISOString(),
        },
      ],
      total: 1,
    };
    return HttpResponse.json(sessions, { status: 200 });
  }),

  http.get('/api/v1/sessions/:sessionId', async ({ params }) => {
    await delay(10);
    const detail: SessionDetail = {
      id: params.sessionId as string,
      preview_text: 'Session detail',
      created_at: new Date().toISOString(),
      last_activity_at: new Date().toISOString(),
      attempts: [
        {
          id: 'session-attempt-1',
          question_text: 'How many users?',
          generated_sql: 'SELECT COUNT(*) FROM users;',
          accepted_at: new Date().toISOString(),
          saved: true,
          feedback: 1,
          result_columns: [{ name: 'count', type: 'bigint' }],
          result_rows: [[42]],
          result_row_count: 1,
        },
      ],
    };
    return HttpResponse.json(detail, { status: 200 });
  }),

  http.delete('/api/v1/sessions/:sessionId', async () => {
    await delay(10);
    return new HttpResponse(null, { status: 204 });
  }),

  // ─────────────────────────── Feedback ───────────────────────────
  http.patch('/api/v1/feedback/:attemptId', async () => {
    await delay(10);
    const feedback: FeedbackResponse = {
      id: '550e8400-e29b-41d4-a716-446655440002',
      feedback: 1,
      saved: true,
    };
    return HttpResponse.json(feedback, { status: 200 });
  }),

  // ─────────────────────────── Admin Settings ───────────────────────────
  http.get('/api/v1/admin/settings', async () => {
    await delay(10);
    const settings: AdminSettingsResponse = {
      llm_context_cap: 3,
      max_regenerate_attempts: 3,
    };
    return HttpResponse.json(settings, { status: 200 });
  }),

  http.patch('/api/v1/admin/settings', async () => {
    await delay(10);
    const response: UpdateAdminSettingsResponse = {
      llm_context_cap: 5,
      max_regenerate_attempts: 3,
      updated_at: new Date().toISOString(),
    };
    return HttpResponse.json(response, { status: 200 });
  }),

  // ─────────────────────────── History DELETE ───────────────────────────
  http.delete('/api/v1/history/:query_id', async () => {
    await delay(10);
    return new HttpResponse(null, { status: 204 });
  }),

  // ─────────────────────────── Audit Search ───────────────────────────
  http.get('/api/v1/admin/audit/entries', () => {
    return HttpResponse.json({
      entries: [],
      pagination: { page: 1, page_size: 10, total_entries: 0, total_pages: 1 },
    });
  }),
];
