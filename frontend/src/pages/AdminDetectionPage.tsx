import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAdminDetection } from '../hooks/useAdminDetection';
import { Shield, RefreshCw, CheckCircle2, XCircle, X, ShieldAlert } from 'lucide-react';
import { ClientQueryState } from '../components/common/ClientQueryState';
import { formatDateTime } from '../i18n/format';
import { validateThresholds, parseThresholdValue } from '../detectionThresholds';

interface Toast {
  id: string;
  type: 'success' | 'error';
  message: string;
}

const ALLOWED_ERROR_KEYS = new Set([
  'error.forbidden',
  'error.unauthorized',
  'error.notFound',
  'error.validation.invalidUUID',
]);

function extractErrorKey(err: unknown): string | null {
  if (!err || typeof err !== 'object') {
    return null;
  }
  const obj = err as Record<string, unknown>;
  if (typeof obj.message_key === 'string' && obj.message_key) return obj.message_key;
  if (typeof obj.error === 'string' && obj.error) return obj.error;

  if (obj.detail) {
    if (typeof obj.detail === 'string' && obj.detail.startsWith('error.')) {
      return obj.detail;
    } else if (typeof obj.detail === 'object') {
      const key = extractErrorKey(obj.detail);
      if (key) return key;
    }
  }

  if (obj.body && typeof obj.body === 'object') {
    const key = extractErrorKey(obj.body);
    if (key) return key;
  }

  return null;
}

