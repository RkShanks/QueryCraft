import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useConnections } from '../../hooks/useConnections';
import { AlertCircle, Loader2, Power, Trash2 } from 'lucide-react';
import { getSafeConnectionErrorKey } from './connectionErrorMessages';

export interface ConnectionActionsProps {
  connectionId: string;
  lifecycleState: 'active' | 'disabled';
  disabled?: boolean;
  onSuccess?: (message: string) => void;
  onError?: (message: string) => void;
}

export const ConnectionActions: React.FC<ConnectionActionsProps> = ({
  connectionId,
  lifecycleState,
  disabled = false,
  onSuccess,
  onError,
}) => {
  const { t } = useTranslation();
  const { disableMutation, enableMutation, deleteMutation } = useConnections();
  const [showConfirm, setShowConfirm] = useState(false);

  React.useEffect(() => {
    const active = disableMutation.isError || enableMutation.isError || deleteMutation.isError;
    if (active) {
      const timer = setTimeout(() => {
        disableMutation.reset();
        enableMutation.reset();
        deleteMutation.reset();
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [
    disableMutation,
    enableMutation,
    deleteMutation,
  ]);

  const isPending = disableMutation.isPending || enableMutation.isPending || deleteMutation.isPending;
  const isActionDisabled = disabled || isPending;

  // Auto-show confirmation dialog if delete is currently pending
  const displayConfirm = showConfirm || deleteMutation.isPending;

  const handleDisable = (e: React.MouseEvent) => {
    e.preventDefault();
    if (isActionDisabled) return;

    disableMutation.mutate(connectionId, {
      onSuccess: () => {
        if (onSuccess) onSuccess(t('admin.connections.disableSuccess') || 'Connection disabled successfully');
      },
      onError: (err) => {
        if (onError) onError(t(getSafeConnectionErrorKey(err)));
      },
    });
  };

  const handleEnable = (e: React.MouseEvent) => {
    e.preventDefault();
    if (isActionDisabled) return;

    enableMutation.mutate(connectionId, {
      onSuccess: () => {
        if (onSuccess) onSuccess(t('admin.connections.enableSuccess') || 'Connection enabled successfully');
      },
      onError: (err) => {
        if (onError) onError(t(getSafeConnectionErrorKey(err)));
      },
    });
  };

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.preventDefault();
    if (isActionDisabled) return;
    setShowConfirm(true);
  };

  const handleCancelDelete = (e: React.MouseEvent) => {
    e.preventDefault();
    setShowConfirm(false);
  };

  const handleConfirmDelete = (e: React.MouseEvent) => {
    e.preventDefault();
    if (isActionDisabled) return;

    deleteMutation.mutate(connectionId, {
      onSuccess: () => {
        setShowConfirm(false);
        if (onSuccess) onSuccess(t('admin.connections.deleteSuccess') || 'Connection deleted successfully');
      },
      onError: (err) => {
        if (onError) onError(t(getSafeConnectionErrorKey(err)));
      },
    });
  };

  // Error UX: allowlist-based safe error mapping across all mutations
  const activeError = disableMutation.error || enableMutation.error || deleteMutation.error;
  let errorMessage = '';

  if (activeError) {
    errorMessage = t(getSafeConnectionErrorKey(activeError));
  }

  return (
    <div className="relative text-start">
      <div className="flex items-center gap-2">
        {lifecycleState === 'active' ? (
          <button
            type="button"
            onClick={handleDisable}
            disabled={isActionDisabled || displayConfirm}
            className="inline-flex items-center justify-center px-3 py-1.5 border border-border bg-transparent text-text-primary hover:bg-bg-elevated rounded-md text-xs font-medium transition-all focus:outline-none focus:ring-2 focus:ring-neon-cyan/20 disabled:opacity-50 disabled:cursor-not-allowed select-none"
          >
            {disableMutation.isPending ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin me-1.5" />
                {t('admin.connections.disabling')}
              </>
            ) : (
              <>
                <Power className="w-3 h-3 me-1.5" />
                {t('admin.connections.disable')}
              </>
            )}
          </button>
        ) : (
          <button
            type="button"
            onClick={handleEnable}
            disabled={isActionDisabled || displayConfirm}
            className="inline-flex items-center justify-center px-3 py-1.5 border border-border bg-transparent text-text-primary hover:bg-bg-elevated rounded-md text-xs font-medium transition-all focus:outline-none focus:ring-2 focus:ring-neon-cyan/20 disabled:opacity-50 disabled:cursor-not-allowed select-none"
          >
            {enableMutation.isPending ? (
              <>
                <Loader2 className="w-3 h-3 animate-spin me-1.5" />
                {t('admin.connections.enabling')}
              </>
            ) : (
              <>
                <Power className="w-3 h-3 me-1.5" />
                {t('admin.connections.enable')}
              </>
            )}
          </button>
        )}

        <button
          type="button"
          onClick={handleDeleteClick}
          disabled={isActionDisabled || displayConfirm}
          className="inline-flex items-center justify-center px-3 py-1.5 border border-red-500/20 bg-red-500/5 text-red-500 hover:bg-red-500/10 rounded-md text-xs font-medium transition-all focus:outline-none focus:ring-2 focus:ring-red-500/20 disabled:opacity-50 disabled:cursor-not-allowed select-none"
        >
          {t('admin.connections.delete')}
        </button>
      </div>

      {errorMessage && (
        <div className="text-xs text-red-500 mt-1 select-none flex items-center gap-1">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {displayConfirm && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-in">
          <div className="bg-bg-card border border-border rounded-xl shadow-2xl max-w-sm w-full p-5 space-y-4 select-none animate-scale-in text-start">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center shrink-0">
                <Trash2 className="w-5 h-5 text-red-500" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-text-primary">
                  {t('admin.connections.delete') || 'Delete Connection'}
                </h3>
                <p className="text-xs text-text-muted mt-0.5">
                  {t('admin.connections.deleteConfirm')}
                </p>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-border/40">
              <button
                type="button"
                onClick={handleCancelDelete}
                disabled={isActionDisabled}
                className="inline-flex items-center justify-center px-3.5 py-1.8 border border-border bg-transparent text-text-primary hover:bg-bg-elevated rounded-md text-xs font-medium transition-all focus:outline-none focus:ring-2 focus:ring-neon-cyan/20 disabled:opacity-50 disabled:cursor-not-allowed select-none"
              >
                {t('common.cancel')}
              </button>
              <button
                type="button"
                data-testid="confirm-delete-btn"
                onClick={handleConfirmDelete}
                disabled={isActionDisabled}
                className="inline-flex items-center justify-center px-3.5 py-1.8 border border-red-500/20 bg-red-500/10 text-red-500 hover:bg-red-500/20 rounded-md text-xs font-medium transition-all focus:outline-none focus:ring-2 focus:ring-red-500/20 disabled:opacity-50 disabled:cursor-not-allowed select-none"
              >
                {deleteMutation.isPending ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin me-1.5" />
                    {t('admin.connections.deleting')}
                  </>
                ) : (
                  <>
                    <Trash2 className="w-3 h-3 me-1.5" />
                    {t('admin.connections.delete')}
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
