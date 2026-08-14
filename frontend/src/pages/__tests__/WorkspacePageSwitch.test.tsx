import { describe, it, expect, beforeEach } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { http, HttpResponse, delay } from 'msw';

import { WorkspacePage } from '../WorkspacePage';
import { renderWithClient } from '../../test/utils';
import { server } from '../../test/server';
import { useUIStore } from '../../stores/uiStore';
import type {
  QueryResult,
  SessionDetail,
  SessionSummary,
  UserConnectionListResponse,
} from '../../api/generated/types.gen';

const POSTGRES_CONNECTION_ID = '550e8400-e29b-41d4-a716-446655440021';
const MYSQL_CONNECTION_ID = '550e8400-e29b-41d4-a716-446655440022';
const SESSION_ID = '550e8400-e29b-41d4-a716-446655440003';
const NO_METADATA_SESSION_ID = '550e8400-e29b-41d4-a716-446655440023';

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

describe('WorkspacePage mid-session DB switch (T-464)', () => {
  it('first submitted turn gets selected connection metadata', async () => {
    server.use(
      http.get('/api/v1/connections', async () => {
        await delay(10);
        return HttpResponse.json({
          connections: [
            { id: POSTGRES_CONNECTION_ID, display_name: 'PostgreSQL DB', database_type: 'postgresql' },
          ],
        } satisfies UserConnectionListResponse);
      }),
      http.post('/api/v1/query/submit', async () => {
        await delay(10);
        return HttpResponse.json({
          kind: 'result',
          attempt_id: '550e8400-e29b-41d4-a716-446655440024',
          session_id: SESSION_ID,
          question: 'Show me users',
          generated_sql: 'SELECT * FROM users;',
          columns: [{ name: 'id', type: 'bigint' }],
          rows: [[1]],
          row_count: 1,
          attempt_number: 1,
          is_last_auto_retry: false,
          accepted_query_id: '550e8400-e29b-41d4-a716-446655440025',
        } satisfies QueryResult);
      })
    );

    renderWithClient(<WorkspacePage />);

    // Wait for auto-select to happen (single connection)
    await waitFor(() => {
      expect(screen.getByText('PostgreSQL DB')).toBeInTheDocument();
    });

    await typeAndSubmit('Show me users');

    await waitFor(() => {
      expect(screen.getByTestId('assistant-response-card')).toBeInTheDocument();
    }, { timeout: 5000 });

    // Metadata should be rendered on the card
    const meta = screen.getByTestId('connection-metadata');
    expect(meta).toBeInTheDocument();
    expect(meta).toHaveTextContent('PostgreSQL DB');
    expect(meta).toHaveTextContent('PostgreSQL');
  }, 15000);

  it('after switching connection, new turn gets new metadata and prior turn keeps old', async () => {
    let submitCount = 0;
    server.use(
      http.get('/api/v1/connections', async () => {
        await delay(10);
        return HttpResponse.json({
          connections: [
            { id: POSTGRES_CONNECTION_ID, display_name: 'PostgreSQL DB', database_type: 'postgresql' },
            { id: MYSQL_CONNECTION_ID, display_name: 'MySQL DB', database_type: 'mysql' },
          ],
        } satisfies UserConnectionListResponse);
      }),
      http.get('/api/v1/sessions/:sessionId', async ({ params }) => {
        await delay(10);
        return HttpResponse.json({
          id: params.sessionId as string,
          connection_id: submitCount >= 1 ? MYSQL_CONNECTION_ID : POSTGRES_CONNECTION_ID,
          preview_text: 'Session detail',
          created_at: new Date().toISOString(),
          last_activity_at: new Date().toISOString(),
          attempts: [],
          attempts_total: 0,
          attempts_next_cursor: null,
        } satisfies SessionDetail);
      }),
      http.patch('/api/v1/sessions/:sessionId/connection', async ({ params }) => {
        await delay(10);
        return HttpResponse.json({
          id: params.sessionId as string,
          connection_id: MYSQL_CONNECTION_ID,
          preview_text: 'Session detail',
          created_at: new Date().toISOString(),
          last_activity_at: new Date().toISOString(),
        } satisfies SessionSummary);
      }),
      http.post('/api/v1/query/submit', async () => {
        await delay(10);
        submitCount++;
        return HttpResponse.json({
          kind: 'result',
          attempt_id: submitCount === 1
            ? '550e8400-e29b-41d4-a716-446655440026'
            : '550e8400-e29b-41d4-a716-446655440027',
          session_id: SESSION_ID,
          question: submitCount === 1 ? 'First query' : 'Second query',
          generated_sql: 'SELECT 1;',
          columns: [{ name: 'id', type: 'bigint' }],
          rows: [[1]],
          row_count: 1,
          attempt_number: 1,
          is_last_auto_retry: false,
          accepted_query_id: submitCount === 1
            ? '550e8400-e29b-41d4-a716-446655440028'
            : '550e8400-e29b-41d4-a716-446655440029',
        } satisfies QueryResult);
      })
    );

    renderWithClient(<WorkspacePage />);

    // Wait for selector to render with two connections
    await waitFor(() => {
      expect(screen.getByTestId('database-selector')).toBeInTheDocument();
    });

    // Select PostgreSQL first (need explicit select with 2 connections)
    fireEvent.click(screen.getByTestId('database-selector-trigger'));
    await waitFor(() => {
      expect(screen.getByTestId(`database-selector-option-${POSTGRES_CONNECTION_ID}`)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId(`database-selector-option-${POSTGRES_CONNECTION_ID}`));

    await waitFor(() => {
      expect(screen.getByText('PostgreSQL DB')).toBeInTheDocument();
    });

    // First submit with PostgreSQL
    await typeAndSubmit('First query');

    await waitFor(() => {
      expect(screen.getAllByTestId('assistant-response-card')).toHaveLength(1);
    }, { timeout: 5000 });

    // Switch to MySQL
    fireEvent.click(screen.getByTestId('database-selector-trigger'));
    await waitFor(() => {
      expect(screen.getByTestId(`database-selector-option-${MYSQL_CONNECTION_ID}`)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId(`database-selector-option-${MYSQL_CONNECTION_ID}`));

    await waitFor(() => {
      expect(screen.getByText('MySQL DB')).toBeInTheDocument();
    });

    // Second submit with MySQL
    await typeAndSubmit('Second query');

    await waitFor(() => {
      expect(screen.getAllByTestId('assistant-response-card')).toHaveLength(2);
    }, { timeout: 5000 });

    const cards = screen.getAllByTestId('assistant-response-card');
    expect(cards).toHaveLength(2);

    // First card should still have PostgreSQL metadata
    expect(cards[0]).toHaveTextContent('PostgreSQL DB');
    expect(cards[0]).toHaveTextContent('PostgreSQL');

    // Second card should have MySQL metadata
    expect(cards[1]).toHaveTextContent('MySQL DB');
    expect(cards[1]).toHaveTextContent('MySQL');
  }, 20000);

  it('missing metadata does not break card rendering', async () => {
    // This test verifies that when a turn has no connection metadata
    // (e.g., from history before T-465 backend changes), the card still renders
    // We simulate this by loading a session with attempts that have no connection metadata
    useUIStore.setState({ activeSessionId: NO_METADATA_SESSION_ID });

    server.use(
      http.get('/api/v1/sessions/:sessionId', async ({ params }) => {
        if (params.sessionId === NO_METADATA_SESSION_ID) {
          return HttpResponse.json({
            id: NO_METADATA_SESSION_ID,
            connection_id: null,
            preview_text: 'Session without meta',
            created_at: new Date().toISOString(),
            last_activity_at: new Date().toISOString(),
            attempts: [
              {
                id: '550e8400-e29b-41d4-a716-446655440030',
                question_text: 'Old query',
                generated_sql: 'SELECT 1;',
                accepted_at: new Date().toISOString(),
                saved: true,
                result_columns: [{ name: 'id', type: 'bigint' }],
                result_rows: [[1]],
                result_row_count: 1,
              },
            ],
            attempts_total: 1,
            attempts_next_cursor: null,
          } satisfies SessionDetail);
        }
        return HttpResponse.json({
          id: params.sessionId as string,
          connection_id: null,
          preview_text: 'Session',
          created_at: new Date().toISOString(),
          last_activity_at: new Date().toISOString(),
          attempts: [],
          attempts_total: 0,
          attempts_next_cursor: null,
        } satisfies SessionDetail);
      })
    );

    renderWithClient(<WorkspacePage />);

    await waitFor(() => {
      expect(screen.getByTestId('assistant-response-card')).toBeInTheDocument();
    }, { timeout: 5000 });

    // Card should render without metadata section
    expect(screen.queryByTestId('connection-metadata')).not.toBeInTheDocument();
    // But the card itself should be present with result table
    expect(screen.getByTestId('result-table')).toBeInTheDocument();
  }, 15000);
});
