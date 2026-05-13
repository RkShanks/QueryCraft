import { describe, it, expect, beforeEach } from 'vitest';
import { screen, waitFor, act, fireEvent } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
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

  it('renders Delete button on result turn when accepted_query_id is returned', async () => {
    renderWithClient(<WorkspacePage />);
    await typeAndSubmit('How many actors?');

    await waitFor(() => {
      expect(screen.getByTestId('assistant-response-card')).toBeInTheDocument();
    }, { timeout: 5000 });

    // auto-save returns accepted_query_id so delete button should appear
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

    fireEvent.click(screen.getByTestId('action-delete-result'));

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
});
