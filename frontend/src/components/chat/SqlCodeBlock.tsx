import React, { lazy, Suspense } from 'react';
import './SqlCodeBlock.css';

const ShikiHighlighter = lazy(() =>
  import('./ShikiHighlighter').then((m) => ({ default: m.ShikiHighlighter }))
);

interface SqlCodeBlockProps {
  code: string;
}

export const SqlCodeBlock: React.FC<SqlCodeBlockProps> = ({ code }) => {
  return (
    <div className="sql-code-block" data-testid="sql-code-block">
      <Suspense fallback={<div className="sql-code-block-skeleton" data-testid="sql-skeleton" />}>
        <ShikiHighlighter code={code} />
      </Suspense>
    </div>
  );
};
