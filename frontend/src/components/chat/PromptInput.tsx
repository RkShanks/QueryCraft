import React, { useState, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Send } from '../icons';
import './PromptInput.css';

interface PromptInputProps {
  onSubmit: (text: string) => void;
  disabled?: boolean;
}

export const PromptInput: React.FC<PromptInputProps> = ({ onSubmit, disabled }) => {
  const { t } = useTranslation();
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = useCallback(() => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [text, disabled, onSubmit]);

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

  return (
    <div className="prompt-input-container" data-testid="prompt-input">
      <div className="prompt-input-wrapper">
        <textarea
          ref={textareaRef}
          className="prompt-input-textarea"
          placeholder={t('query.input.placeholder')}
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
        />
        <button
          type="button"
          className="prompt-input-send"
          onClick={handleSubmit}
          disabled={disabled || !text.trim()}
          aria-label={t('common.send')}
          data-testid="prompt-send"
        >
          <Send className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
};
