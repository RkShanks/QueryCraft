import { describe, it, expect, beforeEach, vi } from 'vitest';
import { screen, waitFor, fireEvent } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { WorkspacePage } from '../WorkspacePage';
import { renderWithClient } from '../../test/utils';
import { server } from '../../test/server';
import { useUIStore } from '../../stores/uiStore';

// We want to test T-460 behavior specifically
describe('WorkspacePage Selector Integration (T-460)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useUIStore.setState({
      activeSessionId: null,
      sidebarCollapsed: false,
      hoveredSessionId: null,
      promptDraft: '',
    });
  });

  it('renders DatabaseSelector when connections are available', async () => {
    server.use(
      http.get('/api/v1/connections', () => {
        return HttpResponse.json({
          connections: [
            { id: 'conn-1', display_name: 'Postgres DB', database_type: 'postgresql' },
            { id: 'conn-2', display_name: 'MySQL DB', database_type: 'mysql' },
          ],
        });
      })
    );

    renderWithClient(<WorkspacePage />);

    // Wait for the selector trigger to render
    await waitFor(() => {
      expect(screen.getByTestId('database-selector-trigger')).toBeInTheDocument();
    });

    expect(screen.getByText('Select database')).toBeInTheDocument();
  });

  it('disables prompt textarea and send button when multiple connections exist and none selected', async () => {
    server.use(
      http.get('/api/v1/connections', () => {
        return HttpResponse.json({
          connections: [
            { id: 'conn-1', display_name: 'Postgres DB', database_type: 'postgresql' },
            { id: 'conn-2', display_name: 'MySQL DB', database_type: 'mysql' },
          ],
        });
      })
    );

    renderWithClient(<WorkspacePage />);

    await waitFor(() => {
      expect(screen.getByTestId('database-selector-trigger')).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Select a database above/i);
    expect(textarea).toBeDisabled();

    const sendBtn = screen.getByTestId('prompt-send');
    expect(sendBtn).toBeDisabled();

    expect(screen.getByTestId('prompt-input-warning')).toHaveTextContent(
      'Please select a database first.'
    );
  });

  it('auto-selects single available connection and enables the prompt', async () => {
    server.use(
      http.get('/api/v1/connections', () => {
        return HttpResponse.json({
          connections: [
            { id: 'conn-1', display_name: 'Postgres DB', database_type: 'postgresql' },
          ],
        });
      })
    );

    renderWithClient(<WorkspacePage />);

    await waitFor(() => {
      expect(screen.getByTestId('database-selector-trigger')).toBeInTheDocument();
    });

    // Should display selected connection name
    expect(screen.getByText('Postgres DB')).toBeInTheDocument();

    // Textarea and send button should be enabled (subject to text being typed)
    const textarea = screen.getByPlaceholderText(/Ask a question about your data/i);
    expect(textarea).not.toBeDisabled();
  });

  it('empty connections state prevents submission and shows localized guidance', async () => {
    server.use(
      http.get('/api/v1/connections', () => {
        return HttpResponse.json({
          connections: [],
        });
      })
    );

    renderWithClient(<WorkspacePage />);

    await waitFor(() => {
      expect(screen.getByTestId('database-selector-empty')).toBeInTheDocument();
    });

    const textarea = screen.getByPlaceholderText(/Please add a database connection/i);
    expect(textarea).toBeDisabled();

    const sendBtn = screen.getByTestId('prompt-send');
    expect(sendBtn).toBeDisabled();

    expect(screen.getByTestId('prompt-input-warning')).toHaveTextContent(
      'Please add a database connection first.'
    );
  });
});
