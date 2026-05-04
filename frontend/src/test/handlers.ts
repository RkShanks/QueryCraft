import { http, HttpResponse, delay } from 'msw';
import type {
  UserProfile,
  QueryResult,
  AcceptedQuerySummary,
  HistoryListResponse,
} from '../api/generated/types.gen';

/** MSW handlers for API mocking in tests. */
export const handlers = [
  // ─────────────────────────── Auth ───────────────────────────
  http.post('/api/v1/auth/sign-in', async () => {
    await delay(10);
    const user: UserProfile = {
      id: 'd290f1ee-6c54-4b01-90e6-d701748f0851',
      username: 'admin',
      display_name: 'Admin User',
      role: 'admin'
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
      role: 'admin'
    };
    return HttpResponse.json(user, { status: 200 });
  }),

  // ─────────────────────────── Query ───────────────────────────
  http.post('/api/v1/query/submit', async () => {
    await delay(10);
    const result: QueryResult = {
      kind: 'result',
      attempt_id: 'a1b2c3d4-5e6f-4a5b-8c7d-9e0f1a2b3c4d',
      question: 'How many users?',
      generated_sql: 'SELECT COUNT(*) FROM users;',
      columns: [{ name: 'count', type: 'bigint' }],
      rows: [[42]],
      row_count: 1,
      attempt_number: 1,
      is_last_auto_retry: false
    };
    return HttpResponse.json(result, { status: 200 });
  }),

  http.post('/api/v1/query/accept', async () => {
    await delay(10);
    const summary: AcceptedQuerySummary = {
      id: 'f9e8d7c6-b5a4-4c3b-2a1d-0e9f8d7c6b5a',
      question_text: 'How many users?',
      generated_sql: 'SELECT COUNT(*) FROM users;',
      accepted_at: new Date().toISOString()
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
          accepted_at: new Date().toISOString()
        }
      ],
      total: 1,
      next_cursor: null
    };
    return HttpResponse.json(history, { status: 200 });
  }),
];
