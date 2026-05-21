import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useConnections } from '../../hooks/useConnections';
import { AlertCircle, Loader2, Power, Trash2 } from 'lucide-react';
import { getSafeConnectionErrorKey } from './connectionErrorMessages';

export interface ConnectionActionsProps {
  connectionId: string;
  lifecycleState: 'active' | 'disabled';
  disabled?: boolean;
  onSuccess?: () => void;
  onError?: (error: unknown) => void;
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
    disableMutation.isError,
    enableMutation.isError,
    deleteMutation.isError,
    disableMutation.reset,
    enableMutation.reset,
    deleteMutation.reset,
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
        if (onSuccess) onSuccess();
      },
      onError: (err) => {
        if (onError) onError(err);
      },
    });
  };

  const handleEnable = (e: React.MouseEvent) => {
    e.preventDefault();
    if (isActionDisabled) return;

    enableMutation.mutate(connectionId, {
      onSuccess: () => {
        if (onSuccess) onSuccess();
      },
      onError: (err) => {
        if (onError) onError(err);
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
        if (onSuccess) onSuccess();
      },
      onError: (err) => {
        if (onError) onError(err);
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

      {displayConfirm && (
        <div className="absolute top-full right-0 mt-1 z-50 flex flex-col gap-2 p-3 bg-bg-card border border-border rounded-md shadow-lg select-none min-w-[240px]">
          <p className="text-xs text-text-secondary">
            {t('admin.connections.deleteConfirm')}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleCancelDelete}
              disabled={isActionDisabled}
              className="inline-flex items-center justify-center px-3 py-1.5 border border-border bg-transparent text-text-primary hover:bg-bg-elevated rounded-md text-xs font-medium transition-all focus:outline-none focus:ring-2 focus:ring-neon-cyan/20 disabled:opacity-50 disabled:cursor-not-allowed select-none"
            >
              {t('common.cancel')}
            </button>
            <button
              type="button"
              data-testid="confirm-delete-btn"
              onClick={handleConfirmDelete}
              disabled={isActionDisabled}
              className="inline-flex items-center justify-center px-3 py-1.5 border border-red-500/20 bg-red-500/10 text-red-500 hover:bg-red-500/20 rounded-md text-xs font-medium transition-all focus:outline-none focus:ring-2 focus:ring-red-500/20 disabled:opacity-50 disabled:cursor-not-allowed select-none"
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
      )}

      {errorMessage && (
        <div className="absolute top-full right-0 mt-1 z-50 flex items-start gap-2 text-xs text-red-500 bg-bg-card border border-red-500/20 px-3 py-2 rounded-md shadow-lg transition-all select-none min-w-[240px]">
          <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
};
