import React, { lazy, Suspense, useState } from 'react';
import './SqlCodeBlock.css';

const ShikiHighlighter = lazy(() =>
  import('./ShikiHighlighter').then((m) => ({ default: m.ShikiHighlighter }))
);

interface SqlCodeBlockProps {
  code: string;
}

export const SqlCodeBlock: React.FC<SqlCodeBlockProps> = ({ code }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="sql-code-block" data-testid="sql-code-block">
      <button 
        className="sql-code-block-toggle" 
        onClick={() => setIsExpanded(!isExpanded)}
        data-testid="sql-toggle-btn"
        aria-expanded={isExpanded}
      >
        <span className={`sql-toggle-arrow ${isExpanded ? 'expanded' : ''}`}>▶</span>
        <span>{isExpanded ? 'Hide SQL' : 'Show SQL'}</span>
      </button>
      
      {isExpanded && (
        <Suspense fallback={<div className="sql-code-block-skeleton" data-testid="sql-skeleton" />}>
          <ShikiHighlighter code={code} />
        </Suspense>
      )}
    </div>
  );
};
