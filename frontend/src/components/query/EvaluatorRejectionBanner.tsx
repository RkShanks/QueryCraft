import React from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle } from 'lucide-react';

export interface Violation {
  type: string;
  detail?: string;
}

export interface EvaluatorRejectionBannerProps {
  violations: Violation[];
}

const typeToKey = (type: string): string => {
  switch (type) {
    case 'read_only':
      return 'query.evaluator.read_only';
    case 'schema_validation':
      return 'query.evaluator.schema_validation';
    case 'single_statement':
      return 'query.evaluator.single_statement';
    case 'unsafe_pattern':
      return 'query.evaluator.unsafe_pattern';
    case 'syntax':
      return 'query.evaluator.syntax';
    default:
      return 'query.evaluator.unknown';
  }
};

export const EvaluatorRejectionBanner: React.FC<EvaluatorRejectionBannerProps> = ({
  violations,
}) => {
  const { t } = useTranslation();

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
          {violations.length > 0 && (
            <ul className="list-disc list-inside text-sm text-red-700 mt-2 ms-0">
              {violations.map((violation, index) => {
                const key = typeToKey(violation.type);
                const params =
                  violation.type === 'schema_validation'
                    ? { identifier: violation.detail }
                    : violation.type === 'unsafe_pattern'
                    ? { pattern: violation.detail }
                    : violation.type === 'syntax'
                    ? { details: violation.detail }
                    : undefined;
                return <li key={index} data-testid={`violation-${index}`}>{t(key, params)}</li>;
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};
