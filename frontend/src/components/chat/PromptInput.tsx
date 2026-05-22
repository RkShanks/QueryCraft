import React, { useState, useRef, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Send } from '../icons';
import './PromptInput.css';

import { DatabaseSelector } from './DatabaseSelector';
import type { UserConnectionResponse } from '../../api/generated/types.gen';

interface PromptInputProps {
  onSubmit: (text: string) => void;
  disabled?: boolean;
  connections: UserConnectionResponse[];
  selectedConnectionId: string | null;
  onSelectConnection: (id: string | null) => void;
  initialText?: string;
}

export const PromptInput: React.FC<PromptInputProps> = ({
  onSubmit,
  disabled,
  connections,
  selectedConnectionId,
  onSelectConnection,
  initialText = '',
}) => {
  const { t } = useTranslation();
  const [text, setText] = useState(initialText);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (initialText) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setText(initialText);
    }
  }, [initialText]);

  const isPromptDisabled = connections.length === 0 || !selectedConnectionId || disabled;

  const handleSubmit = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || isPromptDisabled) return;
    onSubmit(trimmed);
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [text, isPromptDisabled, onSubmit]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  const handleChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, []);

  const getPlaceholder = () => {
    if (connections.length === 0) {
      return t('query.input.placeholderNoConnections');
    }
    if (!selectedConnectionId) {
      return t('query.input.placeholderNoSelection');
    }
    return t('query.input.placeholder');
  };

  return (
    <div className="prompt-input-container" data-testid="prompt-input">
      <div className="prompt-input-header">
        <DatabaseSelector
          connections={connections}
          selectedId={selectedConnectionId}
          onSelect={onSelectConnection}
        />
      </div>

      <div className="prompt-input-wrapper">
        <textarea
          ref={textareaRef}
          className="prompt-input-textarea"
          placeholder={getPlaceholder()}
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={isPromptDisabled}
          rows={1}
        />
        <button
          type="button"
          className="prompt-input-send"
          onClick={handleSubmit}
          disabled={isPromptDisabled || !text.trim()}
          aria-label={t('common.send')}
          data-testid="prompt-send"
        >
          <Send className="w-5 h-5" />
        </button>
      </div>

      {!selectedConnectionId && (
        <div
          className="prompt-input-warning"
          data-testid="prompt-input-warning"
          role="alert"
          aria-live="polite"
        >
          {connections.length === 0
            ? t('query.input.warningNoConnections')
            : t('query.input.warningNoSelection')}
        </div>
      )}
    </div>
  );
};
