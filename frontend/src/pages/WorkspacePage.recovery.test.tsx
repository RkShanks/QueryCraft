import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { useLocation } from 'react-router-dom';
import type {
  AcceptedQueryDetail,
  ErrorResponse,
  QueryResult,
  SessionDetail,
} from '../api/generated/types.gen';
import i18n from '../i18n';
import { beginSessionDeletion, resetSessionDeletionLifecycle } from '../sessionDeletionLifecycle';
import { server } from '../test/server';
import { renderWithClient } from '../test/utils';
import { useUIStore } from '../stores/uiStore';
import { WorkspacePage } from './WorkspacePage';
import { PERMISSIONS } from '../auth/permissions';

const SESSION_A = '550e8400-e29b-41d4-a716-446655440101';
const SESSION_B = '550e8400-e29b-41d4-a716-446655440102';
const SAVED_QUERY_ID = '550e8400-e29b-41d4-a716-446655440103';
const ORIGINAL_ATTEMPT_ID = '550e8400-e29b-41d4-a716-446655440104';
const CONNECTION_ID = '550e8400-e29b-41d4-a716-446655440004';

function sessionDetail(sessionId: string, question = 'Stored question'): SessionDetail {
  return {
    id: sessionId,
    connection_id: CONNECTION_ID,
    preview_text: question,
    created_at: '2026-08-13T12:00:00Z',
    last_activity_at: '2026-08-13T12:01:00Z',
    attempts_total: 1,
    attempts_next_cursor: null,
    attempts: [
      {
        id: SAVED_QUERY_ID,
        question_text: question,
        generated_sql: 'SELECT 7 AS exact_value',
        accepted_at: '2026-08-13T12:01:00Z',
        saved: true,
        result_columns: [{ name: 'exact_value', type: 'integer' }],
        result_rows: [[7]],
        result_row_count: 1,
      },
    ],
  };
}

function acceptedQueryDetail(): AcceptedQueryDetail {
  return {
    id: SAVED_QUERY_ID,
    question_text: 'Stored question',
    generated_sql: 'SELECT 7 AS exact_value',
    accepted_at: '2026-08-13T12:01:00Z',
    llm_provider: 'deterministic',
    database_connection_id: CONNECTION_ID,
    result_columns: [{ name: 'exact_value', type: 'integer' }],
    result_rows: [[7]],
    result_row_count: 1,
  };
}

function errorResponse(error = 'service_unavailable'): ErrorResponse {
  return { error, message_key: `error.${error}` };
}

function mockStoredSession(): void {
  server.use(
    http.get('/api/v1/sessions/:sessionId', ({ params }) =>
      HttpResponse.json(sessionDetail(params.sessionId as string))
    )
  );
  useUIStore.setState({ activeSessionId: SESSION_A });
}

async function submitLocalTurn(): Promise<void> {
  const input = screen.getByRole('textbox');
  await waitFor(() => expect(input).not.toBeDisabled());
  fireEvent.change(input, { target: { value: 'Original retry question' } });
  fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });
  await screen.findByTestId('assistant-response-card');
}

function LocationProbe() {
  return <output data-testid="location-path">{useLocation().pathname}</output>;
}

beforeEach(async () => {
  resetSessionDeletionLifecycle();
  useUIStore.setState({
    activeSessionId: null,
    sidebarCollapsed: false,
    hoveredSessionId: null,
    promptDraft: '',
  });
  await i18n.changeLanguage('en');
});

