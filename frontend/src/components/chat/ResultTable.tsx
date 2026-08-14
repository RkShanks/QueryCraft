import React from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { ColumnMeta, QueryResult } from '../../api/generated/types.gen';
import './ResultTable.css';

interface ResultTableProps {
  result: QueryResult;
}

const PAGE_SIZE = 50;

interface PageState {
  attemptId: string;
  rows: QueryResult['rows'];
  pageIndex: number;
}

export const ResultTable: React.FC<ResultTableProps> = ({ result }) => {
  const { t } = useTranslation();
  const { columns, rows } = result;
  const [pageState, setPageState] = React.useState<PageState>(() => ({
    attemptId: result.attempt_id,
    rows,
    pageIndex: 0,
  }));
  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const isCurrentResult =
    pageState.attemptId === result.attempt_id && pageState.rows === rows;
  const pageIndex = isCurrentResult
    ? Math.min(pageState.pageIndex, pageCount - 1)
    : 0;
  const pageStart = pageIndex * PAGE_SIZE;
  const visibleRows = rows.slice(pageStart, pageStart + PAGE_SIZE);
  const hasPagination = rows.length > PAGE_SIZE;

  const selectPage = (nextPageIndex: number) => {
    setPageState({
      attemptId: result.attempt_id,
      rows,
      pageIndex: nextPageIndex,
    });
  };

  return (
    <div className="result-table-container" data-testid="result-table">
      <div className="result-table-scroll">
        <table className="result-table" aria-label={t('query.result.tableHeading')}>
          <thead>
            <tr>
              {columns.map((col) => {
                const isMasked = (col as ColumnMeta & { masked?: boolean }).masked === true;
                return (
                  <th key={col.name} className="result-table-header" scope="col">
                    <div className="flex items-center gap-2">
                      <span dir="ltr">{col.name}</span>
                      {isMasked && (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200/50 dark:bg-amber-900/20 dark:text-amber-400 dark:border-amber-800/30 whitespace-nowrap normal-case">
                          {t('query.result.columnMasked')}
                        </span>
                      )}
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr className="result-table-row">
                <td className="result-table-cell result-table-empty" colSpan={Math.max(1, columns.length)}>
                  {t('query.result.empty')}
                </td>
              </tr>
            ) : (
              visibleRows.map((row, rowIndex) => (
                <tr key={pageStart + rowIndex} className="result-table-row">
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="result-table-cell">
                      <span dir="auto">{String(cell ?? '')}</span>
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {hasPagination && (
        <nav className="result-table-pagination" aria-label={t('query.result.pagination.label')}>
          <p className="result-table-pagination-status" role="status" aria-live="polite">
            {t('query.result.pagination.status', {
              page: pageIndex + 1,
              pageCount,
              start: pageStart + 1,
              end: Math.min(pageStart + PAGE_SIZE, rows.length),
              total: rows.length,
            })}
          </p>
          <div className="result-table-pagination-actions">
            <button
              type="button"
              className="result-table-pagination-button"
              aria-label={t('query.result.pagination.previous')}
              disabled={pageIndex === 0}
              onClick={() => selectPage(pageIndex - 1)}
            >
              <ChevronLeft className="result-table-pagination-icon" aria-hidden="true" />
            </button>
            <button
              type="button"
              className="result-table-pagination-button"
              aria-label={t('query.result.pagination.next')}
              disabled={pageIndex === pageCount - 1}
              onClick={() => selectPage(pageIndex + 1)}
            >
              <ChevronRight className="result-table-pagination-icon" aria-hidden="true" />
            </button>
          </div>
        </nav>
      )}
    </div>
  );
};
