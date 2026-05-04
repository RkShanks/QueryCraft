import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import HistoryPage from './HistoryPage';
import { createWrapper } from '../test/utils';
import { server } from '../test/server';
import { http, HttpResponse } from 'msw';

describe('HistoryPage', () => {
  it('should render history title and list', async () => {
    render(<HistoryPage />, { wrapper: createWrapper() });

    expect(screen.getByText(/query history/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('How many users?')).toBeInTheDocument();
    });
  });

  it('should render empty state when no history', async () => {
    server.use(
      http.get('/api/v1/history', () => {
        return HttpResponse.json({ items: [], total: 0, next_cursor: null });
      })
    );

    render(<HistoryPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/no accepted queries yet/i)).toBeInTheDocument();
    });
  });
});