describe('Workspace result deletion recovery', () => {
  it('restores the exact turn after a definite failure and retries once', async () => {
    let deleteRequests = 0;
    mockStoredSession();
    server.use(
      http.delete('/api/v1/history/:queryId', () => {
        deleteRequests += 1;
        return deleteRequests === 1
          ? HttpResponse.json(errorResponse(), { status: 503 })
          : new HttpResponse(null, { status: 204 });
      })
    );
    renderWithClient(<WorkspacePage />);

    fireEvent.click(await screen.findByTestId('action-delete-result'));

    const recovery = await screen.findByRole('alert', {
      name: 'Delete failed. The result was restored.',
    });
    expect(screen.getByText('Stored question')).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: '7' })).toBeInTheDocument();
    expect(screen.getByTestId('action-delete-result')).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent('service_unavailable');
    fireEvent.click(within(recovery).getByRole('button', { name: 'Retry' }));

    await waitFor(() => expect(deleteRequests).toBe(2));
    await waitFor(() => expect(screen.queryByText('Stored question')).not.toBeInTheDocument());
  });

  it('keeps an ambiguously committed delete removed after authoritative absence', async () => {
    mockStoredSession();
    server.use(
      http.delete('/api/v1/history/:queryId', () => HttpResponse.error()),
      http.get('/api/v1/history/:queryId', () =>
        HttpResponse.json(errorResponse('not_found'), { status: 404 })
      )
    );
    renderWithClient(<WorkspacePage />);

    fireEvent.click(await screen.findByTestId('action-delete-result'));

    await waitFor(() => expect(screen.queryByText('Stored question')).not.toBeInTheDocument());
    expect(screen.queryByRole('alert', { name: /delete/i })).not.toBeInTheDocument();
  });

  it('restores an ambiguously uncommitted delete from authoritative presence', async () => {
    mockStoredSession();
    server.use(
      http.delete('/api/v1/history/:queryId', () => HttpResponse.error()),
      http.get('/api/v1/history/:queryId', () => HttpResponse.json(acceptedQueryDetail()))
    );
    renderWithClient(<WorkspacePage />);

    fireEvent.click(await screen.findByTestId('action-delete-result'));

    expect(await screen.findByRole('alert', {
      name: 'Delete failed. The result was restored.',
    })).toBeInTheDocument();
    expect(screen.getByText('Stored question')).toBeInTheDocument();
  });

  it('restores with an explicit uncertain state when reconciliation also fails', async () => {
    mockStoredSession();
    server.use(
      http.delete('/api/v1/history/:queryId', () => HttpResponse.error()),
      http.get('/api/v1/history/:queryId', () => HttpResponse.error())
    );
    renderWithClient(<WorkspacePage />);

    fireEvent.click(await screen.findByTestId('action-delete-result'));

    expect(await screen.findByRole('alert', {
      name: 'Delete status is uncertain. The result was restored.',
    })).toBeInTheDocument();
    expect(screen.getByTestId('action-delete-result')).toBeInTheDocument();
  });

  it('suppresses duplicate delete clicks while the first request is pending', async () => {
    let deleteRequests = 0;
    let releaseDelete: (() => void) | undefined;
    const deleteGate = new Promise<void>((resolve) => {
      releaseDelete = resolve;
    });
    mockStoredSession();
    server.use(
      http.delete('/api/v1/history/:queryId', async () => {
        deleteRequests += 1;
        await deleteGate;
        return new HttpResponse(null, { status: 204 });
      })
    );
    renderWithClient(<WorkspacePage />);
    const deleteButton = await screen.findByTestId('action-delete-result');

    fireEvent.click(deleteButton);
    fireEvent.click(deleteButton);

    await waitFor(() => expect(deleteRequests).toBe(1));
    releaseDelete?.();
  });

  it('ignores a late delete failure after switching sessions', async () => {
    let releaseDelete: (() => void) | undefined;
    const deleteGate = new Promise<void>((resolve) => {
      releaseDelete = resolve;
    });
    mockStoredSession();
    server.use(
      http.get('/api/v1/sessions/:sessionId', ({ params }) =>
        HttpResponse.json(sessionDetail(params.sessionId as string, params.sessionId === SESSION_B ? 'Session B question' : 'Session A question'))
      ),
      http.delete('/api/v1/history/:queryId', async () => {
        await deleteGate;
        return HttpResponse.json(errorResponse(), { status: 503 });
      })
    );
    renderWithClient(<WorkspacePage />);
    fireEvent.click(await screen.findByTestId('action-delete-result'));

    await act(async () => {
      useUIStore.getState().setActiveSessionId(SESSION_B);
    });
    expect(await screen.findByText('Session B question')).toBeInTheDocument();
    releaseDelete?.();

    await waitFor(() => expect(screen.getByText('Session B question')).toBeInTheDocument());
    expect(screen.queryByText('Session A question')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert', { name: /delete/i })).not.toBeInTheDocument();
  });
});

