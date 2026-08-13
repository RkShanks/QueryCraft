import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, waitFor, act, fireEvent } from '@testing-library/react';
import { http, HttpResponse } from 'msw';

import { WorkspacePage } from '../WorkspacePage';
import { renderWithClient } from '../../test/utils';
import { server } from '../../test/server';
import { useUIStore } from '../../stores/uiStore';
import i18n from '../../i18n';
import type { QueryResult, SessionDetail } from '../../api/generated/types.gen';

beforeEach(() => {
  useUIStore.setState({
    activeSessionId: null,
    sidebarCollapsed: false,
    hoveredSessionId: null,
    promptDraft: '',
  });
});

async function typeAndSubmit(text: string): Promise<void> {
  const input = screen.getByRole('textbox');
  await waitFor(() => {
    expect(input).not.toBeDisabled();
  });
  fireEvent.change(input, { target: { value: text } });
  fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });
}

const NEW_SESSION_ID = 'new-session-1234-5678-9000';
const ATTEMPT_ID = 'attempt-1234-5678-9000';
const ACCEPTED_QUERY_ID = 'accepted-1234-5678-9000';

function mockSubmitReturnsNewSession() {
  server.use(
    http.post('/api/v1/query/submit', async () => {
      const result: QueryResult = {
        kind: 'result',
        attempt_id: ATTEMPT_ID,
        session_id: NEW_SESSION_ID,
        question: 'What is revenue?',
        generated_sql: 'SELECT SUM(revenue) FROM sales;',
        columns: [{ name: 'sum', type: 'bigint' }],
        rows: [[100000]],
        row_count: 1,
        attempt_number: 1,
        is_last_auto_retry: false,
        accepted_query_id: ACCEPTED_QUERY_ID,
      };
      return HttpResponse.json(result, { status: 200 });
    }),
  );
}

function mockSessionDetailWithSameAttempt() {
  server.use(
    http.get('/api/v1/sessions/:sessionId', async ({ params }) => {
      const detail: SessionDetail = {
        id: params.sessionId as string,
        preview_text: 'What is revenue?',
        created_at: new Date().toISOString(),
        last_activity_at: new Date().toISOString(),
        attempts_total: 1,
        attempts_next_cursor: null,
        attempts: [
          {
            id: ACCEPTED_QUERY_ID,
            question_text: 'What is revenue?',
            generated_sql: 'SELECT SUM(revenue) FROM sales;',
            accepted_at: new Date().toISOString(),
            saved: true,
            feedback: undefined,
            result_columns: [{ name: 'sum', type: 'bigint' }],
            result_rows: [[100000]],
            result_row_count: 1,
          },
        ],
      };
      return HttpResponse.json(detail, { status: 200 });
    }),
  );
}

