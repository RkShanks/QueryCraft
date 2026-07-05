import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { ResultTable } from '../chat/ResultTable';
import type { AcceptedQueryDetail, QueryResult } from '../../api/generated/types.gen';
import { Copy, Check, Sparkles, Database, Calendar, Terminal } from 'lucide-react';

export interface HistoryDetailProps {
  item: AcceptedQueryDetail | null;
  isLoading?: boolean;
  error?: Error | null;
}

export const HistoryDetail: React.FC<HistoryDetailProps> = ({ item, isLoading, error }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [copied, setCopied] = useState(false);

  const getDatabaseTypeLabel = (databaseType?: string | null) => {
    if (!databaseType) return null;
    const key = `query.result.databaseType.${databaseType}`;
    const translated = t(key);
    return translated === key ? databaseType : translated;
  };

  const handleCopy = async () => {
    if (!item?.generated_sql) return;
    try {
      await navigator.clipboard.writeText(item.generated_sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text: ', err);
    }
  };

  const handleLoadInWorkspace = () => {
    if (!item) return;
    const connectionParam = item.database_connection_id ? `&connectionId=${item.database_connection_id}` : '';
    const url = `/?question=${encodeURIComponent(item.question_text)}${connectionParam}`;
    navigate(url);
  };

  if (error) {
    return (
      <div className="history-detail-error p-6 text-red-400 bg-red-500/5 border border-red-500/10 rounded-2xl text-center select-none animate-fade-in">
        {t('history.error')}
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="history-detail-loading p-8 text-center text-text-muted select-none flex flex-col items-center justify-center min-h-[300px] gap-3 animate-fade-in">
        <div className="w-8 h-8 rounded-full border-2 border-neon-cyan/20 border-t-neon-cyan animate-spin" />
        <span>{t('history.loading')}</span>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="history-detail-empty p-8 text-center text-text-muted select-none flex flex-col items-center justify-center min-h-[300px] gap-4 animate-fade-in">
        <div className="w-16 h-16 rounded-full bg-obsidian-950/60 border border-obsidian-800 flex items-center justify-center">
          <Terminal className="w-8 h-8 opacity-30 text-neon-cyan" />
        </div>
        <p className="max-w-xs text-sm leading-relaxed">{t('history.detail.empty')}</p>
      </div>
    );
  }

  const historyResult: QueryResult | null =
    item.result_columns && item.result_rows
      ? ({
          kind: 'result',
          attempt_id: item.id,
          question: item.question_text,
          generated_sql: item.generated_sql,
          columns: item.result_columns,
          rows: item.result_rows,
          row_count: item.result_row_count ?? 0,
          attempt_number: 1,
          is_last_auto_retry: false,
          accepted_query_id: item.id,
        } as QueryResult)
      : null;

  return (
    <article
      className="history-detail space-y-6 animate-fade-in text-start select-none"
      data-testid="history-detail"
    >
      {/* Top Header Panel: Metadata & Load in Workspace */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-obsidian-800/80">
        {item.database_connection_name && item.database_type ? (
          <div className="history-detail-meta flex items-center gap-2" data-testid="history-detail-meta">
            <span className="font-semibold text-text-primary text-sm flex items-center gap-1.5">
              <Database className="w-4 h-4 text-neon-cyan" />
              {item.database_connection_name}
            </span>
            <span className="rounded-full bg-neon-cyan/5 border border-neon-cyan/15 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-neon-cyan">
              {getDatabaseTypeLabel(item.database_type)}
            </span>
          </div>
        ) : (
          <div className="h-6" /> // spacer to maintain layout
        )}

        <button
          onClick={handleLoadInWorkspace}
          className="flex items-center justify-center gap-2 px-4 py-2 text-xs font-semibold bg-neon-cyan text-gray-900 rounded-xl hover:bg-opacity-95 shadow-[0_0_12px_rgba(6,182,212,0.15)] hover:shadow-[0_0_18px_rgba(6,182,212,0.25)] transition-all cursor-pointer font-medium"
        >
          <Sparkles className="w-3.5 h-3.5" />
          {t('history.detail.loadInWorkspace') || 'Load in Chat'}
        </button>
      </div>

      {/* Natural Language Question Section */}
      <section className="space-y-1.5">
        <h3 className="text-xs font-bold text-text-muted uppercase tracking-wider">
          {t('history.detail.question')}
        </h3>
        <p className="text-text-primary text-base font-medium leading-relaxed">
          {item.question_text}
        </p>
      </section>

      {/* SQL Block Editor Section */}
      <section className="space-y-1.5">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold text-text-muted uppercase tracking-wider">
            {t('history.detail.sql')}
          </h3>
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1 text-[11px] font-semibold text-text-muted hover:text-neon-cyan transition-colors px-2 py-1 bg-obsidian-950 border border-obsidian-800 rounded-lg cursor-pointer"
          >
            {copied ? (
              <>
                <Check className="w-3 h-3 text-green-400" />
                <span className="text-green-400">{t('common.copied')}</span>
              </>
            ) : (
              <>
                <Copy className="w-3 h-3" />
                <span>{t('common.copy')}</span>
              </>
            )}
          </button>
        </div>
        <pre
          className="mt-1 bg-obsidian-950 p-4 rounded-xl border border-obsidian-800 overflow-x-auto text-obsidian-200 shadow-inner max-h-[300px]"
          dir="ltr"
        >
          <code className="text-xs font-mono leading-relaxed font-light" dir="ltr">{item.generated_sql}</code>
        </pre>
      </section>

      {/* Query Result Table Section */}
      {historyResult && (
        <section className="space-y-2">
          <h3 className="text-xs font-bold text-text-muted uppercase tracking-wider">
            {t('query.result.tableHeading')}
          </h3>
          <div className="border border-obsidian-800/80 rounded-xl overflow-hidden shadow-lg bg-obsidian-950/20">
            <ResultTable result={historyResult} />
          </div>
        </section>
      )}

      {/* Metadata Bottom Strip */}
      <section className="flex flex-wrap gap-x-6 gap-y-2 text-xs text-text-muted border-t border-obsidian-800/60 pt-4 select-none">
        <div className="flex items-center gap-1.5">
          <span className="font-semibold">{t('history.detail.llmProvider')}:</span>
          <span className="px-2 py-0.5 rounded bg-obsidian-950 border border-obsidian-800 text-[10px] uppercase font-mono tracking-wider text-text-secondary">
            {item.llm_provider ?? '—'}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <Calendar className="w-3.5 h-3.5 text-text-muted" />
          <span className="font-semibold">{t('history.detail.acceptedAt')}:</span>
          <span>{item.accepted_at ? new Date(item.accepted_at).toLocaleString() : '—'}</span>
        </div>
      </section>
    </article>
  );
};
