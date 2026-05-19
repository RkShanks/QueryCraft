import React from 'react';
import { useTranslation } from 'react-i18next';
import { useConnections } from '../../hooks/useConnections';
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';

export interface ConnectionTestButtonProps {
  connectionId: string;
  disabled?: boolean;
  onSuccess?: () => void;
  onError?: (error: unknown) => void;
}

const mapCategoryToKey = (category?: string | null): string => {
  if (!category) return 'error.unknown.message';
  if (category.startsWith('error.')) return category;
  if (category === 'auth_failed' || category === 'connection_auth_failed') return 'error.connection_auth_failed';
  if (category === 'network_unreachable' || category === 'connection_network_unreachable') return 'error.connection_network_unreachable';
  if (category === 'timeout' || category === 'connection_timeout') return 'error.connection_timeout';
  if (category === 'credential_config') return 'error.credential_config';
  return `error.${category}`;
};

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

  const isUnhealthyResult = testMutation.isSuccess && testMutation.data?.status === 'unhealthy';
  const isHealthyResult = testMutation.isSuccess && testMutation.data?.status === 'healthy';
  const isErrorState = testMutation.isError || isUnhealthyResult;

  let errorMessage = '';
  if (isUnhealthyResult && testMutation.data) {
    const data = testMutation.data;
    const key = data.message_key || mapCategoryToKey(data.error_category);
    errorMessage = t(key, { defaultValue: t('error.unknown.message') });
  } else if (testMutation.isError && testMutation.error) {
    const errorObj = testMutation.error as unknown as Record<string, unknown> | null;
    if (errorObj && typeof errorObj === 'object' && 'message_key' in errorObj && typeof errorObj.message_key === 'string') {
      errorMessage = t(errorObj.message_key, { defaultValue: t('error.unknown.message') });
    } else if (errorObj && typeof errorObj === 'object' && 'error' in errorObj && typeof errorObj.error === 'string') {
      errorMessage = t(mapCategoryToKey(errorObj.error), { defaultValue: t('error.unknown.message') });
    } else {
      errorMessage = t('error.unknown.message');
    }
  }

  return (
    <div className="flex flex-col gap-2 text-start">
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
        <div className="flex items-center gap-2 text-sm text-green-500 bg-green-500/10 border border-green-500/20 px-3 py-2 rounded-md transition-all select-none">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>
            {t('admin.connections.testSuccess', {
              latency: testMutation.data.latency_ms ?? 0,
            })}
          </span>
        </div>
      )}

      {isErrorState && errorMessage && (
        <div className="flex items-start gap-2 text-sm text-red-500 bg-red-500/10 border border-red-500/20 px-3 py-2 rounded-md transition-all select-none">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
};
