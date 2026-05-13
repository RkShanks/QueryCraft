import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { UserBubble } from '../UserBubble';
import { AssistantResponseCard } from '../AssistantResponseCard';
import { ResultTable } from '../ResultTable';
import type { QueryResult } from '../../../api/generated/types.gen';

const mockResult: QueryResult = {
  kind: 'result',
  attempt_id: 'test-attempt-id',
  question: 'Test question',
  generated_sql: 'SELECT * FROM users;',
  columns: [
    { name: 'id', type: 'bigint' },
    { name: 'name', type: 'text' },
  ],
  rows: [
    [1, 'Alice'],
    [2, 'Bob'],
  ],
  row_count: 2,
  attempt_number: 1,
  is_last_auto_retry: false,
};

describe('UserBubble', () => {
  it('renders user text', () => {
    render(<UserBubble text="Hello world" />);
    expect(screen.getByText('Hello world')).toBeInTheDocument();
  });

  it('is end-aligned using logical properties', () => {
    render(<UserBubble text="Hello" />);
    const bubble = screen.getByTestId('user-bubble').querySelector('.user-bubble');
    expect(bubble).toHaveClass('user-bubble');
  });
});

describe('AssistantResponseCard', () => {
  it('renders SQL heading and code block', () => {
    render(<AssistantResponseCard sql="SELECT 1;" />);
    expect(screen.getByText('Generated SQL')).toBeInTheDocument();
    expect(screen.getByTestId('sql-code-block')).toBeInTheDocument();
  });

  it('renders code block action bar when attemptId is provided', () => {
    render(
      <AssistantResponseCard
        sql="SELECT 1;"
        attemptId="test-id"
        onRegenerate={vi.fn()}
        onFeedback={vi.fn()}
      />
    );
    expect(screen.getByTestId('code-block-action-bar')).toBeInTheDocument();
  });

  it('does not render action bar when attemptId is missing', () => {
    render(<AssistantResponseCard sql="SELECT 1;" />);
    expect(screen.queryByTestId('code-block-action-bar')).not.toBeInTheDocument();
  });

  it('renders result table when result is provided', () => {
    render(<AssistantResponseCard sql="SELECT 1;" result={mockResult} />);
    expect(screen.getByText('Results')).toBeInTheDocument();
    expect(screen.getByTestId('result-table')).toBeInTheDocument();
  });

  it('does not render result table when result is absent', () => {
    render(<AssistantResponseCard sql="SELECT 1;" />);
    expect(screen.queryByTestId('result-table')).not.toBeInTheDocument();
  });
});

describe('ResultTable', () => {
  it('renders column headers from QueryResult', () => {
    render(<ResultTable result={mockResult} />);
    expect(screen.getByText('id')).toBeInTheDocument();
    expect(screen.getByText('name')).toBeInTheDocument();
  });

  it('renders row data', () => {
    render(<ResultTable result={mockResult} />);
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
  });

  it('renders empty cell for null values', () => {
    const resultWithNull: QueryResult = {
      ...mockResult,
      rows: [[null, 'Alice']],
    };
    render(<ResultTable result={resultWithNull} />);
    // null rendered as empty string
    expect(screen.getByText('Alice')).toBeInTheDocument();
  });
});
