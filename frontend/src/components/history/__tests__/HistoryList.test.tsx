import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { HistoryList, type HistoryItem } from '../HistoryList';

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
    const rows = screen.getAllByRole('row');
    // header + 2 data rows
    expect(rows).toHaveLength(3);
    // First data row corresponds to the most recent (2026-05-11)
    expect(rows[1]).toHaveTextContent('Total customers?');
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
    fireEvent.click(screen.getAllByRole('row')[1]);
    expect(onSelect).toHaveBeenCalledWith(sample[0].id);
  });
});
