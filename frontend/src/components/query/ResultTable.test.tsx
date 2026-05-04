import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ResultTable } from './ResultTable';
import { createWrapper } from '../../test/utils';
import type { QueryResult } from '../../api/generated/types.gen';

describe('ResultTable', () => {
  const mockResult: QueryResult = {
    attempt_id: 'test-id',
    sql: 'SELECT * FROM users;',
    columns: ['id', 'name'],
    rows: [['1', 'Alice'], ['2', 'Bob']],
    created_at: '2023-01-01T00:00:00Z',
    kind: 'result',
  };

  it('should render TanStack Table columns and rows', () => {
    render(<ResultTable result={mockResult} onAccept={vi.fn()} onReject={vi.fn()} onRegenerate={vi.fn()} />, { wrapper: createWrapper() });
    
    expect(screen.getByText('id')).toBeInTheDocument();
    expect(screen.getByText('name')).toBeInTheDocument();
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
  });

  it('should show "no results" message on zero rows', () => {
    const emptyResult = { ...mockResult, rows: [] };
    render(<ResultTable result={emptyResult} onAccept={vi.fn()} onReject={vi.fn()} onRegenerate={vi.fn()} />, { wrapper: createWrapper() });
    
    expect(screen.getByText(/no results/i)).toBeInTheDocument();
  });

  it('should display generated SQL', () => {
    render(<ResultTable result={mockResult} onAccept={vi.fn()} onReject={vi.fn()} onRegenerate={vi.fn()} />, { wrapper: createWrapper() });
    
    expect(screen.getByText('SELECT * FROM users;')).toBeInTheDocument();
  });

  it('should render actions and trigger callbacks', () => {
    const onAccept = vi.fn();
    const onReject = vi.fn();
    const onRegenerate = vi.fn();
    
    render(<ResultTable result={mockResult} onAccept={onAccept} onReject={onReject} onRegenerate={onRegenerate} />, { wrapper: createWrapper() });
    
    const acceptBtn = screen.getByRole('button', { name: /accept/i });
    const rejectBtn = screen.getByRole('button', { name: /reject/i });
    const regenBtn = screen.getByRole('button', { name: /regenerate/i });
    
    fireEvent.click(acceptBtn);
    expect(onAccept).toHaveBeenCalledWith('test-id');
    
    fireEvent.click(rejectBtn);
    expect(onReject).toHaveBeenCalledWith('test-id');
    
    fireEvent.click(regenBtn);
    expect(onRegenerate).toHaveBeenCalledWith('test-id');
  });
});
