import React from 'react';
import { useTranslation } from 'react-i18next';
import { useConnections } from '../../hooks/useConnections';
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { getSafeConnectionErrorKey } from './connectionErrorMessages';

export interface ConnectionTestButtonProps {
  connectionId: string;
  disabled?: boolean;
  onSuccess?: (message: string) => void;
  onError?: (message: string) => void;
}

export const ConnectionTestButton: React.FC<ConnectionTestButtonProps> = ({
  connectionId,
  disabled = false,
  onSuccess,
  onError,
}) => {
  const { t } = useTranslation();
  const { testMutation } = useConnections();

  const handleTest = (e: React.MouseEvent) => {
    e.preventDefault();
    if (disabled || testMutation.isPending) return;

    testMutation.mutate(connectionId, {
      onSuccess: (data) => {
        if (data.status === 'unhealthy') {
          const errMsg = t(getSafeConnectionErrorKey(data));
          if (onError) {
            onError(errMsg);
          }
        } else {
          const succMsg = t('admin.connections.testSuccess', {
            latency: data.latency_ms ?? 0,
          });
          if (onSuccess) {
            onSuccess(succMsg);
          }
        }
      },
      onError: (err) => {
        const errMsg = t(getSafeConnectionErrorKey(err));
        if (onError) {
          onError(errMsg);
        }
      },
    });
  };

  React.useEffect(() => {
    if (testMutation.isSuccess || testMutation.isError) {
      const timer = setTimeout(() => {
        testMutation.reset();
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [testMutation]);

  const isUnhealthyResult = testMutation.isSuccess && testMutation.data?.status === 'unhealthy';
  const isHealthyResult = testMutation.isSuccess && testMutation.data?.status === 'healthy';
  const isErrorState = testMutation.isError || isUnhealthyResult;

  let errorMessage = '';
  if (isUnhealthyResult && testMutation.data) {
    errorMessage = t(getSafeConnectionErrorKey(testMutation.data));
  } else if (testMutation.isError && testMutation.error) {
    errorMessage = t(getSafeConnectionErrorKey(testMutation.error));
  }

  // Choose styling class based on mutation status
  let buttonClasses = "inline-flex items-center justify-center px-4 py-2 border rounded-md text-sm font-medium transition-all select-none";
  if (testMutation.isPending) {
    buttonClasses += " border-border bg-transparent text-text-primary opacity-50 cursor-not-allowed";
  } else if (isHealthyResult) {
    buttonClasses += " border-green-500/30 bg-green-500/10 text-green-500 shadow-[0_0_12px_rgba(34,197,94,0.15)]";
  } else if (isErrorState) {
    buttonClasses += " border-red-500/30 bg-red-500/10 text-red-500 shadow-[0_0_12px_rgba(239,68,68,0.15)]";
  } else {
    buttonClasses += " border-border bg-transparent text-text-primary hover:bg-bg-elevated focus:outline-none focus:ring-2 focus:ring-neon-cyan/20 disabled:opacity-50 disabled:cursor-not-allowed";
  }

  return (
    <div aria-live="polite">
    <button
      type="button"
      onClick={handleTest}
      disabled={disabled || testMutation.isPending}
      className={buttonClasses}
    >
      {testMutation.isPending ? (
        <>
          <Loader2 className="w-4 h-4 animate-spin me-2" />
          {t('admin.connections.testing')}
        </>
      ) : isHealthyResult && testMutation.data ? (
        <>
          <CheckCircle2 className="w-4 h-4 shrink-0 me-2" />
          <span>
            {t('admin.connections.testSuccess', {
              latency: testMutation.data.latency_ms ?? 0,
            })}
          </span>
        </>
      ) : isErrorState && errorMessage ? (
        <>
          <AlertCircle className="w-4 h-4 shrink-0 me-2" />
          <span className="text-xs text-start">{errorMessage}</span>
        </>
      ) : (
        t('admin.connections.test')
      )}
    </button>
    </div>
  );
};
