import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ResultTable } from './ResultTable';
import { createWrapper } from '../../test/utils';
import type { QueryResult } from '../../api/generated/types.gen';

describe('ResultTable', () => {
  const mockResult: QueryResult = {
    attempt_id: 'test-id',
    generated_sql: 'SELECT * FROM users;',
    columns: [{ name: 'id', type: 'integer' }, { name: 'name', type: 'text' }],
    rows: [['1', 'Alice'], ['2', 'Bob']],
    kind: 'result',
    question: 'How many users?',
    row_count: 2,
    attempt_number: 1,
    is_last_auto_retry: false,
  };

  it('should render TanStack Table columns and rows', () => {
    render(<ResultTable result={mockResult} onAccept={vi.fn()} />, { wrapper: createWrapper() });
    
    expect(screen.getByText('id')).toBeInTheDocument();
    expect(screen.getByText('name')).toBeInTheDocument();
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
  });

  it('should show "no results" message on zero rows', () => {
    const emptyResult = { ...mockResult, rows: [] };
    render(<ResultTable result={emptyResult} onAccept={vi.fn()} />, { wrapper: createWrapper() });
    
    expect(screen.getByText(/no results/i)).toBeInTheDocument();
  });

  it('should display generated SQL', () => {
    render(<ResultTable result={mockResult} onAccept={vi.fn()} />, { wrapper: createWrapper() });
    
    expect(screen.getByText('SELECT * FROM users;')).toBeInTheDocument();
  });

  it('should render accept action and trigger callback', () => {
    const onAccept = vi.fn();
    
    render(<ResultTable result={mockResult} onAccept={onAccept} />, { wrapper: createWrapper() });
    
    const acceptBtn = screen.getByRole('button', { name: /accept/i });
    
    fireEvent.click(acceptBtn);
    expect(onAccept).toHaveBeenCalledWith('test-id');
  });
});
