import React from 'react';
import { useTranslation } from 'react-i18next';
import { Clock } from 'lucide-react';

export interface TimeoutBannerProps {
  timeout: boolean;
  onRetry: () => void;
}

export const TimeoutBanner: React.FC<TimeoutBannerProps> = ({
  timeout,
  onRetry,
}) => {
  const { t } = useTranslation();

  if (!timeout) return null;

  return (
    <div
      role="alert"
      className="bg-orange-50 border border-orange-200 rounded-lg p-4 flex flex-col gap-3"
    >
      <div className="flex items-start gap-3">
        <Clock className="w-5 h-5 text-orange-600 shrink-0 mt-0.5" aria-hidden="true" />
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-orange-800">
            {t('query.timeout.heading')}
          </h3>
          <p className="text-sm text-orange-700 mt-1">
            {t('query.timeout.body')}
          </p>
        </div>
      </div>
      <div className="flex justify-end">
        <button
          onClick={onRetry}
          className="inline-flex items-center px-4 py-2 text-sm font-medium text-orange-800 bg-orange-100 border border-orange-300 rounded-md hover:bg-orange-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500 transition-all"
        >
          {t('query.timeout.cta')}
        </button>
      </div>
    </div>
  );
};