describe('Workspace regenerate recovery', () => {
  it('preserves the prior card, suppresses duplicates, and retries the original attempt', async () => {
    const attemptIds: string[] = [];
    let releaseFirstRegenerate: (() => void) | undefined;
    const firstRegenerateGate = new Promise<void>((resolve) => {
      releaseFirstRegenerate = resolve;
    });
    server.use(
      http.post('/api/v1/query/submit', () =>
        HttpResponse.json({
          kind: 'result',
          attempt_id: ORIGINAL_ATTEMPT_ID,
          session_id: SESSION_A,
          question: 'Original retry question',
          generated_sql: 'SELECT 7 AS original_value',
          columns: [{ name: 'original_value', type: 'integer' }],
          rows: [[7]],
          row_count: 1,
          attempt_number: 1,
          is_last_auto_retry: false,
          accepted_query_id: SAVED_QUERY_ID,
        } satisfies QueryResult)
      ),
      http.get('/api/v1/sessions/:sessionId', ({ params }) =>
        HttpResponse.json({ ...sessionDetail(params.sessionId as string), attempts: [], attempts_total: 0 })
      ),
      http.post('/api/v1/query/regenerate', async ({ request }) => {
        const body = (await request.json()) as { attempt_id: string };
        attemptIds.push(body.attempt_id);
        if (attemptIds.length === 1) {
          await firstRegenerateGate;
          return HttpResponse.json(errorResponse(), { status: 503 });
        }
        return HttpResponse.json({
          kind: 'result',
          attempt_id: '550e8400-e29b-41d4-a716-446655440105',
          session_id: SESSION_A,
          question: 'Original retry question',
          generated_sql: 'SELECT 8 AS regenerated_value',
          columns: [{ name: 'regenerated_value', type: 'integer' }],
          rows: [[8]],
          row_count: 1,
          attempt_number: 2,
          is_last_auto_retry: false,
          accepted_query_id: '550e8400-e29b-41d4-a716-446655440106',
        } satisfies QueryResult);
      })
    );
    renderWithClient(<WorkspacePage />);
    await submitLocalTurn();
    fireEvent.click(screen.getByTestId('sql-toggle-btn'));
    await waitFor(() =>
      expect(screen.getByTestId('assistant-response-card')).toHaveTextContent(
        'SELECT 7 AS original_value'
      )
    );
    const regenerateButton = screen.getByTestId('action-regenerate');

    fireEvent.click(regenerateButton);
    fireEvent.click(regenerateButton);

    expect(screen.getByTestId('assistant-response-card')).toHaveTextContent('SELECT 7 AS original_value');
    expect(screen.getByRole('status')).toHaveTextContent('Regenerating the original attempt…');
    await waitFor(() => expect(attemptIds).toEqual([ORIGINAL_ATTEMPT_ID]));
    releaseFirstRegenerate?.();

    const recovery = await screen.findByRole('alert', {
      name: 'Regeneration failed. The previous result is still available.',
    });
    expect(screen.getByTestId('assistant-response-card')).toHaveTextContent('SELECT 7 AS original_value');
    expect(screen.getByRole('cell', { name: '7' })).toBeInTheDocument();
    fireEvent.click(within(recovery).getByRole('button', { name: 'Retry' }));

    await waitFor(() => expect(attemptIds).toEqual([ORIGINAL_ATTEMPT_ID, ORIGINAL_ATTEMPT_ID]));
    expect(await screen.findByRole('cell', { name: '8' })).toBeInTheDocument();
  });

  it('refetches and removes Retry after a terminal inactive-attempt failure', async () => {
    let sessionRequests = 0;
    useUIStore.setState({ activeSessionId: SESSION_A });
    server.use(
      http.get('/api/v1/sessions/:sessionId', ({ params }) => {
        sessionRequests += 1;
        return HttpResponse.json({ ...sessionDetail(params.sessionId as string), attempts: [], attempts_total: 0 });
      }),
      http.post('/api/v1/query/submit', () =>
        HttpResponse.json({
          kind: 'result',
          attempt_id: ORIGINAL_ATTEMPT_ID,
          session_id: SESSION_A,
          question: 'Original retry question',
          generated_sql: 'SELECT 7 AS original_value',
          columns: [{ name: 'original_value', type: 'integer' }],
          rows: [[7]],
          row_count: 1,
          attempt_number: 1,
          is_last_auto_retry: false,
        } satisfies QueryResult)
      ),
      http.post('/api/v1/query/regenerate', () =>
        HttpResponse.json(errorResponse('attempt_invalid'), { status: 400 })
      )
    );
    renderWithClient(<WorkspacePage />);
    await submitLocalTurn();
    fireEvent.click(screen.getByTestId('action-regenerate'));

    const terminal = await screen.findByRole('alert', {
      name: 'This result can no longer be regenerated. The latest session state was loaded.',
    });
    expect(within(terminal).queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
    await waitFor(() => expect(sessionRequests).toBeGreaterThanOrEqual(2));
  });

  it('ignores regenerate settlement after the source session is deleted and switched', async () => {
    let releaseRegenerate: (() => void) | undefined;
    const regenerateGate = new Promise<void>((resolve) => {
      releaseRegenerate = resolve;
    });
    useUIStore.setState({ activeSessionId: SESSION_A });
    server.use(
      http.get('/api/v1/sessions/:sessionId', ({ params }) =>
        HttpResponse.json(
          params.sessionId === SESSION_B
            ? sessionDetail(SESSION_B, 'Session B remains active')
            : { ...sessionDetail(SESSION_A), attempts: [], attempts_total: 0 }
        )
      ),
      http.post('/api/v1/query/submit', () =>
        HttpResponse.json({
          kind: 'result',
          attempt_id: ORIGINAL_ATTEMPT_ID,
          session_id: SESSION_A,
          question: 'Original retry question',
          generated_sql: 'SELECT 7 AS original_value',
          columns: [{ name: 'original_value', type: 'integer' }],
          rows: [[7]],
          row_count: 1,
          attempt_number: 1,
          is_last_auto_retry: false,
        } satisfies QueryResult)
      ),
      http.post('/api/v1/query/regenerate', async () => {
        await regenerateGate;
        return HttpResponse.json({
          kind: 'result',
          attempt_id: '550e8400-e29b-41d4-a716-446655440107',
          session_id: SESSION_A,
          question: 'Original retry question',
          generated_sql: 'SELECT 999 AS stale_value',
          columns: [{ name: 'stale_value', type: 'integer' }],
          rows: [[999]],
          row_count: 1,
          attempt_number: 2,
          is_last_auto_retry: false,
        } satisfies QueryResult);
      })
    );
    renderWithClient(<WorkspacePage />);
    await submitLocalTurn();
    fireEvent.click(screen.getByTestId('action-regenerate'));

    beginSessionDeletion(SESSION_A);
    await act(async () => {
      useUIStore.getState().setActiveSessionId(SESSION_B);
    });
    expect(await screen.findByText('Session B remains active')).toBeInTheDocument();
    releaseRegenerate?.();

    await waitFor(() => expect(screen.getByText('Session B remains active')).toBeInTheDocument());
    expect(document.body).not.toHaveTextContent('stale_value');
    expect(screen.queryByRole('alert', { name: /regeneration/i })).not.toBeInTheDocument();
  });
});

describe('Workspace connection recovery', () => {
  it('navigates authorized users to connection management', async () => {
    server.use(
      http.post('/api/v1/query/submit', () =>
        HttpResponse.json(errorResponse('connection_disabled'), { status: 400 })
      )
    );
    renderWithClient(
      <>
        <WorkspacePage />
        <LocationProbe />
      </>,
      [PERMISSIONS.QUERY_SUBMIT, PERMISSIONS.ADMIN_CONNECTIONS_MANAGE]
    );

    const input = screen.getByRole('textbox');
    await waitFor(() => expect(input).not.toBeDisabled());
    fireEvent.change(input, { target: { value: 'Connection status question' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });
    fireEvent.click(await screen.findByRole('button', { name: 'Manage connections' }));

    expect(screen.getByTestId('location-path')).toHaveTextContent('/admin/connections');
  });

  it('shows guidance instead of a dead action without management permission', async () => {
    server.use(
      http.get('/api/v1/auth/me', () =>
        HttpResponse.json({
          id: 'd290f1ee-6c54-4b01-90e6-d701748f0851',
          username: 'analyst',
          display_name: 'Analyst User',
          role: 'analyst',
          permissions: [PERMISSIONS.QUERY_SUBMIT],
        })
      ),
      http.post('/api/v1/query/submit', () =>
        HttpResponse.json(errorResponse('connection_no_schema'), { status: 400 })
      )
    );
    renderWithClient(<WorkspacePage />, [PERMISSIONS.QUERY_SUBMIT]);

    const input = screen.getByRole('textbox');
    await waitFor(() => expect(input).not.toBeDisabled());
    fireEvent.change(input, { target: { value: 'Schema status question' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    expect(
      await screen.findByText('Ask a connection administrator to review this connection.')
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Manage connections' })).not.toBeInTheDocument();
  });

  it('retries with the original question, session, and immutable connection', async () => {
    const requestBodies: Array<Record<string, unknown>> = [];
    let releaseRetry: (() => void) | undefined;
    const retryGate = new Promise<void>((resolve) => {
      releaseRetry = resolve;
    });
    mockStoredSession();
    server.use(
      http.post('/api/v1/query/submit', async ({ request }) => {
        requestBodies.push((await request.json()) as Record<string, unknown>);
        if (requestBodies.length === 1) {
          return HttpResponse.json(errorResponse('query_execution_failed'), { status: 400 });
        }
        await retryGate;
        return HttpResponse.json({
          kind: 'result',
          attempt_id: '550e8400-e29b-41d4-a716-446655440115',
          session_id: SESSION_A,
          question: 'Immutable connection question',
          generated_sql: 'SELECT 9 AS recovered_value',
          columns: [{ name: 'recovered_value', type: 'integer' }],
          rows: [[9]],
          row_count: 1,
          attempt_number: 1,
          is_last_auto_retry: false,
          accepted_query_id: '550e8400-e29b-41d4-a716-446655440116',
        } satisfies QueryResult);
      })
    );
    renderWithClient(<WorkspacePage />);

    const input = screen.getByRole('textbox');
    await waitFor(() => expect(input).not.toBeDisabled());
    fireEvent.change(input, { target: { value: 'Immutable connection question' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });
    const retry = await screen.findByRole('button', { name: 'Retry' });
    retry.focus();
    fireEvent.click(retry);
    fireEvent.click(retry);

    expect(retry).toHaveFocus();
    expect(retry).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('Retrying the original question…');
    await waitFor(() => expect(requestBodies).toHaveLength(2));
    expect(requestBodies).toEqual([
      {
        question: 'Immutable connection question',
        session_id: SESSION_A,
        connection_id: CONNECTION_ID,
      },
      {
        question: 'Immutable connection question',
        session_id: SESSION_A,
        connection_id: CONNECTION_ID,
      },
    ]);
    releaseRetry?.();
    expect(await screen.findByRole('cell', { name: '9' })).toBeInTheDocument();
  });
});
