import { useEffect, useState } from 'react';
import type { ComponentType } from 'react';
import { useTranslation } from 'react-i18next';
import './SqlCodeBlock.css';

type HighlighterComponent = ComponentType<{ code: string }>;

// One shared lazy chunk load for the whole session; failures are remembered so
// a rejected import never retries or produces an unhandled rejection.
let highlighterModulePromise: Promise<HighlighterComponent> | null = null;

function loadHighlighter(): Promise<HighlighterComponent> {
  if (!highlighterModulePromise) {
    highlighterModulePromise = import('./ShikiHighlighter').then(
      (m) => m.ShikiHighlighter,
    );
    highlighterModulePromise.catch(() => {
      // Swallow at the shared-promise level; callers handle their own state.
    });
  }
  return highlighterModulePromise;
}

interface SqlCodeBlockProps {
  code: string;
}

export const SqlCodeBlock: React.FC<SqlCodeBlockProps> = ({ code }) => {
  const { t } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(false);
  const [Highlighter, setHighlighter] = useState<HighlighterComponent | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    if (!isExpanded || Highlighter || unavailable) return;
    let cancelled = false;
    loadHighlighter()
      .then((component) => {
        if (!cancelled) setHighlighter(() => component);
      })
      .catch(() => {
        // Local recovery only: keep readable SQL, announce unavailability.
        if (!cancelled) setUnavailable(true);
      });
    return () => {
      cancelled = true;
    };
  }, [isExpanded, Highlighter, unavailable]);

  return (
    <div className="sql-code-block" data-testid="sql-code-block">
      <button
        className="sql-code-block-toggle"
        onClick={() => setIsExpanded(!isExpanded)}
        data-testid="sql-toggle-btn"
        aria-expanded={isExpanded}
      >
        <span className={`sql-toggle-arrow ${isExpanded ? 'expanded' : ''}`}>▶</span>
        <span>{isExpanded ? t('query.sql.hide') : t('query.sql.show')}</span>
      </button>

      {isExpanded && Highlighter && <Highlighter code={code} />}
      {isExpanded && !Highlighter && !unavailable && (
        <div className="sql-code-block-skeleton" data-testid="sql-skeleton" />
      )}
      {isExpanded && unavailable && (
        <>
          <pre
            className="mt-1 bg-obsidian-950 p-4 rounded-xl border border-obsidian-800 overflow-x-auto text-obsidian-200 shadow-inner max-h-[300px]"
            data-testid="sql-plain-fallback"
            dir="ltr"
          >
            <code className="text-xs font-mono leading-relaxed font-light" dir="ltr">{code}</code>
          </pre>
          <p role="status" dir="auto" className="mt-2 text-xs text-text-muted">
            {t('query.sql.highlightUnavailable')}
          </p>
        </>
      )}
    </div>
  );
};
