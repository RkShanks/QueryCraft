import React from 'react';
import { useTranslation } from 'react-i18next';

export interface QueryActionsProps {
  attemptId: string;
  onAccept: (id: string) => void;
  isAccepting?: boolean;
  onReject?: (id: string) => void;
  onRegenerate?: (id: string) => void;
  canRegenerate?: boolean;
}

export const QueryActions: React.FC<QueryActionsProps> = ({
  attemptId,
  onAccept,
  isAccepting,
  onReject,
  onRegenerate,
  canRegenerate,
}) => {
  const { t } = useTranslation();

  return (
    <div className="query-actions flex gap-3 justify-end items-center mt-4">
      {onReject && (
        <button
          onClick={() => onReject(attemptId)}
          disabled={isAccepting}
          className="inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          {t('query.actions.reject')}
        </button>
      )}
      {canRegenerate && onRegenerate && (
        <button
          onClick={() => onRegenerate(attemptId)}
          disabled={isAccepting}
          className="inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          {t('query.actions.regenerate')}
        </button>
      )}
      <button
        onClick={() => onAccept(attemptId)}
        disabled={isAccepting}
        className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-md shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
      >
        {isAccepting ? (
          <>
            <svg className="animate-spin -ms-1 me-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {t('query.actions.accepting')}
          </>
        ) : (
          t('query.actions.accept')
        )}
      </button>
    </div>
  );
};
