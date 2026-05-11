import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { HistoryList, type HistoryItem } from './HistoryList';

function setup(items: HistoryItem[], extraProps: Partial<React.ComponentProps<typeof HistoryList>> = {}) {
  return render(
    <HistoryList items={items} total={items.length} isLoading={false} {...extraProps} />
  );
}

const sample = [
  { id: '1', question_text: 'Total customers?', generated_sql: 'SELECT COUNT(*) FROM customer', accepted_at: '2026-05-11T10:00:00Z', schema: 'public' },
  { id: '2', question_text: 'Top revenue', generated_sql: 'SELECT ... FROM payment', accepted_at: '2026-05-10T10:00:00Z', schema: 'public' },
];

describe('HistoryList', () => {
  it('renders items in reverse-chronological order (SC-006)', () => {
    setup(sample);
    const rows = screen.getAllByTestId('history-row');
    expect(rows).toHaveLength(2);
    // First data row corresponds to the most recent (2026-05-11)
    expect(rows[0]).toHaveTextContent('Total customers?');
  });

  it('renders schema column for each row (SC-007)', () => {
    setup(sample);
    expect(screen.getAllByText('public')).toHaveLength(2);
  });

  it('filters by question text (FR-022 client-side filtering)', () => {
    setup(sample);
    const filterInput = screen.getByPlaceholderText(/filter/i);
    fireEvent.change(filterInput, { target: { value: 'revenue' } });
    expect(screen.queryByText('Total customers?')).not.toBeInTheDocument();
    expect(screen.getByText('Top revenue')).toBeInTheDocument();
  });

  it('renders empty state when no items (FR-021)', () => {
    setup([]);
    expect(screen.getByText(/no history yet/i)).toBeInTheDocument();
  });

  it('renders loading state (SC-009 — visible feedback)', () => {
    setup([], { isLoading: true });
    expect(screen.getByText(/loading history/i)).toBeInTheDocument();
  });

  it('calls onSelect when row is clicked (FR-023)', () => {
    const onSelect = vi.fn();
    setup(sample, { onSelect });
    fireEvent.click(screen.getAllByTestId('history-row')[0]);
    expect(onSelect).toHaveBeenCalledWith(sample[0].id);
  });

  it('renders load more button when hasMore is true', () => {
    setup(sample, { hasMore: true, onLoadMore: vi.fn() });
    expect(screen.getByRole('button', { name: /load more/i })).toBeInTheDocument();
  });

  it('calls onLoadMore when load more clicked', () => {
    const onLoadMore = vi.fn();
    setup(sample, { hasMore: true, onLoadMore });
    screen.getByRole('button', { name: /load more/i }).click();
    expect(onLoadMore).toHaveBeenCalled();
  });

  it('renders question, sql, and accepted date', () => {
    setup(sample);
    expect(screen.getByText('Total customers?')).toBeInTheDocument();
    expect(screen.getByText('SELECT COUNT(*) FROM customer')).toBeInTheDocument();
    expect(screen.getByText('Top revenue')).toBeInTheDocument();
    expect(screen.getByText('SELECT ... FROM payment')).toBeInTheDocument();
  });

  it('row is keyboard accessible (tabIndex + Enter/Space)', () => {
    const onSelect = vi.fn();
    setup(sample, { onSelect });
    const row = screen.getAllByTestId('history-row')[0];
    expect(row).toHaveAttribute('tabIndex', '0');
    fireEvent.keyDown(row, { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith(sample[0].id);
    onSelect.mockClear();
    fireEvent.keyDown(row, { key: ' ' });
    expect(onSelect).toHaveBeenCalledWith(sample[0].id);
  });
});
