import React from 'react';
import { useTranslation } from 'react-i18next';
import { Info } from 'lucide-react';

export interface RefinePromptBannerProps {
  refinePrompt: {
    reason: 'max_retries' | 'byte_equal_duplicate' | 'evaluator_blocked';
  };
  onRefine: () => void;
}

const reasonToKey: Record<RefinePromptBannerProps['refinePrompt']['reason'], string> = {
  max_retries: 'query.refine.body.maxRetries',
  byte_equal_duplicate: 'query.refine.body.byteEqual',
  evaluator_blocked: 'query.refine.body.evaluatorBlocked',
};

export const RefinePromptBanner: React.FC<RefinePromptBannerProps> = ({
  refinePrompt,
  onRefine,
}) => {
  const { t } = useTranslation();
  const bodyKey = reasonToKey[refinePrompt.reason];

  return (
    <div
      role="alert"
      className="bg-amber-50 border border-amber-200 rounded-lg p-4 flex flex-col gap-3"
    >
      <div className="flex items-start gap-3">
        <Info className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" aria-hidden="true" />
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-amber-800">
            {t('query.refine.heading')}
          </h3>
          <p className="text-sm text-amber-700 mt-1">
            {t(bodyKey)}
          </p>
        </div>
      </div>
      <div className="flex justify-end">
        <button
          onClick={onRefine}
          className="inline-flex items-center px-4 py-2 text-sm font-medium text-amber-800 bg-amber-100 border border-amber-300 rounded-md hover:bg-amber-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-amber-500 transition-all"
        >
          {t('query.refine.cta')}
        </button>
      </div>
    </div>
  );
};
