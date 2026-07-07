import { describe, it, expect, beforeEach } from 'vitest';
import { screen, waitFor, act, fireEvent } from '@testing-library/react';
import { http, HttpResponse, delay } from 'msw';

import { WorkspacePage } from '../WorkspacePage';
import { renderWithClient } from '../../test/utils';
import { server } from '../../test/server';
import { useUIStore } from '../../stores/uiStore';
import { setSubmitScenario } from '../../test/handlers';

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

describe('WorkspacePage first-submit UX', () => {
  it('renders empty state when no active session', () => {
    renderWithClient(<WorkspacePage />);
    expect(screen.getByText('Start a new conversation')).toBeInTheDocument();
  });

  it('preserves the submitted turn after first submit creates a new session', async () => {
    renderWithClient(<WorkspacePage />);

    expect(screen.getByText('Start a new conversation')).toBeInTheDocument();

    await typeAndSubmit('How many actors?');

    await waitFor(() => {
      expect(screen.getByTestId('assistant-loading')).toBeInTheDocument();
    });

    expect(screen.getByText('How many actors?')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId('assistant-response-card')).toBeInTheDocument();
    });

    expect(screen.queryByText('Start a new conversation')).not.toBeInTheDocument();

    const state = useUIStore.getState();
    expect(state.activeSessionId).toBe('550e8400-e29b-41d4-a716-446655440003');
  }, 10000);

  it('renders copy, regenerate, and delete actions on successful live submit', async () => {
    server.use(
      http.get('/api/v1/sessions/:sessionId', async () => {
        return HttpResponse.json({
          id: '550e8400-e29b-41d4-a716-446655440003',
          preview_text: '',
          created_at: new Date().toISOString(),
          last_activity_at: new Date().toISOString(),
          attempts: [],
        }, { status: 200 });
      }),
    );

    renderWithClient(<WorkspacePage />);
    await typeAndSubmit('How many actors?');

    await waitFor(() => {
      expect(screen.getByTestId('assistant-response-card')).toBeInTheDocument();
    }, { timeout: 5000 });

    // auto-save returns accepted_query_id so delete button should appear
    expect(screen.getByTestId('action-copy')).toBeInTheDocument();
    expect(screen.getByTestId('action-regenerate')).toBeInTheDocument();
    expect(screen.getByTestId('action-delete-result')).toBeInTheDocument();
  }, 10000);

  it('keeps live attempt actions when refreshed session history contains the saved result', async () => {
    server.use(
      http.get('/api/v1/sessions/:sessionId', async ({ params }) => {
        return HttpResponse.json({
          id: params.sessionId as string,
          preview_text: '',
          created_at: new Date().toISOString(),
          last_activity_at: new Date().toISOString(),
          attempts: [
            {
              id: 'f9e8d7c6-b5a4-4c3b-2a1d-0e9f8d7c6b5a',
              question_text: 'How many actors?',
              generated_sql: 'SELECT COUNT(*) FROM users;',
              accepted_at: new Date().toISOString(),
              saved: true,
              feedback: 1,
              result_columns: [{ name: 'count', type: 'bigint' }],
              result_rows: [[42]],
              result_row_count: 1,
            },
          ],
        }, { status: 200 });
      }),
    );

    renderWithClient(<WorkspacePage />);
    await typeAndSubmit('How many actors?');

    await waitFor(() => {
      expect(screen.getAllByTestId('assistant-response-card')).toHaveLength(1);
    }, { timeout: 5000 });

    expect(screen.getByTestId('action-copy')).toBeInTheDocument();
    expect(screen.getByTestId('action-regenerate')).toBeInTheDocument();
    expect(screen.getByTestId('action-delete-result')).toBeInTheDocument();
  }, 10000);

  it('clicking Delete calls DELETE /history/{id}', async () => {
    let deletedId: string | undefined;

    server.use(
      http.delete('/api/v1/history/:query_id', ({ params }) => {
        deletedId = params.query_id as string;
        return new HttpResponse(null, { status: 204 });
      }),
    );

    renderWithClient(<WorkspacePage />);
    await typeAndSubmit('How many actors?');

    await waitFor(() => {
      expect(screen.getByTestId('action-delete-result')).toBeInTheDocument();
    }, { timeout: 5000 });

    const deleteButtons = screen.getAllByTestId('action-delete-result');
    fireEvent.click(deleteButtons[deleteButtons.length - 1]);

    await waitFor(() => {
      expect(deletedId).toBeDefined();
    });
  }, 15000);

  it('renders result table from loaded session detail attempts with result payload', async () => {
    useUIStore.setState({ activeSessionId: 'session-with-result' });

    renderWithClient(<WorkspacePage />);

    await waitFor(() => {
      expect(screen.getByTestId('assistant-response-card')).toBeInTheDocument();
    }, { timeout: 5000 });

    expect(screen.getByText('count')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByTestId('result-table')).toBeInTheDocument();
    expect(screen.getByTestId('action-copy')).toBeInTheDocument();
    expect(screen.queryByTestId('action-regenerate')).not.toBeInTheDocument();
    expect(screen.getByTestId('action-delete-result')).toBeInTheDocument();
  }, 10000);

  it('optimistically removes historical (session-loaded) turn on delete', async () => {
    useUIStore.setState({ activeSessionId: 'session-with-delete-test' });

    renderWithClient(<WorkspacePage />);

    await waitFor(() => {
      expect(screen.getByTestId('assistant-response-card')).toBeInTheDocument();
    }, { timeout: 5000 });

    const deleteBtn = screen.getByTestId('action-delete-result');
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(screen.queryByTestId('assistant-response-card')).not.toBeInTheDocument();
    }, { timeout: 5000 });
  }, 15000);

  it('clears local turns on New Chat (activeSessionId set to null)', async () => {
    renderWithClient(<WorkspacePage />);

    await typeAndSubmit('Some question?');

    await waitFor(() => {
      expect(screen.getByTestId('assistant-response-card')).toBeInTheDocument();
    }, { timeout: 5000 });

    await act(async () => {
      useUIStore.getState().setActiveSessionId(null);
    });

    await waitFor(() => {
      expect(screen.getByText('Start a new conversation')).toBeInTheDocument();
    }, { timeout: 5000 });
  }, 15000);

  it('uses result.attempt_id for regenerate actions', async () => {
    let capturedRegenerateId: string | undefined;

    const EXPECTED_ATTEMPT_ID = 'a1b2c3d4-5e6f-4a5b-8c7d-9e0f1a2b3c4d';

    server.use(
      http.post('/api/v1/query/regenerate', async ({ request }) => {
        const body = (await request.json()) as { attempt_id: string };
        capturedRegenerateId = body.attempt_id;
        return HttpResponse.json({
          kind: 'result',
          attempt_id: 'regen-attempt-id',
          session_id: '550e8400-e29b-41d4-a716-446655440003',
          question: 'How many actors?',
          generated_sql: 'SELECT COUNT(*) FROM users;',
          columns: [{ name: 'count', type: 'bigint' }],
          rows: [[42]],
          row_count: 1,
          attempt_number: 2,
          is_last_auto_retry: false,
        });
      }),
    );

    renderWithClient(<WorkspacePage />);
    await typeAndSubmit('How many actors?');

    await waitFor(() => {
      expect(screen.getByTestId('assistant-response-card')).toBeInTheDocument();
    }, { timeout: 5000 });

    const regenerateBtn = screen.getByTestId('action-regenerate');
    fireEvent.click(regenerateBtn);

    await waitFor(() => {
      expect(capturedRegenerateId).toBeDefined();
    });

    expect(capturedRegenerateId).toBe(EXPECTED_ATTEMPT_ID);
    expect(capturedRegenerateId).not.toMatch(/^turn-/);
  }, 15000);

  it('second submit (follow-up) in same session preserves both turns', async () => {
    renderWithClient(<WorkspacePage />);

    await typeAndSubmit('First question?');

    await waitFor(() => {
      expect(screen.getAllByTestId('assistant-response-card')).toHaveLength(1);
    }, { timeout: 5000 });

    await typeAndSubmit('Second question?');

    await waitFor(() => {
      expect(screen.getAllByTestId('assistant-response-card')).toHaveLength(2);
    }, { timeout: 5000 });

    expect(screen.getByText('First question?')).toBeInTheDocument();
    expect(screen.getByText('Second question?')).toBeInTheDocument();

    expect(screen.queryByText('Start a new conversation')).not.toBeInTheDocument();
  }, 15000);
});

