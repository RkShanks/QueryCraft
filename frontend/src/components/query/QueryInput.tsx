import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

export interface QueryInputProps {
  onSubmit: (question: string) => void;
  isSubmitting: boolean;
  maxLength?: number;
  value?: string;
  onChange?: (value: string) => void;
}

export const QueryInput: React.FC<QueryInputProps> = ({ onSubmit, isSubmitting, maxLength = 2000, value: controlledValue, onChange }) => {
  const { t } = useTranslation();
  const [internalQuestion, setInternalQuestion] = useState('');
  const [droppedChars, setDroppedChars] = useState(0);
  const question = controlledValue !== undefined ? controlledValue : internalQuestion;

  const setQuestion = (val: string, dropped: number = 0) => {
    if (controlledValue === undefined) {
      setInternalQuestion(val);
    }
    setDroppedChars(dropped);
    onChange?.(val);
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const raw = e.target.value;
    const truncated = raw.slice(0, maxLength);
    const dropped = raw.length - truncated.length;
    setQuestion(truncated, dropped);
  };

  const handleSubmit = () => {
    if (question.trim() && !isSubmitting && question.length <= maxLength) {
      onSubmit(question.trim());
      setQuestion('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const isOverLimit = question.length > maxLength;

  return (
    <div className="query-input flex flex-col gap-2">
      <textarea
        value={question}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        disabled={isSubmitting}
        placeholder={t('query.input.placeholder', { defaultValue: 'Ask a question about your data...' })}
        className="border p-2 min-h-[100px] resize-y w-full"
      />
        {droppedChars > 0 && (
        <div
          data-testid="truncation-warning"
          className="bg-amber-50 border border-amber-200 rounded p-2 text-sm text-amber-800"
        >
          {t('query.input.truncation.warning', {
            current: question.length,
            max: maxLength,
            dropped: droppedChars,
            defaultValue: '{{current}} / {{max}} — input truncated, {{dropped}} characters dropped',
          })}
        </div>
      )}
      <div className="flex justify-between items-center">
        <span className="text-sm text-gray-500" data-testid="char-counter">
          {t('query.input.charCount', { current: question.length, max: maxLength, defaultValue: '{{current}} / {{max}}' })}
        </span>
        <button
          onClick={handleSubmit}
          disabled={!question.trim() || isOverLimit || isSubmitting}
          className="bg-blue-500 text-white p-2 rounded disabled:opacity-50"
        >
          {isSubmitting 
            ? t('query.input.submitting', { defaultValue: 'Submitting...' }) 
            : t('query.input.submit', { defaultValue: 'Ask' })}
        </button>
      </div>
    </div>
  );
};
