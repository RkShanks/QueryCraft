import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import HistoryPage from './HistoryPage';
import { createWrapper } from '../test/utils';

vi.mock('../api/historyApi', () => ({
  listHistory: vi.fn(),
  getHistoryItem: vi.fn(),
}));
import * as historyApi from '../api/historyApi';

function renderPage() {
  return render(<HistoryPage />, { wrapper: createWrapper() });
}

describe('HistoryPage server-side search behavior (IS-GAP-032)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('sends the debounced search to the server and never auto-loads every page', async () => {
    const listCalls: Array<{ search?: string; cursor?: string }> = [];
    vi.mocked(historyApi.listHistory).mockImplementation(async (params) => {
      listCalls.push({ search: params.search, cursor: params.cursor });
      if (!params.search && !params.cursor) {
        return {
          items: [
            { id: '1', question_text: 'Customer count page one', generated_sql: 'SELECT 1', accepted_at: '2026-05-11T00:00:00Z' },
          ],
          total: 3,
          next_cursor: 'cursor-2',
        };
      }
      if (params.search === 'needle') {
        if (params.cursor) {
          return {
            items: [
              { id: '9', question_text: 'needle on a later page', generated_sql: 'SELECT 9', accepted_at: '2026-05-01T00:00:00Z' },
            ],
            total: 2,
            next_cursor: null,
          };
        }
        return {
          items: [],
          total: 2,
          next_cursor: 'cursor-search-2',
        };
      }
      return { items: [], total: 0, next_cursor: null };
    });

    renderPage();
    await waitFor(() => screen.getByText('Customer count page one'));

    fireEvent.change(screen.getByPlaceholderText(/filter/i), { target: { value: 'needle' } });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 350));
    });

    // Server-side search replaces the dataset; Load More stays explicit.
    expect(listCalls.some((call) => call.search === 'needle')).toBe(true);
    const searchCalls = listCalls.filter((call) => call.search === 'needle');
    expect(searchCalls).toHaveLength(1);
    expect(screen.queryByText('needle on a later page')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /load more/i }));
    await waitFor(() => expect(screen.getByText('needle on a later page')).toBeInTheDocument());
    expect(searchCalls).toHaveLength(1);
    expect(listCalls.filter((call) => call.search === 'needle' && call.cursor)).toHaveLength(1);

    // Total calls stay bounded: initial + search + explicit next page only.
    expect(listCalls).toHaveLength(3);
  });

  it('clears the selected detail when the active filter excludes it', async () => {
    vi.mocked(historyApi.listHistory).mockImplementation(async (params) => {
      if (params.search === 'excluded') {
        return {
          items: [{ id: 'other', question_text: 'Other match', generated_sql: 'SELECT O', accepted_at: '2026-05-02T00:00:00Z' }],
          total: 1,
          next_cursor: null,
        };
      }
      return {
        items: [{ id: 'sel-1', question_text: 'Selected question', generated_sql: 'SELECT S', accepted_at: '2026-05-11T00:00:00Z' }],
        total: 1,
        next_cursor: null,
      };
    });
    vi.mocked(historyApi.getHistoryItem).mockResolvedValue({
      id: 'sel-1', question_text: 'Selected question', generated_sql: 'SELECT S', accepted_at: '2026-05-11T00:00:00Z', llm_provider: 'ollama',
    });

    renderPage();
    await waitFor(() => screen.getByText('Selected question'));
    fireEvent.click(screen.getByRole('button', { name: /selected question/i }));
    await waitFor(() => expect(screen.getByTestId('history-detail')).toBeInTheDocument());

    fireEvent.change(screen.getByPlaceholderText(/filter/i), { target: { value: 'excluded' } });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 350));
    });

    await waitFor(() => expect(screen.getByText(/select an item/i)).toBeInTheDocument());
    expect(historyApi.getHistoryItem).toHaveBeenCalledTimes(1);
  });

  it('places list/search errors in the list panel and detail errors in the detail panel', async () => {
    vi.mocked(historyApi.listHistory).mockRejectedValue(new Error('list down'));
    renderPage();

    await waitFor(() => expect(screen.getAllByRole('alert').length).toBeGreaterThan(0));

    // The list alert lives inside the list panel container.
    const listPanel = document.querySelector('[data-testid="history-list-panel"]');
    expect(listPanel).not.toBeNull();
    expect(listPanel?.querySelectorAll('[role="alert"]').length ?? 0).toBeGreaterThanOrEqual(1);
    const detailPanel = document.querySelector('[data-testid="history-detail-panel"]');
    expect(detailPanel?.querySelectorAll('[role="alert"]').length ?? 0).toBe(0);
  });

  it('shows a localized no-match state for searches without results', async () => {
    vi.mocked(historyApi.listHistory).mockResolvedValue({ items: [], total: 0, next_cursor: null });
    renderPage();
    fireEvent.change(screen.getByPlaceholderText(/filter/i), { target: { value: 'zzz-no-match' } });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 350));
    });
    await waitFor(() =>
      expect(screen.getByTestId('history-list-panel').textContent).toMatch(/no.*(match|results)/i)
    );
  });
});
