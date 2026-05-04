import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

export interface QueryInputProps {
  onSubmit: (question: string) => void;
  isSubmitting: boolean;
}

export const QueryInput: React.FC<QueryInputProps> = ({ onSubmit, isSubmitting }) => {
  const { t } = useTranslation();
  const [question, setQuestion] = useState('');
  const maxLength = 2000;

  const handleSubmit = () => {
    if (question.trim() && !isSubmitting) {
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

  return (
    <div className="query-input flex flex-col gap-2">
      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value.slice(0, maxLength))}
        onKeyDown={handleKeyDown}
        disabled={isSubmitting}
        placeholder={t('query.input.placeholder', { defaultValue: 'Ask a question about your data...' })}
        className="border p-2 min-h-[100px] resize-y w-full"
      />
      <div className="flex justify-between items-center">
        <span className="text-sm text-gray-500">
          {question.length} / {maxLength}
        </span>
        <button
          onClick={handleSubmit}
          disabled={!question.trim() || isSubmitting}
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
