import React, { useState, useRef, useCallback, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Send } from '../icons';
import './PromptInput.css';

import { DatabaseSelector } from './DatabaseSelector';
import type { UserConnectionResponse } from '../../api/generated/types.gen';

interface PromptInputProps {
  onSubmit: (text: string) => void | Promise<void>;
  disabled?: boolean;
  connections: UserConnectionResponse[];
  selectedConnectionId: string | null;
  onSelectConnection: (id: string | null) => void;
  initialText?: string;
  questionLimit: QuestionLimitState;
}

export type QuestionLimitState =
  | { status: 'loading' }
  | { status: 'error'; onRetry: () => void }
  | { status: 'ready'; maxQuestionLength: number };

function countUnicodeCodePoints(text: string): number {
  return Array.from(text).length;
}

function isPythonStripWhitespace(codePoint: number): boolean {
  // Mirrors CPython 3.12 str.strip() so browser and API canonicalization agree.
  return (
    (codePoint >= 0x0009 && codePoint <= 0x000d) ||
    (codePoint >= 0x001c && codePoint <= 0x0020) ||
    codePoint === 0x0085 ||
    codePoint === 0x00a0 ||
    codePoint === 0x1680 ||
    (codePoint >= 0x2000 && codePoint <= 0x200a) ||
    codePoint === 0x2028 ||
    codePoint === 0x2029 ||
    codePoint === 0x202f ||
    codePoint === 0x205f ||
    codePoint === 0x3000
  );
}

function canonicalizeQuestion(text: string): string {
  const codePoints = Array.from(text);
  let start = 0;
  let end = codePoints.length;
  while (start < end && isPythonStripWhitespace(codePoints[start].codePointAt(0) ?? 0)) {
    start += 1;
  }
  while (end > start && isPythonStripWhitespace(codePoints[end - 1].codePointAt(0) ?? 0)) {
    end -= 1;
  }
  return codePoints.slice(start, end).join('');
}

export const PromptInput: React.FC<PromptInputProps> = ({
  onSubmit,
  disabled,
  connections,
  selectedConnectionId,
  onSelectConnection,
  initialText = '',
  questionLimit,
}) => {
  const { t } = useTranslation();
  const [text, setText] = useState(initialText);
  const [isLocallySubmitting, setIsLocallySubmitting] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const submissionInFlightRef = useRef(false);

  useEffect(() => {
    if (initialText) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setText(initialText);
    }
  }, [initialText]);

  const canonicalText = canonicalizeQuestion(text);
  const questionLength = countUnicodeCodePoints(canonicalText);
  const isLimitReady = questionLimit.status === 'ready';
  const isOverLimit = isLimitReady && questionLength > questionLimit.maxQuestionLength;
  const isPromptDisabled =
    connections.length === 0 ||
    !selectedConnectionId ||
    disabled ||
    !isLimitReady ||
    isLocallySubmitting;
  const canSubmitPrompt = Boolean(canonicalText) && !isPromptDisabled && !isOverLimit;

  const submitPrompt = useCallback(async () => {
    if (!canSubmitPrompt || submissionInFlightRef.current) return;
    submissionInFlightRef.current = true;
    setIsLocallySubmitting(true);
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    try {
      await onSubmit(canonicalText);
    } finally {
      submissionInFlightRef.current = false;
      setIsLocallySubmitting(false);
    }
  }, [canSubmitPrompt, canonicalText, onSubmit]);

  const submitOnEnter = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
        e.preventDefault();
        void submitPrompt();
      }
    },
    [submitPrompt]
  );

  const updatePromptText = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, []);

  const getPromptPlaceholder = () => {
    if (connections.length === 0) {
      return t('query.input.placeholderNoConnections');
    }
    if (!selectedConnectionId) {
      return t('query.input.placeholderNoSelection');
    }
    return t('query.input.placeholder');
  };

  const describedBy = [
    isLimitReady ? 'prompt-character-count' : 'prompt-limit-status',
    isOverLimit ? 'prompt-length-error' : null,
  ].filter(Boolean).join(' ');

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
          aria-label={t('query.input.label')}
          placeholder={getPromptPlaceholder()}
          value={text}
          onChange={updatePromptText}
          onKeyDown={submitOnEnter}
          disabled={isPromptDisabled}
          aria-describedby={describedBy}
          aria-invalid={isOverLimit}
          rows={1}
        />
        <button
          type="button"
          className="prompt-input-send"
          onClick={() => void submitPrompt()}
          disabled={!canSubmitPrompt}
          aria-label={t('common.send')}
          data-testid="prompt-send"
        >
          <Send className="w-5 h-5" />
        </button>
      </div>

      {questionLimit.status === 'ready' && (
        <div className="prompt-input-meta">
          <div
            id="prompt-character-count"
            className={`prompt-input-count${isOverLimit ? ' is-over-limit' : ''}`}
            data-testid="prompt-character-count"
            aria-live="polite"
            aria-atomic="true"
          >
            {t('query.input.charCount', {
              current: questionLength,
              max: questionLimit.maxQuestionLength,
            })}
          </div>
        </div>
      )}

      {isOverLimit && questionLimit.status === 'ready' && (
        <div id="prompt-length-error" className="prompt-input-error" role="alert">
          {t('query.error.validation.questionTooLong', {
            max: questionLimit.maxQuestionLength,
          })}
        </div>
      )}

      {questionLimit.status === 'loading' && (
        <div id="prompt-limit-status" className="prompt-input-limit-status" role="status">
          {t('query.input.limitLoading')}
        </div>
      )}

      {questionLimit.status === 'error' && (
        <div id="prompt-limit-status" className="prompt-input-limit-status" role="alert">
          <span>{t('query.input.limitLoadError')}</span>
          <button
            type="button"
            className="prompt-input-retry"
            onClick={questionLimit.onRetry}
          >
            {t('common.retry')}
          </button>
        </div>
      )}

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
