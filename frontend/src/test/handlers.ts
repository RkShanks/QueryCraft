import { http, HttpResponse } from 'msw';

/** MSW handlers for API mocking in tests. */
export const handlers = [
  // Auth
  http.post('/api/v1/auth/sign-in', () => {
    return HttpResponse.json(
      { user_id: 'test-uuid', username: 'admin', display_name: 'Admin', role: 'admin' },
      { status: 200 },
    );
  }),

  http.post('/api/v1/auth/sign-out', () => {
    return new HttpResponse(null, { status: 204 });
  }),

  http.get('/api/v1/auth/me', () => {
    return HttpResponse.json(
      { user_id: 'test-uuid', username: 'admin', display_name: 'Admin', role: 'admin' },
      { status: 200 },
    );
  }),

  // Query
  http.post('/api/v1/query/submit', () => {
    return HttpResponse.json({
      attempt_id: 'attempt-uuid',
      question_text: 'How many users?',
      generated_sql: 'SELECT COUNT(*) FROM users',
      is_second_attempt: false,
    });
  }),

  // History
  http.get('/api/v1/history', () => {
    return HttpResponse.json({ items: [] });
  }),
];
