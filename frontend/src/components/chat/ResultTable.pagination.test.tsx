import { fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { ColumnMeta, QueryResult } from '../../api/generated/types.gen';
import i18n from '../../i18n';
import { ResultTable } from './ResultTable';

const columns: ColumnMeta[] = [
  { name: 'row_number', type: 'integer' },
  { name: 'protected_value', type: 'text', masked: true },
];

function resultWithRows(count: number, attemptId = 'attempt-page-one'): QueryResult {
  return {
    kind: 'result',
    attempt_id: attemptId,
    question: 'List rows',
    generated_sql: 'SELECT row_number, protected_value FROM generated_rows',
    columns,
    rows: Array.from({ length: count }, (_, index) => [index + 1, `masked-${index + 1}`]),
    row_count: count,
    attempt_number: 1,
    is_last_auto_retry: false,
  };
}

function renderedBodyRows(): HTMLElement[] {
  const table = screen.getByRole('table');
  const body = table.querySelector('tbody');
  expect(body).not.toBeNull();
  return within(body as HTMLTableSectionElement).getAllByRole('row');
}

afterEach(async () => {
  await i18n.changeLanguage('en');
});

describe('chat ResultTable pagination', () => {
  it.each([
    ['en', 'No results found for your query'],
    ['ar', 'لم يُعثر على نتائج لاستعلامك'],
  ])('renders zero rows as a successful localized table in %s', async (language, emptyCopy) => {
    await i18n.changeLanguage(language);
    render(<ResultTable result={resultWithRows(0)} />);

    const table = screen.getByRole('table');
    expect(within(table).getAllByRole('columnheader')).toHaveLength(2);
    expect(within(table).getByRole('cell', { name: emptyCopy })).toHaveAttribute('colspan', '2');
    expect(screen.queryByRole('button', { name: /previous|السابق/i })).not.toBeInTheDocument();
  });

  it('renders at most 50 body rows and traverses every returned row exactly once', () => {
    render(<ResultTable result={resultWithRows(101)} />);

    const visitedRows = new Set<string>();
    for (let page = 1; page <= 3; page += 1) {
      const rows = renderedBodyRows();
      expect(rows.length).toBeLessThanOrEqual(50);
      rows.forEach((row) => {
        const rowNumber = within(row).getAllByRole('cell')[0].textContent;
        expect(visitedRows.has(rowNumber ?? '')).toBe(false);
        visitedRows.add(rowNumber ?? '');
      });
      expect(screen.getByRole('table')).toHaveAccessibleName('Results');
      expect(screen.getByText('Masked')).toBeInTheDocument();
      if (page < 3) fireEvent.click(screen.getByRole('button', { name: 'Next page' }));
    }

    expect(visitedRows).toEqual(new Set(Array.from({ length: 101 }, (_, index) => String(index + 1))));
    expect(screen.getByRole('button', { name: 'Next page' })).toBeDisabled();
  });

  it('resets to the first page when the returned result changes', () => {
    const { rerender } = render(<ResultTable result={resultWithRows(101)} />);
    fireEvent.click(screen.getByRole('button', { name: 'Next page' }));
    fireEvent.click(screen.getByRole('button', { name: 'Next page' }));
    expect(screen.getByRole('status')).toHaveTextContent('Page 3 of 3');

    rerender(<ResultTable result={resultWithRows(51, 'replacement-attempt')} />);

    expect(screen.getByRole('status')).toHaveTextContent('Page 1 of 2');
    expect(screen.getByRole('cell', { name: '1' })).toBeInTheDocument();
  });

  it('localizes pagination names and status in Arabic RTL', async () => {
    await i18n.changeLanguage('ar');
    render(
      <div dir="rtl">
        <ResultTable result={resultWithRows(51)} />
      </div>
    );

    expect(screen.getByRole('button', { name: 'الصفحة التالية' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'الصفحة السابقة' })).toBeDisabled();
    expect(screen.getByRole('status')).toHaveTextContent('الصفحة 1 من 2');
  });
});
