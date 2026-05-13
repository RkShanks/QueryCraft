import React, { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Copy, RefreshCw } from '../icons';
import './CodeBlockActionBar.css';

interface CodeBlockActionBarProps {
  sql: string;
  attemptId: string;
  onRegenerate: (attemptId: string) => void;
}

export const CodeBlockActionBar: React.FC<CodeBlockActionBarProps> = ({
  sql,
  attemptId,
  onRegenerate,
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
    onRegenerate(attemptId);
  }, [attemptId, onRegenerate]);

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
    </div>
  );
};
