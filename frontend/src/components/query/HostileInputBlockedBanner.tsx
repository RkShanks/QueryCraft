import React from 'react';
import { useTranslation } from 'react-i18next';
import { ShieldAlert } from 'lucide-react';

export const HostileInputBlockedBanner: React.FC = () => {
  const { t } = useTranslation();

  return (
    <div
      role="alert"
      className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 flex flex-col gap-3 shadow-lg backdrop-blur-sm animate-in fade-in slide-in-from-top-2 duration-300"
      data-testid="hostile-input-blocked-banner"
    >
      <div className="flex items-start gap-3 justify-start">
        <ShieldAlert className="w-5 h-5 text-red-400 shrink-0 mt-0.5" aria-hidden="true" />
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-red-400">
            {t('error.hostile_input_blocked')}
          </h3>
        </div>
      </div>
    </div>
  );
};
