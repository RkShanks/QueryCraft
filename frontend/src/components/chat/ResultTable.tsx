import React from 'react';
import { useTranslation } from 'react-i18next';
import type { ColumnMeta, QueryResult } from '../../api/generated/types.gen';
import './ResultTable.css';

interface ResultTableProps {
  result: QueryResult;
}

export const ResultTable: React.FC<ResultTableProps> = ({ result }) => {
  const { t } = useTranslation();
  const { columns, rows } = result;

  return (
    <div className="result-table-scroll" data-testid="result-table">
      <table className="result-table">
        <thead>
          <tr>
            {columns.map((col) => {
              const isMasked = (col as ColumnMeta & { masked?: boolean }).masked === true;
              return (
                <th key={col.name} className="result-table-header" scope="col">
                  <div className="flex items-center gap-2">
                    <span>{col.name}</span>
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
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="result-table-row">
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className="result-table-cell">
                  {String(cell ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
