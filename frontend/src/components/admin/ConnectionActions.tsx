import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useConnections } from '../../hooks/useConnections';
import { AlertCircle, Loader2, Power, Trash2 } from 'lucide-react';

export interface ConnectionActionsProps {
  connectionId: string;
  lifecycleState: 'active' | 'disabled';
  disabled?: boolean;
  onSuccess?: () => void;
  onError?: (error: unknown) => void;
}

const KNOWN_SAFE_KEYS = [
  'error.connection_referenced_delete_blocked',
  'error.connection_already_active',
  'error.connection_already_disabled',
  'error.connection_not_found',
  'error.credential_config',
  'error.unknown.message',
];

const mapCategoryToKey = (category?: string | null): string => {
  if (!category) return 'error.unknown.message';
  if (category === 'connection_referenced_delete_blocked' || category === 'referenced_delete_blocked') {
    return 'error.connection_referenced_delete_blocked';
  }
  if (category === 'connection_already_active') {
    return 'error.connection_already_active';
  }
  if (category === 'connection_already_disabled') {
    return 'error.connection_already_disabled';
  }
  if (category === 'connection_not_found') {
    return 'error.connection_not_found';
  }
  if (category === 'credential_config') {
    return 'error.credential_config';
  }
  return 'error.unknown.message';
};

const getSafeMessageKey = (key?: string | null): string => {
  if (key && KNOWN_SAFE_KEYS.includes(key)) {
    return key;
  }
  return 'error.unknown.message';
};

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
    const errorObj = activeError as unknown as Record<string, unknown> | null;
    if (errorObj && typeof errorObj === 'object' && 'message_key' in errorObj && typeof errorObj.message_key === 'string') {
      errorMessage = t(getSafeMessageKey(errorObj.message_key));
    } else if (errorObj && typeof errorObj === 'object' && 'error' in errorObj && typeof errorObj.error === 'string') {
      errorMessage = t(mapCategoryToKey(errorObj.error));
    } else {
      errorMessage = t('error.unknown.message');
    }
  }

  return (
    <div className="flex flex-col gap-2 text-start">
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
        <div className="flex flex-col gap-2 p-3 bg-bg-elevated border border-border rounded-md select-none mt-1">
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
        <div className="flex items-start gap-2 text-xs text-red-500 bg-red-500/10 border border-red-500/20 px-3 py-2 rounded-md transition-all select-none">
          <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
};
