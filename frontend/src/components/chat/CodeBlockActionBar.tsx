import React, { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Copy, RefreshCw, ThumbsDown } from '../icons';
import './CodeBlockActionBar.css';

interface CodeBlockActionBarProps {
  sql: string;
  attemptId: string;
  onRegenerate: (attemptId: string) => void;
  onFeedback: (attemptId: string, feedback: number) => void;
}

export const CodeBlockActionBar: React.FC<CodeBlockActionBarProps> = ({
  sql,
  attemptId,
  onRegenerate,
  onFeedback,
}) => {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard write failed silently
    }
  }, [sql]);

  const handleRegenerate = useCallback(() => {
    onFeedback(attemptId, -1);
    onRegenerate(attemptId);
  }, [attemptId, onFeedback, onRegenerate]);

  const handleThumbsDown = useCallback(() => {
    onFeedback(attemptId, -1);
  }, [attemptId, onFeedback]);

  return (
    <div className="code-block-action-bar" data-testid="code-block-action-bar">
      <button
        className="action-btn"
        onClick={handleCopy}
        data-testid="action-copy"
        title={t('common.copy')}
      >
        {copied ? <span className="copy-confirmed">{t('common.copy')} ✓</span> : <Copy className="action-icon" />}
      </button>
      <button
        className="action-btn"
        onClick={handleRegenerate}
        data-testid="action-regenerate"
        title={t('common.regenerate')}
      >
        <RefreshCw className="action-icon" />
      </button>
      <button
        className="action-btn"
        onClick={handleThumbsDown}
        data-testid="action-thumbs-down"
        title={t('feedback.thumbsDown')}
      >
        <ThumbsDown className="action-icon" />
      </button>
    </div>
  );
};