describe('WorkspacePage submit scenarios', () => {
  it('shows evaluator rejection card when evaluator rejects', async () => {
    setSubmitScenario('evaluator_rejected');
    renderWithClient(<WorkspacePage />);

    await typeAndSubmit('Bad query?');

    await waitFor(() => {
      expect(screen.getByTestId('rejection-banner')).toBeInTheDocument();
    }, { timeout: 5000 });
  }, 10000);

  it('shows concurrent error alert toast with logical layout class end-4 instead of physical right-4', async () => {
    setSubmitScenario('concurrent');
    renderWithClient(<WorkspacePage />);

    await typeAndSubmit('Concurrent query?');

    await waitFor(() => {
      const alertEl = screen.getByRole('alert');
      expect(alertEl).toBeInTheDocument();
      expect(alertEl.className).toContain('end-4');
      expect(alertEl.className).not.toContain('right-4');
    }, { timeout: 5000 });
  }, 10000);
});

describe('WorkspacePage multi-connection selection (T-460)', () => {
  it('prompt disabled with two connections until explicit selection, submit sends selected connection_id', async () => {
    let capturedBody: Record<string, unknown> | undefined;

    server.use(
      http.get('/api/v1/connections', async () => {
        await delay(10);
        return HttpResponse.json(
          {
            connections: [
              {
                id: 'conn-pg-001',
                display_name: 'PostgreSQL DB',
                database_type: 'postgresql',
              },
              {
                id: 'conn-mysql-002',
                display_name: 'MySQL DB',
                database_type: 'mysql',
              },
            ],
          },
          { status: 200 }
        );
      }),
      http.post('/api/v1/query/submit', async ({ request }) => {
        await delay(10);
        capturedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            kind: 'result',
            attempt_id: 'attempt-460-001',
            session_id: '550e8400-e29b-41d4-a716-446655440003',
            question: 'Show me users',
            generated_sql: 'SELECT * FROM users;',
            columns: [{ name: 'id', type: 'bigint' }],
            rows: [[1]],
            row_count: 1,
            attempt_number: 1,
            is_last_auto_retry: false,
            accepted_query_id: 'accepted-460-001',
          },
          { status: 200 }
        );
      })
    );

    renderWithClient(<WorkspacePage />);

    // Selector should render with two connections
    await waitFor(() => {
      expect(screen.getByTestId('database-selector')).toBeInTheDocument();
    });

    // Prompt should be disabled because no connection is auto-selected when >1 available
    const input = screen.getByRole('textbox');
    expect(input).toBeDisabled();

    // Open selector and select MySQL connection
    fireEvent.click(screen.getByTestId('database-selector-trigger'));
    await waitFor(() => {
      expect(screen.getByTestId('database-selector-option-conn-mysql-002')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('database-selector-option-conn-mysql-002'));

    // Prompt should now be enabled
    await waitFor(() => {
      expect(input).not.toBeDisabled();
    });

    // Type and submit
    fireEvent.change(input, { target: { value: 'Show me users' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(screen.getByTestId('assistant-response-card')).toBeInTheDocument();
    }, { timeout: 5000 });

    // Assert captured POST body includes selected connection_id
    expect(capturedBody).toBeDefined();
    expect(capturedBody!.connection_id).toBe('conn-mysql-002');
  }, 15000);
});
