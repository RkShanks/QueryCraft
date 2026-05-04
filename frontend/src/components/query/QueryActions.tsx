import React from 'react';
import { useTranslation } from 'react-i18next';

export interface QueryActionsProps {
  attemptId: string;
  onAccept: (id: string) => void;
  isAccepting?: boolean;
}

export const QueryActions: React.FC<QueryActionsProps> = ({
  attemptId,
  onAccept,
  isAccepting
}) => {
  const { t } = useTranslation();

  return (
    <div className="query-actions flex gap-3 justify-end items-center mt-4">
      <button
        onClick={() => onAccept(attemptId)}
        disabled={isAccepting}
        className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-md shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
      >
        {isAccepting ? (
          <>
            <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {t('query.action.accepting', { defaultValue: 'Accepting...' })}
          </>
        ) : (
          t('query.action.accept', { defaultValue: 'Accept' })
        )}
      </button>
    </div>
  );
};
