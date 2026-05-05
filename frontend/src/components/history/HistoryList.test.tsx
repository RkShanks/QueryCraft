import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { HistoryList } from './HistoryList';
import { createWrapper } from '../../test/utils';
import type { AcceptedQuerySummary } from '../../api/generated/types.gen';

describe('HistoryList', () => {
  const mockItems: AcceptedQuerySummary[] = [
    {
      id: '1',
      question_text: 'How many users?',
      generated_sql: 'SELECT COUNT(*) FROM users;',
      accepted_at: '2023-01-01T00:00:00Z',
    },
    {
      id: '2',
      question_text: 'Top 10 orders by amount',
      generated_sql: 'SELECT * FROM orders ORDER BY amount DESC LIMIT 10;',
      accepted_at: '2023-01-02T00:00:00Z',
    },
  ];

  it('should render history items with question, sql, and accepted date', () => {
    render(
      <HistoryList items={mockItems} />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByText('How many users?')).toBeInTheDocument();
    expect(screen.getByText('SELECT COUNT(*) FROM users;')).toBeInTheDocument();
    expect(screen.getByText('Top 10 orders by amount')).toBeInTheDocument();
    expect(screen.getByText('SELECT * FROM orders ORDER BY amount DESC LIMIT 10;')).toBeInTheDocument();
  });

  it('should render empty state when no items', () => {
    render(
      <HistoryList items={[]} />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByText(/no accepted queries yet/i)).toBeInTheDocument();
  });

  it('should render load more button when hasMore is true', () => {
    render(
      <HistoryList items={mockItems} hasMore onLoadMore={vi.fn()} />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByRole('button', { name: /load more/i })).toBeInTheDocument();
  });

  it('should call onLoadMore when load more clicked', () => {
    const onLoadMore = vi.fn();
    render(
      <HistoryList items={mockItems} hasMore onLoadMore={onLoadMore} />,
      { wrapper: createWrapper() }
    );

    screen.getByRole('button', { name: /load more/i }).click();
    expect(onLoadMore).toHaveBeenCalled();
  });
});
