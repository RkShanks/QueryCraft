import React from 'react';
import { useTranslation } from 'react-i18next';
import { useConnections } from '../../hooks/useConnections';
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { getSafeConnectionErrorKey } from './connectionErrorMessages';

export interface ConnectionTestButtonProps {
  connectionId: string;
  disabled?: boolean;
  onSuccess?: () => void;
  onError?: (error: unknown) => void;
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
          if (onError) {
            onError(data);
          }
        } else {
          if (onSuccess) {
            onSuccess();
          }
        }
      },
      onError: (err) => {
        if (onError) {
          onError(err);
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
  }, [testMutation.isSuccess, testMutation.isError, testMutation.reset]);

  const isUnhealthyResult = testMutation.isSuccess && testMutation.data?.status === 'unhealthy';
  const isHealthyResult = testMutation.isSuccess && testMutation.data?.status === 'healthy';
  const isErrorState = testMutation.isError || isUnhealthyResult;

  let errorMessage = '';
  if (isUnhealthyResult && testMutation.data) {
    errorMessage = t(getSafeConnectionErrorKey(testMutation.data));
  } else if (testMutation.isError && testMutation.error) {
    errorMessage = t(getSafeConnectionErrorKey(testMutation.error));
  }

  return (
    <div className="relative text-start">
      <button
        type="button"
        onClick={handleTest}
        disabled={disabled || testMutation.isPending}
        className="inline-flex items-center justify-center px-4 py-2 border border-border bg-transparent text-text-primary hover:bg-bg-elevated rounded-md text-sm font-medium transition-all focus:outline-none focus:ring-2 focus:ring-neon-cyan/20 disabled:opacity-50 disabled:cursor-not-allowed select-none"
      >
        {testMutation.isPending ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin me-2" />
            {t('admin.connections.testing')}
          </>
        ) : (
          t('admin.connections.test')
        )}
      </button>

      {isHealthyResult && testMutation.data && (
        <div className="absolute top-full right-0 mt-1 z-50 flex items-center gap-2 text-sm text-green-500 bg-bg-card border border-green-500/20 px-3 py-2 rounded-md shadow-lg transition-all select-none min-w-[240px]">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>
            {t('admin.connections.testSuccess', {
              latency: testMutation.data.latency_ms ?? 0,
            })}
          </span>
        </div>
      )}

      {isErrorState && errorMessage && (
        <div className="absolute top-full right-0 mt-1 z-50 flex items-start gap-2 text-sm text-red-500 bg-bg-card border border-red-500/20 px-3 py-2 rounded-md shadow-lg transition-all select-none min-w-[240px]">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
};
