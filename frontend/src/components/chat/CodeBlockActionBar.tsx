import React, { useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Copy, RefreshCw } from '../icons';
import { useCopyToClipboard } from '../../hooks/useCopyToClipboard';
import './CodeBlockActionBar.css';

interface CodeBlockActionBarProps {
  sql: string;
  attemptId?: string;
  onRegenerate?: (attemptId: string) => void;
  isRegenerating?: boolean;
}

export const CodeBlockActionBar: React.FC<CodeBlockActionBarProps> = ({
  sql,
  attemptId,
  onRegenerate,
  isRegenerating = false,
}) => {
  const { t } = useTranslation();
  const { status, copy } = useCopyToClipboard();

  const handleCopy = useCallback(() => {
    void copy(sql);
  }, [copy, sql]);

  const handleRegenerate = useCallback(() => {
    if (!attemptId || !onRegenerate) return;
    onRegenerate(attemptId);
  }, [attemptId, onRegenerate]);

  const canRegenerate = !!attemptId && !!onRegenerate;

  const copyStateLabel =
    status === 'copied'
      ? t('common.copied')
      : status === 'failed'
        ? t('common.copyFailed')
        : t('common.copy');

  return (
    <div className="code-block-action-bar" data-testid="code-block-action-bar">
      <button
        type="button"
        className={`action-btn ${status === 'failed' ? 'action-btn-failed' : ''}`}
        onClick={handleCopy}
        data-testid="action-copy"
        title={copyStateLabel}
        aria-label={copyStateLabel}
        data-copy-status={status}
      >
        {status === 'copied' ? (
          <span className="copy-confirmed">{t('common.copy')} ✓</span>
        ) : (
          <Copy className="action-icon" />
        )}
      </button>
      <span aria-live="polite" aria-atomic="true" className="sr-only" data-testid="copy-status">
        {status === 'copied'
          ? t('common.copied')
          : status === 'failed'
            ? t('common.copyFailed')
            : ''}
      </span>
      {canRegenerate && (
        <button
          type="button"
          className="action-btn"
          onClick={handleRegenerate}
          data-testid="action-regenerate"
          title={t('common.regenerate')}
          aria-label={t('common.regenerate')}
          disabled={isRegenerating}
        >
          <RefreshCw className="action-icon" />
        </button>
      )}
    </div>
  );
};
