import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AssistantResponseCard } from './AssistantResponseCard';
import type { QueryResult } from '../../api/generated/types.gen';

const mockResult: QueryResult = {
  kind: 'result',
  attempt_id: 'test-attempt-id',
  question: 'Test question',
  generated_sql: 'SELECT * FROM users;',
  columns: [{ name: 'id', type: 'bigint' }],
  rows: [[1]],
  row_count: 1,
  attempt_number: 1,
  is_last_auto_retry: false,
};

describe('AssistantResponseCard connection metadata', () => {
  it('renders connection display name and database type badge when metadata is provided', () => {
    render(
      <AssistantResponseCard
        sql="SELECT 1;"
        connectionName="Production DB"
        databaseType="postgresql"
      />
    );
    expect(screen.getByText('Production DB')).toBeInTheDocument();
    expect(screen.getByText('PostgreSQL')).toBeInTheDocument();
  });

  it('omits metadata cleanly when absent', () => {
    render(<AssistantResponseCard sql="SELECT 1;" />);
    expect(screen.queryByTestId('connection-metadata')).not.toBeInTheDocument();
  });

  it('preserves existing SQL/result rendering with metadata', () => {
    render(
      <AssistantResponseCard
        sql="SELECT * FROM users;"
        result={mockResult}
        connectionName="Analytics MySQL"
        databaseType="mysql"
      />
    );
    expect(screen.getByText('Generated SQL')).toBeInTheDocument();
    expect(screen.getByText('Results')).toBeInTheDocument();
    expect(screen.getByText('Analytics MySQL')).toBeInTheDocument();
    expect(screen.getByText('MySQL')).toBeInTheDocument();
  });

  it('preserves regenerate/delete actions with metadata', () => {
    render(
      <AssistantResponseCard
        sql="SELECT 1;"
        attemptId="attempt-123"
        onRegenerate={vi.fn()}
        savedQueryId="saved-456"
        onDelete={vi.fn()}
        connectionName="Test DB"
        databaseType="mssql"
      />
    );
    expect(screen.getByTestId('code-block-action-bar')).toBeInTheDocument();
    expect(screen.getByTestId('action-delete-result')).toBeInTheDocument();
    expect(screen.getByText('Test DB')).toBeInTheDocument();
    expect(screen.getByText('MS SQL Server')).toBeInTheDocument();
  });
});
