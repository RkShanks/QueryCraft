import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, waitFor, act, fireEvent } from '@testing-library/react';
import { http, HttpResponse, delay } from 'msw';

import { WorkspacePage } from '../WorkspacePage';
import { renderWithClient } from '../../test/utils';
import { server } from '../../test/server';
import { useUIStore } from '../../stores/uiStore';

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
            { id: 'conn-pg-001', display_name: 'PostgreSQL DB', database_type: 'postgresql' },
          ],
        });
      }),
      http.post('/api/v1/query/submit', async () => {
        await delay(10);
        return HttpResponse.json({
          kind: 'result',
          attempt_id: 'attempt-464-001',
          session_id: '550e8400-e29b-41d4-a716-446655440003',
          question: 'Show me users',
          generated_sql: 'SELECT * FROM users;',
          columns: [{ name: 'id', type: 'bigint' }],
          rows: [[1]],
          row_count: 1,
          attempt_number: 1,
          is_last_auto_retry: false,
          accepted_query_id: 'accepted-464-001',
        });
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
    expect(screen.getByTestId('connection-metadata')).toBeInTheDocument();
    expect(screen.getByText('PostgreSQL DB')).toBeInTheDocument();
  }, 15000);

  it('after switching connection, new turn gets new metadata and prior turn keeps old', async () => {
    let submitCount = 0;
    server.use(
      http.get('/api/v1/connections', async () => {
        await delay(10);
        return HttpResponse.json({
          connections: [
            { id: 'conn-pg-001', display_name: 'PostgreSQL DB', database_type: 'postgresql' },
            { id: 'conn-mysql-002', display_name: 'MySQL DB', database_type: 'mysql' },
          ],
        });
      }),
      http.patch('/api/v1/sessions/:sessionId/connection', async ({ params }) => {
        await delay(10);
        return HttpResponse.json({
          id: params.sessionId as string,
          connection_id: 'conn-mysql-002',
          preview_text: 'Session detail',
          created_at: new Date().toISOString(),
          last_activity_at: new Date().toISOString(),
        });
      }),
      http.post('/api/v1/query/submit', async () => {
        await delay(10);
        submitCount++;
        return HttpResponse.json({
          kind: 'result',
          attempt_id: `attempt-464-00${submitCount}`,
          session_id: '550e8400-e29b-41d4-a716-446655440003',
          question: submitCount === 1 ? 'First query' : 'Second query',
          generated_sql: 'SELECT 1;',
          columns: [{ name: 'id', type: 'bigint' }],
          rows: [[1]],
          row_count: 1,
          attempt_number: 1,
          is_last_auto_retry: false,
          accepted_query_id: `accepted-464-00${submitCount}`,
        });
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
      expect(screen.getByTestId('database-selector-option-conn-pg-001')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('database-selector-option-conn-pg-001'));

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
      expect(screen.getByTestId('database-selector-option-conn-mysql-002')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('database-selector-option-conn-mysql-002'));

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
    expect(cards[0]).toHaveTextContent('postgresql');

    // Second card should have MySQL metadata
    expect(cards[1]).toHaveTextContent('MySQL DB');
    expect(cards[1]).toHaveTextContent('mysql');
  }, 20000);

  it('missing metadata does not break card rendering', async () => {
    server.use(
      http.get('/api/v1/connections', async () => {
        await delay(10);
        return HttpResponse.json({
          connections: [
            { id: 'conn-pg-001', display_name: 'PostgreSQL DB', database_type: 'postgresql' },
          ],
        });
      }),
      http.post('/api/v1/query/submit', async () => {
        await delay(10);
        return HttpResponse.json({
          kind: 'result',
          attempt_id: 'attempt-464-003',
          session_id: '550e8400-e29b-41d4-a716-446655440003',
          question: 'No meta',
          generated_sql: 'SELECT 1;',
          columns: [{ name: 'id', type: 'bigint' }],
          rows: [[1]],
          row_count: 1,
          attempt_number: 1,
          is_last_auto_retry: false,
          accepted_query_id: 'accepted-464-003',
        });
      })
    );

    renderWithClient(<WorkspacePage />);

    await waitFor(() => {
      expect(screen.getByText('PostgreSQL DB')).toBeInTheDocument();
    });

    await typeAndSubmit('No meta');

    await waitFor(() => {
      expect(screen.getByTestId('assistant-response-card')).toBeInTheDocument();
    }, { timeout: 5000 });

    // Card should render without metadata section
    expect(screen.queryByTestId('connection-metadata')).not.toBeInTheDocument();
    // But the card itself should be present with result table
    expect(screen.getByTestId('result-table')).toBeInTheDocument();
  }, 15000);
});
