import React from 'react';
import type { QueryResult } from '../../api/generated/types.gen';
import './ResultTable.css';

interface ResultTableProps {
  result: QueryResult;
}

export const ResultTable: React.FC<ResultTableProps> = ({ result }) => {
  const { columns, rows } = result;

  return (
    <div className="result-table-scroll" data-testid="result-table">
      <table className="result-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.name} className="result-table-header" scope="col">
                {col.name}
              </th>
            ))}
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
