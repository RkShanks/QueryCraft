import React from 'react';
import { useTranslation } from 'react-i18next';
import type { QueryResult } from '../../api/generated/types.gen';
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table';
import type { ColumnDef } from '@tanstack/react-table';
import { SqlDisplay } from './SqlDisplay';
import { QueryActions } from './QueryActions';

export interface ResultTableProps {
  result: QueryResult;
  onAccept: (id: string) => void;
  isAccepting?: boolean;
}

export const ResultTable: React.FC<ResultTableProps> = ({ 
  result, onAccept, isAccepting 
}) => {
  const { t } = useTranslation();
  
  const columns = React.useMemo<ColumnDef<unknown[]>[]>(() => result.columns.map((col, index) => ({
    header: col.name,
    accessorFn: (row) => row[index],
    id: col.name,
    cell: (info) => <span className="text-gray-700">{String(info.getValue())}</span>,
  })), [result.columns]);
  
  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Table v8 + React Compiler false-positive; remove when TanStack Table v9 ships
  const table = useReactTable({
    data: result.rows as unknown[][],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="result-container flex flex-col gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <SqlDisplay sql={result.generated_sql} />
      
      <div className="table-wrapper bg-white shadow-sm border border-gray-200 rounded-xl overflow-hidden">
        {result.rows.length === 0 ? (
          <div className="no-results p-8 text-center bg-gray-50 text-gray-500 italic">
            {t('query.result.empty', { defaultValue: 'No results found for your query' })}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                {table.getHeaderGroups().map(headerGroup => (
                  <tr key={headerGroup.id}>
                    {headerGroup.headers.map(header => (
                      <th key={header.id} className="px-6 py-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {table.getRowModel().rows.map(row => (
                  <tr key={row.id} className="hover:bg-gray-50 transition-colors">
                    {row.getVisibleCells().map(cell => (
                      <td key={cell.id} className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      
      <QueryActions 
        attemptId={result.attempt_id}
        onAccept={onAccept}
        isAccepting={isAccepting}
      />
    </div>
  );
};