describe('WorkspacePage duplicate turn regression', () => {
  it('does not duplicate a turn after session detail refetches a persisted attempt', async () => {
    mockSubmitReturnsNewSession();
    mockSessionDetailWithSameAttempt();

    renderWithClient(<WorkspacePage />);

    await typeAndSubmit('What is revenue?');

    // Wait for submit response and UI update
    await waitFor(() => {
      expect(screen.getAllByTestId('user-bubble')).toHaveLength(1);
    }, { timeout: 5000 });

    await waitFor(() => {
      expect(screen.getAllByTestId('assistant-response-card')).toHaveLength(1);
    }, { timeout: 5000 });

    // Force session detail refetch by updating activeSessionId (simulating what useQuerySubmit does internally)
    await act(async () => {
      useUIStore.setState({ activeSessionId: NEW_SESSION_ID });
    });

    // Let react-query refetch session detail
    await waitFor(() => {
      expect(screen.getByText('What is revenue?')).toBeInTheDocument();
    }, { timeout: 5000 });

    // Critical assertion: exactly one user bubble, exactly one assistant card after refetch
    const userBubbles = screen.getAllByTestId('user-bubble');
    const assistantCards = screen.getAllByTestId('assistant-response-card');
    expect(userBubbles).toHaveLength(1);
    expect(assistantCards).toHaveLength(1);
  }, 15000);

  it('does not duplicate a follow-up turn after session detail refetches', async () => {
    mockSubmitReturnsNewSession();
    mockSessionDetailWithSameAttempt();

    renderWithClient(<WorkspacePage />);

    // First submit
    await typeAndSubmit('What is revenue?');
    await waitFor(() => {
      expect(screen.getAllByTestId('user-bubble')).toHaveLength(1);
    }, { timeout: 5000 });
    await waitFor(() => {
      expect(screen.getAllByTestId('assistant-response-card')).toHaveLength(1);
    }, { timeout: 5000 });

    await act(async () => {
      useUIStore.setState({ activeSessionId: NEW_SESSION_ID });
    });

    // Now simulate second submit in the same active session
    const FOLLOWUP_ATTEMPT_ID = 'attempt-followup-1234';
    const FOLLOWUP_ACCEPTED_ID = 'accepted-followup-1234';
    server.use(
      http.post('/api/v1/query/submit', async () => {
        const result: QueryResult = {
          kind: 'result',
          attempt_id: FOLLOWUP_ATTEMPT_ID,
          session_id: NEW_SESSION_ID,
          question: 'What is profit?',
          generated_sql: 'SELECT SUM(profit) FROM sales;',
          columns: [{ name: 'sum', type: 'bigint' }],
          rows: [[50000]],
          row_count: 1,
          attempt_number: 1,
          is_last_auto_retry: false,
          accepted_query_id: FOLLOWUP_ACCEPTED_ID,
        };
        return HttpResponse.json(result, { status: 200 });
      }),
    );
    server.use(
      http.get('/api/v1/sessions/:sessionId', async ({ params }) => {
        const detail: SessionDetail = {
          id: params.sessionId as string,
          preview_text: 'What is revenue?',
          created_at: new Date().toISOString(),
          last_activity_at: new Date().toISOString(),
          attempts_total: 2,
          attempts_next_cursor: null,
          attempts: [
            {
              id: ACCEPTED_QUERY_ID,
              question_text: 'What is revenue?',
              generated_sql: 'SELECT SUM(revenue) FROM sales;',
              accepted_at: new Date().toISOString(),
              saved: true,
              feedback: undefined,
              result_columns: [{ name: 'sum', type: 'bigint' }],
              result_rows: [[100000]],
              result_row_count: 1,
            },
            {
              id: FOLLOWUP_ACCEPTED_ID,
              question_text: 'What is profit?',
              generated_sql: 'SELECT SUM(profit) FROM sales;',
              accepted_at: new Date().toISOString(),
              saved: true,
              feedback: undefined,
              result_columns: [{ name: 'sum', type: 'bigint' }],
              result_rows: [[50000]],
              result_row_count: 1,
            },
          ],
        };
        return HttpResponse.json(detail, { status: 200 });
      }),
    );

    await typeAndSubmit('What is profit?');

    await waitFor(() => {
      expect(screen.getAllByTestId('user-bubble')).toHaveLength(2);
    }, { timeout: 5000 });

    await waitFor(() => {
      expect(screen.getAllByTestId('assistant-response-card')).toHaveLength(2);
    }, { timeout: 5000 });

    const userBubbles = screen.getAllByTestId('user-bubble');
    const assistantCards = screen.getAllByTestId('assistant-response-card');
    expect(userBubbles).toHaveLength(2);
    expect(assistantCards).toHaveLength(2);
  }, 15000);

  it('shows exactly one persisted turn after hard refresh (no locals)', async () => {
    mockSessionDetailWithSameAttempt();

    useUIStore.setState({ activeSessionId: NEW_SESSION_ID });
    renderWithClient(<WorkspacePage />);

    await waitFor(() => {
      expect(screen.getAllByTestId('user-bubble')).toHaveLength(1);
    }, { timeout: 5000 });

    await waitFor(() => {
      expect(screen.getAllByTestId('assistant-response-card')).toHaveLength(1);
    }, { timeout: 5000 });

    const userBubbles = screen.getAllByTestId('user-bubble');
    expect(userBubbles).toHaveLength(1);
  }, 10000);

  it.each([
    ['en', 'Load older messages'],
    ['ar', 'تحميل الرسائل الأقدم'],
  ])('loads older attempts explicitly in chronological order in %s', async (language, label) => {
    await i18n.changeLanguage(language);
    const requestedCursors: Array<string | null> = [];
    useUIStore.setState({ activeSessionId: NEW_SESSION_ID });
    server.use(
      http.get('/api/v1/sessions/:sessionId', ({ params, request }) => {
        const cursor = new URL(request.url).searchParams.get('attempt_cursor');
        requestedCursors.push(cursor);
        const base = {
          id: params.sessionId as string,
          connection_id: null,
          preview_text: '',
          created_at: '2026-08-10T00:00:00Z',
          last_activity_at: '2026-08-12T00:00:00Z',
          attempts_total: 2,
        };
        if (cursor === 'older-page') {
          return HttpResponse.json({
            ...base,
            attempts: [
              { id: 'newer-attempt', question_text: 'Newer question', generated_sql: '', accepted_at: '2026-08-12T00:00:00Z', saved: true },
              { id: 'older-attempt', question_text: 'Older question', generated_sql: '', accepted_at: '2026-08-10T00:00:00Z', saved: true },
            ],
            attempts_next_cursor: null,
          });
        }
        return HttpResponse.json({
          ...base,
          attempts: [
            { id: 'newer-attempt', question_text: 'Newer question', generated_sql: '', accepted_at: '2026-08-12T00:00:00Z', saved: true },
          ],
          attempts_next_cursor: 'older-page',
        });
      })
    );

    try {
      renderWithClient(<WorkspacePage />);
      const loadOlder = await screen.findByRole('button', { name: label });
      const conversation = document.querySelector<HTMLElement>('.workspace-conversation');
      expect(conversation).not.toBeNull();
      Object.defineProperty(conversation!, 'scrollHeight', {
        configurable: true,
        get: () => screen.queryAllByTestId('user-bubble').length * 100,
      });
      Object.defineProperty(conversation!, 'scrollTop', {
        configurable: true,
        value: 25,
        writable: true,
      });
      const animationFrame = vi
        .spyOn(window, 'requestAnimationFrame')
        .mockImplementation((callback) => {
          callback(0);
          return 1;
        });
      expect(requestedCursors).toEqual([null]);
      fireEvent.click(loadOlder);

      await waitFor(() => {
        expect(screen.getAllByTestId('user-bubble').map((bubble) => bubble.textContent)).toEqual([
          'Older question',
          'Newer question',
        ]);
      });
      expect(requestedCursors).toEqual([null, 'older-page']);
      expect(conversation!.scrollTop).toBe(125);
      animationFrame.mockRestore();
    } finally {
      await i18n.changeLanguage('en');
    }
  });

  it('retries a failed initial attempt page without showing stale turns', async () => {
    let requests = 0;
    useUIStore.setState({ activeSessionId: NEW_SESSION_ID });
    server.use(
      http.get('/api/v1/sessions/:sessionId', ({ params }) => {
        requests += 1;
        if (requests === 1) {
          return HttpResponse.json(
            { error: 'service_unavailable', message_key: 'error.service_unavailable' },
            { status: 503 }
          );
        }
        return HttpResponse.json({
          id: params.sessionId as string,
          connection_id: null,
          preview_text: '',
          created_at: '2026-08-10T00:00:00Z',
          last_activity_at: '2026-08-12T00:00:00Z',
          attempts: [],
          attempts_total: 0,
          attempts_next_cursor: null,
        });
      })
    );

    renderWithClient(<WorkspacePage />);
    const historyError = await screen.findByRole('alert', {
      name: 'Unable to load conversation history.',
    });
    expect(historyError).toHaveTextContent('Unable to load conversation history.');
    expect(screen.queryByTestId('user-bubble')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    await waitFor(() => expect(requests).toBe(2));
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  });
});
