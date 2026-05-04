import React from 'react';

export interface SqlDisplayProps {
  sql: string;
}

export const SqlDisplay: React.FC<SqlDisplayProps> = ({ sql }) => {
  return (
    <div className="sql-display bg-gray-900 text-gray-100 p-4 rounded-lg font-mono text-sm overflow-x-auto border border-gray-700 shadow-inner">
      <div className="flex justify-between items-center mb-2 text-gray-400 text-xs uppercase tracking-wider">
        <span>Generated SQL</span>
      </div>
      <pre className="whitespace-pre-wrap break-all">{sql}</pre>
    </div>
  );
};
