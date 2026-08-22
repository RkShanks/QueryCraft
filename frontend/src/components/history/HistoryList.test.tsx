import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { HistoryList, type HistoryItem } from './HistoryList';
import { formatDateTime } from '../../i18n/format';

function setup(items: HistoryItem[], extraProps: Partial<React.ComponentProps<typeof HistoryList>> = {}) {
  return render(
    <HistoryList items={items} total={items.length} isLoading={false} {...extraProps} />
  );
}

const sample = [
  { id: '1', question_text: 'Total customers?', generated_sql: 'SELECT COUNT(*) FROM customer', accepted_at: '2026-05-11T10:00:00Z' },
  { id: '2', question_text: 'Top revenue', generated_sql: 'SELECT ... FROM payment', accepted_at: '2026-05-10T10:00:00Z' },
];

const sampleWithConnection = [
  {
    id: '1',
    question_text: 'Total customers?',
    generated_sql: 'SELECT COUNT(*) FROM customer',
    accepted_at: '2026-05-11T10:00:00Z',
    database_connection_id: 'conn-pg-001',
    database_connection_name: 'Production PG',
    database_type: 'postgresql' as const,
  },
  {
    id: '2',
    question_text: 'Top revenue',
    generated_sql: 'SELECT ... FROM payment',
    accepted_at: '2026-05-10T10:00:00Z',
    database_connection_id: 'conn-mysql-002',
    database_connection_name: 'Warehouse MySQL',
    database_type: 'mysql' as const,
  },
];

describe('HistoryList', () => {
  it('renders items in reverse-chronological order (SC-006)', () => {
    setup(sample);
    const rows = screen.getAllByTestId('history-row');
    expect(rows).toHaveLength(2);
    // First data row corresponds to the most recent (2026-05-11)
    expect(rows[0]).toHaveTextContent('Total customers?');
  });

  it('renders a controlled search box without client-side dataset filtering (IS-GAP-032)', () => {
    const onSearchChange = vi.fn();
    setup(sample, { search: 'revenue', onSearchChange });
    const filterInput = screen.getByPlaceholderText(/filter/i);
    expect(filterInput).toHaveValue('revenue');
    // Filtering is server-side now: the component shows whatever the page
    // feeds it and forwards keystrokes upward.
    fireEvent.change(filterInput, { target: { value: 'needle' } });
    expect(onSearchChange).toHaveBeenCalledWith('needle');
    // Unfiltered rows stay visible until the page supplies filtered results.
    expect(screen.getByText('Total customers?')).toBeInTheDocument();
  });

  it('does not render phantom schema column (G-007/O-009)', () => {
    setup(sample);
    expect(screen.queryByText('Schema')).not.toBeInTheDocument();
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

  it('keeps compact history SQL previews LTR in Arabic chrome (P4-FR-100)', () => {
    setup(sample);
    expect(screen.getByText('SELECT COUNT(*) FROM customer')).toHaveAttribute('dir', 'ltr');
  });

  it.each([
    ['English', 'ltr'],
    ['Arabic', 'rtl'],
  ])('isolates history list metadata in the %s layout', (_locale, direction) => {
    const { container } = render(
      <div dir={direction}>
        <HistoryList
          items={sampleWithConnection}
          total={sampleWithConnection.length}
          isLoading={false}
        />
      </div>
    );

    for (const item of sampleWithConnection) {
      expect(screen.getByText(item.generated_sql)).toHaveAttribute('dir', 'ltr');
      expect(
        screen.getByText(formatDateTime(item.accepted_at))
      ).toHaveAttribute('dir', 'ltr');
      expect(screen.getByText(item.database_connection_name)).toHaveAttribute('dir', 'auto');
    }
    for (const databaseType of ['PostgreSQL', 'MySQL']) {
      expect(screen.getByText(databaseType)).toHaveAttribute('dir', 'ltr');
    }
    expect(container.firstChild).toHaveAttribute('dir', direction);
  });

  it('row is a real button with native keyboard activation (IS-GAP-032)', () => {
    const onSelect = vi.fn();
    setup(sample, { onSelect });
    const row = screen.getAllByTestId('history-row')[0];
    expect(row.tagName).toBe('BUTTON');
    expect(row).not.toHaveAttribute('tabindex');
    fireEvent.click(row);
    expect(onSelect).toHaveBeenCalledWith(sample[0].id);
    // Native button semantics handle Enter/Space; no custom keydown handlers.
  });

  it('renders a semantic list without table imitation (IS-GAP-032)', () => {
    setup(sample);
    expect(screen.getByRole('list')).toBeInTheDocument();
    expect(screen.queryAllByRole('columnheader')).toHaveLength(0);
  });

  it('debounce ownership moved upstream: keystrokes propagate immediately (IS-GAP-032)', () => {
    const onSearchChange = vi.fn();
    setup(sample, { search: '', onSearchChange });
    const filterInput = screen.getByPlaceholderText(/filter/i);
    fireEvent.change(filterInput, { target: { value: 'n' } });
    expect(onSearchChange).toHaveBeenCalledWith('n');
  });

  it('renders display name and database type badge when metadata is present (T-465)', () => {
    setup(sampleWithConnection);
    const rows = screen.getAllByTestId('history-row');
    expect(rows[0]).toHaveTextContent('Production PG');
    expect(rows[0]).toHaveTextContent('PostgreSQL');
    expect(rows[0]).not.toHaveTextContent('conn-pg-001');
    expect(rows[1]).toHaveTextContent('Warehouse MySQL');
    expect(rows[1]).toHaveTextContent('MySQL');
    expect(rows[1]).not.toHaveTextContent('conn-mysql-002');
  });

  it('does not render connection metadata badge when metadata is absent (T-465)', () => {
    setup(sample);
    const rows = screen.getAllByTestId('history-row');
    expect(rows[0]).toHaveTextContent('-');
    expect(rows[1]).toHaveTextContent('-');
  });
});
