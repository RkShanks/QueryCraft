import React from 'react';
import { useTranslation } from 'react-i18next';
import { useConnections } from '../../hooks/useConnections';
import { AlertCircle, CheckCircle2, Loader2, RefreshCw } from 'lucide-react';
import { getSafeConnectionErrorKey } from './connectionErrorMessages';

export interface RefreshSchemaButtonProps {
  connectionId: string;
  disabled?: boolean;
  schemaLastRefreshedAt?: string | null;
  onSuccess?: (message: string) => void;
  onError?: (message: string) => void;
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
      onSuccess: (data) => {
        const tablesCount = data?.tables_count;
        const columnsCount = data?.columns_count;
        const hasCounts = typeof tablesCount === 'number' && typeof columnsCount === 'number';
        const succMsg = hasCounts
          ? t('admin.connections.refreshSchemaSuccess', {
              tables: tablesCount,
              columns: columnsCount,
            })
          : t('admin.connections.schema.success');
        if (onSuccess) {
          onSuccess(succMsg);
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
    if (refreshSchemaMutation.isSuccess || refreshSchemaMutation.isError) {
      const timer = setTimeout(() => {
        refreshSchemaMutation.reset();
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [refreshSchemaMutation]);

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

  // Choose styling class based on mutation status
  let buttonClasses = "inline-flex items-center justify-center px-4 py-2 border rounded-md text-sm font-medium transition-all select-none";
  if (refreshSchemaMutation.isPending) {
    buttonClasses += " border-border bg-transparent text-text-primary opacity-50 cursor-not-allowed";
  } else if (isSuccessState) {
    buttonClasses += " border-green-500/30 bg-green-500/10 text-green-500 shadow-[0_0_12px_rgba(34,197,94,0.15)]";
  } else if (isErrorState) {
    buttonClasses += " border-red-500/30 bg-red-500/10 text-red-500 shadow-[0_0_12px_rgba(239,68,68,0.15)]";
  } else {
    buttonClasses += " border-border bg-transparent text-text-primary hover:bg-bg-elevated focus:outline-none focus:ring-2 focus:ring-neon-cyan/20 disabled:opacity-50 disabled:cursor-not-allowed";
  }

  return (
    <div className="relative text-start">
      <button
        type="button"
        onClick={handleRefresh}
        disabled={disabled || refreshSchemaMutation.isPending}
        className={buttonClasses}
      >
        {refreshSchemaMutation.isPending ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin me-2" />
            {t('admin.connections.refreshingSchema')}
          </>
        ) : isSuccessState ? (
          <>
            <CheckCircle2 className="w-4 h-4 shrink-0 me-2" />
            <span>
              {hasCounts
                ? t('admin.connections.refreshSchemaSuccess', {
                    tables: tablesCount,
                    columns: columnsCount,
                  })
                : t('admin.connections.schema.success')}
            </span>
          </>
        ) : isErrorState && errorMessage ? (
          <>
            <AlertCircle className="w-4 h-4 shrink-0 me-2" />
            <span className="text-xs text-start">{errorMessage}</span>
          </>
        ) : (
          <>
            <RefreshCw className="w-4 h-4 me-2" />
            {t('admin.connections.refreshSchema')}
          </>
        )}
      </button>

      {lastRefreshed && !refreshSchemaMutation.isPending && (
        <div className="text-xs text-text-muted select-none px-1 mt-1">
          {t('admin.connections.schema.refreshed', {
            time: formatRefreshedAt(lastRefreshed),
          })}
        </div>
      )}
    </div>
  );
};
