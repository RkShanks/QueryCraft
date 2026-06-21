import React from 'react';
import { useTranslation } from 'react-i18next';
import { AlertCircle } from 'lucide-react';

export interface QuotaExceededBannerProps {
  resetAt?: string;
}

export const QuotaExceededBanner: React.FC<QuotaExceededBannerProps> = ({ resetAt }) => {
  const { t } = useTranslation();

  const formattedTime = React.useMemo(() => {
    if (!resetAt) return '';
    try {
      return new Date(resetAt).toLocaleString();
    } catch {
      return resetAt;
    }
  }, [resetAt]);

  return (
    <div
      role="alert"
      className="bg-red-50 border border-red-200 rounded-lg p-4 flex flex-col gap-3"
      data-testid="quota-exceeded-banner"
    >
      <div className="flex items-start gap-3 justify-start">
        <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" aria-hidden="true" />
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-red-800">
            {t('error.quota_exceeded')}
          </h3>
          {resetAt && formattedTime && (
            <p className="text-sm text-red-700 mt-1">
              {t('quota.reset_at', { time: formattedTime })}
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