export const AdminDetectionPage: React.FC = () => {
  const { t } = useTranslation();
  const [toasts, setToasts] = useState<Toast[]>([]);
  
  const [blockVal, setBlockVal] = useState<string>('0.8');
  const [flagVal, setFlagVal] = useState<string>('0.5');
  const [validationError, setValidationError] = useState<string | null>(null);

  const addToast = (type: 'success' | 'error', message: string) => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  };

  const getErrorMessage = (err: unknown, fallbackKey: string): string => {
    const key = extractErrorKey(err);
    if (key && ALLOWED_ERROR_KEYS.has(key)) {
      return t(key);
    }
    return t(fallbackKey);
  };

  const { configQuery, updateMutation } = useAdminDetection({
    onUpdateSuccess: () => {
      addToast('success', t('common.saveSuccess') || 'Changes saved successfully');
      setValidationError(null);
    },
    onUpdateError: (err) => {
      addToast('error', getErrorMessage(err, 'detection.save_error'));
    },
  });

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (configQuery.data) {
      setBlockVal(String(configQuery.data.block_confidence));
      setFlagVal(String(configQuery.data.flag_confidence));
    }
  }, [configQuery.data]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (updateMutation.isPending) return;
    const result = validateThresholds(blockVal, flagVal);
    if (!result.ok) {
      setValidationError(
        result.issue === 'order'
          ? t('detection.validation_error')
          : t('detection.validation_range')
      );
      return;
    }

    setValidationError(null);
    updateMutation.mutate({
      block_confidence: result.block,
      flag_confidence: result.flag,
    });
  };

  const authoritative = configQuery.data;
  const blockNumber = parseThresholdValue(blockVal);
  const flagNumber = parseThresholdValue(flagVal);
  const isDirty =
    blockNumber === null ||
    flagNumber === null ||
    (authoritative !== undefined &&
      (blockNumber !== authoritative.block_confidence ||
        flagNumber !== authoritative.flag_confidence));

  const handleReset = () => {
    if (!authoritative || updateMutation.isPending) return;
    setBlockVal(String(authoritative.block_confidence));
    setFlagVal(String(authoritative.flag_confidence));
    setValidationError(null);
  };

  if (configQuery.isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <RefreshCw className="animate-spin text-neon-cyan w-8 h-8" data-testid="loading-spinner" />
      </div>
    );
  }

  if (configQuery.isError && configQuery.data === undefined) {
    const err = configQuery.error;
    const isForbidden = extractErrorKey(err) === 'error.forbidden' || (err as { status?: number })?.status === 403;
    if (!isForbidden) {
      return (
        <div className="mx-auto flex min-h-64 max-w-xl items-center justify-center p-6">
          <ClientQueryState
            query={configQuery}
            fallbackErrorKey="error.unknown.message"
          />
        </div>
      );
    }
    return (
      <div className="p-6 max-w-xl mx-auto mt-12 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm flex items-start gap-3">
        <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold" data-testid="access-denied-error">
            {isForbidden ? t('error.forbidden') : t('error.unknown.message')}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 relative">
      <ClientQueryState query={configQuery} fallbackErrorKey="error.unknown.message" />
      {/* Global Toast Container */}
      <div className="fixed top-6 end-6 z-50 flex flex-col gap-3 max-w-sm w-full select-none pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            role={t.type === 'success' ? 'status' : 'alert'}
            aria-label={t.message}
            className={`pointer-events-auto flex items-start gap-3 p-4 rounded-xl border shadow-2xl backdrop-blur-md animate-fade-in transition-all ${
              t.type === 'success'
                ? 'bg-green-500/10 border-green-500/20 text-green-400'
                : 'bg-red-500/10 border-red-500/20 text-red-400'
            }`}
          >
            <div className="shrink-0 mt-0.5">
              {t.type === 'success' ? (
                <CheckCircle2 className="w-5 h-5 text-green-500" aria-hidden="true" />
              ) : (
                <XCircle className="w-5 h-5 text-red-500" aria-hidden="true" />
              )}
            </div>
            <div className="flex-1 text-sm font-medium leading-relaxed">{t.message}</div>
            <button
              onClick={() => setToasts((prev) => prev.filter((item) => item.id !== t.id))}
              className="shrink-0 text-gray-400 hover:text-white p-0.5 rounded transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      <div className="flex justify-between items-center border-b border-gray-800 pb-4">
        <h1 className="text-2xl font-semibold text-text-primary flex items-center gap-2">
          <Shield className="w-6 h-6 text-neon-cyan" />
          {t('detection.page_title')}
        </h1>
        {configQuery.data?.updated_at && (
          <span data-testid="detection-updated-at" className="text-xs text-gray-500">
            {t('detection.updated_at')}:{' '}
            <bdi data-testid="detection-updated-at-value" dir="ltr">
              {formatDateTime(configQuery.data.updated_at)}
            </bdi>
          </span>
        )}
      </div>

      {validationError && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm flex items-start gap-3">
          <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" aria-hidden="true" />
          <div>
            <p className="font-semibold" role="alert" id="detection-validation-error">
              {validationError}
            </p>
          </div>
        </div>
      )}

      <form onSubmit={handleSave} className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-6 shadow-xl">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <label htmlFor="block_confidence" className="block text-sm font-medium text-gray-400">
              {t('detection.block_threshold')}
            </label>
            <div className="flex items-center gap-4">
              <input
                id="block_confidence"
                type="range"
                min="0.0"
                max="1.0"
                step="0.05"
                value={blockVal}
                onChange={(e) => setBlockVal(e.target.value)}
                className="w-full h-2 bg-gray-950 rounded-lg appearance-none cursor-pointer accent-neon-cyan focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900"
              />
              <input
                dir="ltr"
                type="number"
                aria-label={t('detection.block_threshold')}
                min="0.0"
                max="1.0"
                step="0.01"
                value={blockVal}
                onChange={(e) => setBlockVal(e.target.value)}
                aria-invalid={validationError ? true : undefined}
                aria-describedby={validationError ? 'detection-validation-error' : undefined}
                className="w-20 bg-gray-950 border border-gray-800 rounded-lg px-2 py-1 text-white text-center focus-visible:outline-none focus-visible:border-neon-cyan focus-visible:ring-2 focus-visible:ring-neon-cyan focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label htmlFor="flag_confidence" className="block text-sm font-medium text-gray-400">
              {t('detection.flag_threshold')}
            </label>
            <div className="flex items-center gap-4">
              <input
                id="flag_confidence"
                type="range"
                min="0.0"
                max="1.0"
                step="0.05"
                value={flagVal}
                onChange={(e) => setFlagVal(e.target.value)}
                className="w-full h-2 bg-gray-950 rounded-lg appearance-none cursor-pointer accent-neon-purple focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon-purple focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900"
              />
              <input
                dir="ltr"
                type="number"
                aria-label={t('detection.flag_threshold')}
                min="0.0"
                max="1.0"
                step="0.01"
                value={flagVal}
                onChange={(e) => setFlagVal(e.target.value)}
                aria-invalid={validationError ? true : undefined}
                aria-describedby={validationError ? 'detection-validation-error' : undefined}
                className="w-20 bg-gray-950 border border-gray-800 rounded-lg px-2 py-1 text-white text-center focus-visible:outline-none focus-visible:border-neon-purple focus-visible:ring-2 focus-visible:ring-neon-purple focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900"
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-6 border-t border-gray-800">
          {authoritative !== undefined && isDirty && (
            <button
              type="button"
              onClick={handleReset}
              disabled={updateMutation.isPending}
              className="px-6 py-2.5 border border-gray-700 text-gray-300 font-semibold rounded-lg hover:bg-gray-800 transition-colors disabled:opacity-50 cursor-pointer"
            >
              {t('detection.reset')}
            </button>
          )}
          <button
            type="submit"
            disabled={updateMutation.isPending}
            className="px-6 py-2.5 bg-neon-cyan text-gray-900 font-semibold rounded-lg hover:bg-opacity-90 transition-colors disabled:opacity-50 flex items-center gap-2 cursor-pointer"
          >
            {updateMutation.isPending && <RefreshCw className="w-4 h-4 animate-spin" aria-hidden="true" />}
            {t('detection.save')}
          </button>
        </div>
        <p role="status" aria-live="polite" className="sr-only">
          {updateMutation.isPending ? t('detection.saving') : ''}
        </p>
      </form>
    </div>
  );
};
