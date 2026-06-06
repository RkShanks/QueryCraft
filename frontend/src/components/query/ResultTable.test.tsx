import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ResultTable } from './ResultTable';
import { createWrapper } from '../../test/utils';
import type { ColumnMeta, QueryResult } from '../../api/generated/types.gen';
import en from '../../locales/en.json';
import ar from '../../locales/ar.json';

let mockLanguage = 'en';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: unknown) => {
      if (typeof options === 'string') return options;
      const opts = options as Record<string, unknown> | undefined;
      const defaultValue = opts?.defaultValue as string | undefined;
      const translations = mockLanguage === 'ar' ? ar : en;
      const value = (translations as Record<string, string>)[key] ?? defaultValue ?? key;
      return value.replace(/\{\{(\w+)\}\}/g, (_, match) => String(opts?.[match] ?? `{{${match}}}`));
    },
    i18n: {
      changeLanguage: (lng: string) => {
        mockLanguage = lng;
        return Promise.resolve();
      },
      language: mockLanguage,
    },
  }),
  initReactI18next: {
    type: '3rdParty',
    init: () => {},
  },
}));

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

  it('should render Reject and Regenerate buttons', () => {
    render(
      <ResultTable
        result={mockResult}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onRegenerate={vi.fn()}
        canRegenerate
      />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByRole('button', { name: /reject/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /regenerate/i })).toBeInTheDocument();
  });

  it('should call onReject when Reject clicked', () => {
    const onReject = vi.fn();
    render(
      <ResultTable
        result={mockResult}
        onAccept={vi.fn()}
        onReject={onReject}
        onRegenerate={vi.fn()}
        canRegenerate
      />,
      { wrapper: createWrapper() }
    );

    fireEvent.click(screen.getByRole('button', { name: /reject/i }));
    expect(onReject).toHaveBeenCalledWith('test-id');
  });

  it('should call onRegenerate when Regenerate clicked', () => {
    const onRegenerate = vi.fn();
    render(
      <ResultTable
        result={mockResult}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onRegenerate={onRegenerate}
        canRegenerate
      />,
      { wrapper: createWrapper() }
    );

    fireEvent.click(screen.getByRole('button', { name: /regenerate/i }));
    expect(onRegenerate).toHaveBeenCalledWith('test-id');
  });

  it('should hide Regenerate button when canRegenerate is false', () => {
    render(
      <ResultTable
        result={mockResult}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onRegenerate={vi.fn()}
        canRegenerate={false}
      />,
      { wrapper: createWrapper() }
    );

    expect(screen.queryByRole('button', { name: /regenerate/i })).not.toBeInTheDocument();
  });

  it('should show last auto retry indicator when is_last_auto_retry is true', () => {
    const lastRetryResult = { ...mockResult, is_last_auto_retry: true };
    render(
      <ResultTable
        result={lastRetryResult}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        onRegenerate={vi.fn()}
        canRegenerate={false}
      />,
      { wrapper: createWrapper() }
    );

    expect(screen.getByText(/last auto retry/i)).toBeInTheDocument();
  });

  beforeEach(() => {
    mockLanguage = 'en';
  });

  it('should render masked column indicator in English (Masked)', () => {
    mockLanguage = 'en';
    const maskedResult: QueryResult = {
      ...mockResult,
      columns: [
        { name: 'id', type: 'integer' },
        { name: 'secret_name', type: 'text', masked: true } as ColumnMeta & { masked?: boolean },
      ],
      rows: [['1', '***']],
    };

    render(<ResultTable result={maskedResult} onAccept={vi.fn()} />, { wrapper: createWrapper() });

    // Normal column header is rendered, but no masked text next to it
    expect(screen.getByText('id')).toBeInTheDocument();

    // Masked column header is rendered with the Masked badge
    expect(screen.getByText('secret_name')).toBeInTheDocument();
    expect(screen.getByText('Masked')).toBeInTheDocument();
  });

  it('should render masked column indicator in Arabic (محجوب)', () => {
    mockLanguage = 'ar';
    const maskedResult: QueryResult = {
      ...mockResult,
      columns: [
        { name: 'id', type: 'integer' },
        { name: 'secret_name', type: 'text', masked: true } as ColumnMeta & { masked?: boolean },
      ],
      rows: [['1', '***']],
    };

    render(<ResultTable result={maskedResult} onAccept={vi.fn()} />, { wrapper: createWrapper() });

    // Normal column header is rendered, but no masked text next to it
    expect(screen.getByText('id')).toBeInTheDocument();

    // Masked column header is rendered with the Arabic badge
    expect(screen.getByText('secret_name')).toBeInTheDocument();
    expect(screen.getByText('محجوب')).toBeInTheDocument();
  });

  it('should use i18n for all visible strings', () => {
    render(<ResultTable result={mockResult} onAccept={vi.fn()} />, { wrapper: createWrapper() });

    expect(screen.getByText(/generated sql/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /accept/i })).toBeInTheDocument();
  });
});
