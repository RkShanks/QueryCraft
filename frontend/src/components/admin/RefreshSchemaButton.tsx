import React from 'react';
import { useTranslation } from 'react-i18next';
import { useConnections } from '../../hooks/useConnections';
import { AlertCircle, CheckCircle2, Loader2, RefreshCw } from 'lucide-react';
import { getSafeConnectionErrorKey } from './connectionErrorMessages';

export interface RefreshSchemaButtonProps {
  connectionId: string;
  disabled?: boolean;
  schemaLastRefreshedAt?: string | null;
  onSuccess?: () => void;
  onError?: (error: unknown) => void;
}

export const RefreshSchemaButton: React.FC<RefreshSchemaButtonProps> = ({
  connectionId,
  disabled = false,
  schemaLastRefreshedAt = null,
  onSuccess,
  onError,
}) => {
  const { t, i18n } = useTranslation();
  const { refreshSchemaMutation } = useConnections();

  const handleRefresh = (e: React.MouseEvent) => {
    e.preventDefault();
    if (disabled || refreshSchemaMutation.isPending) return;

    refreshSchemaMutation.mutate(connectionId, {
      onSuccess: () => {
        if (onSuccess) {
          onSuccess();
        }
      },
      onError: (err) => {
        if (onError) {
          onError(err);
        }
      },
    });
  };

  const formatRefreshedAt = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleString(i18n.language || 'en', {
        dateStyle: 'medium',
        timeStyle: 'short',
      });
    } catch {
      return isoString;
    }
  };

  const isSuccessState = refreshSchemaMutation.isSuccess;
  const isErrorState = refreshSchemaMutation.isError;

  let errorMessage = '';
  if (isErrorState && refreshSchemaMutation.error) {
    errorMessage = t(getSafeConnectionErrorKey(refreshSchemaMutation.error));
  }

  // Display counts if available from the mutation success payload
  const tablesCount = refreshSchemaMutation.data?.tables_count;
  const columnsCount = refreshSchemaMutation.data?.columns_count;
  const hasCounts = typeof tablesCount === 'number' && typeof columnsCount === 'number';

  // Last refreshed timestamp from mutation data, fallback to prop
  const lastRefreshed = refreshSchemaMutation.data?.refreshed_at || schemaLastRefreshedAt;

  return (
    <div className="flex flex-col gap-2 text-start">
      <button
        type="button"
        onClick={handleRefresh}
        disabled={disabled || refreshSchemaMutation.isPending}
        className="inline-flex items-center justify-center px-4 py-2 border border-border bg-transparent text-text-primary hover:bg-bg-elevated rounded-md text-sm font-medium transition-all focus:outline-none focus:ring-2 focus:ring-neon-cyan/20 disabled:opacity-50 disabled:cursor-not-allowed select-none"
      >
        {refreshSchemaMutation.isPending ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin me-2" />
            {t('admin.connections.refreshingSchema')}
          </>
        ) : (
          <>
            <RefreshCw className="w-4 h-4 me-2" />
            {t('admin.connections.refreshSchema')}
          </>
        )}
      </button>

      {isSuccessState && (
        <div className="flex flex-col gap-1 text-sm text-green-500 bg-green-500/10 border border-green-500/20 px-3 py-2 rounded-md transition-all select-none">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>
              {hasCounts
                ? t('admin.connections.refreshSchemaSuccess', {
                    tables: tablesCount,
                    columns: columnsCount,
                  })
                : t('admin.connections.schema.success')}
            </span>
          </div>
        </div>
      )}

      {isErrorState && errorMessage && (
        <div className="flex items-start gap-2 text-sm text-red-500 bg-red-500/10 border border-red-500/20 px-3 py-2 rounded-md transition-all select-none">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}

      {lastRefreshed && (
        <div className="text-xs text-text-muted select-none px-1">
          {t('admin.connections.schema.refreshed', {
            time: formatRefreshedAt(lastRefreshed),
          })}
        </div>
      )}
    </div>
  );
};
