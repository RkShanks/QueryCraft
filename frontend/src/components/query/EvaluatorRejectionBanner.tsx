import React from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle } from 'lucide-react';

export interface EvaluatorRejectionBannerProps {
  evaluatorRejection: {
    failedRule: string;
    reason: string;
    violations?: string[];
  };
}

export const EvaluatorRejectionBanner: React.FC<EvaluatorRejectionBannerProps> = ({
  evaluatorRejection,
}) => {
  const { t } = useTranslation();
  const { failedRule, reason, violations } = evaluatorRejection;

  const ruleKey = `query.evaluatorRejection.rule.${failedRule}`;

  return (
    <div
      role="alert"
      className="bg-red-50 border border-red-200 rounded-lg p-4 flex flex-col gap-3"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" aria-hidden="true" />
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-red-800">
            {t('query.evaluatorRejection.heading')}
          </h3>
          <p className="text-sm text-red-700 mt-1">
            {t('query.evaluatorRejection.body', { reason })}
          </p>
          <p className="text-sm text-red-700 mt-1">
            {t(ruleKey)}
          </p>
        </div>
      </div>
      {violations && violations.length > 0 && (
        <ul className="list-disc list-inside text-sm text-red-700 ms-8">
          {violations.map((violation, index) => (
            <li key={index}>{violation}</li>
          ))}
        </ul>
      )}
    </div>
  );
};
