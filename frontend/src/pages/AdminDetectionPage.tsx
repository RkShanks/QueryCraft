import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAdminDetection } from '../hooks/useAdminDetection';
import { Shield, RefreshCw, CheckCircle2, XCircle, X, ShieldAlert } from 'lucide-react';

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

const FORBIDDEN_SUFFIX = ' (Forbidden)';

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
      addToast('error', getErrorMessage(err, 'admin.settings.error'));
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
    const block = parseFloat(blockVal);
    const flag = parseFloat(flagVal);

    if (isNaN(block) || isNaN(flag) || block <= flag) {
      setValidationError(t('detection.validation_error'));
      return;
    }

    setValidationError(null);
    updateMutation.mutate({
      block_confidence: block,
      flag_confidence: flag,
    });
  };

  if (configQuery.isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <RefreshCw className="animate-spin text-neon-cyan w-8 h-8" data-testid="loading-spinner" />
      </div>
    );
  }

  if (configQuery.isError) {
    const err = configQuery.error;
    const isForbidden = extractErrorKey(err) === 'error.forbidden' || (err as { status?: number })?.status === 403;
    return (
      <div className="p-6 max-w-xl mx-auto mt-12 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm flex items-start gap-3">
        <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold" data-testid="access-denied-error">
            {isForbidden ? `${t('error.forbidden')}${FORBIDDEN_SUFFIX}` : t('error.unknown.message')}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 relative">
      {/* Global Toast Container */}
      <div className="fixed top-6 end-6 z-50 flex flex-col gap-3 max-w-sm w-full select-none pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start gap-3 p-4 rounded-xl border shadow-2xl backdrop-blur-md animate-fade-in transition-all ${
              t.type === 'success'
                ? 'bg-green-500/10 border-green-500/20 text-green-400'
                : 'bg-red-500/10 border-red-500/20 text-red-400'
            }`}
          >
            <div className="shrink-0 mt-0.5">
              {t.type === 'success' ? (
                <CheckCircle2 className="w-5 h-5 text-green-500" />
              ) : (
                <XCircle className="w-5 h-5 text-red-500" />
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
          <span className="text-xs text-gray-500">
            {t('quota.reset_at').split(':')[0]}: {new Date(configQuery.data.updated_at).toLocaleString()}
          </span>
        )}
      </div>

      {validationError && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm flex items-start gap-3">
          <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">{validationError}</p>
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
                className="w-full h-2 bg-gray-950 rounded-lg appearance-none cursor-pointer accent-neon-cyan focus:outline-none"
              />
              <input
                type="number"
                min="0.0"
                max="1.0"
                step="0.01"
                value={blockVal}
                onChange={(e) => setBlockVal(e.target.value)}
                className="w-20 bg-gray-950 border border-gray-800 rounded-lg px-2 py-1 text-white text-center focus:outline-none focus:border-neon-cyan"
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
                className="w-full h-2 bg-gray-950 rounded-lg appearance-none cursor-pointer accent-neon-purple focus:outline-none"
              />
              <input
                type="number"
                min="0.0"
                max="1.0"
                step="0.01"
                value={flagVal}
                onChange={(e) => setFlagVal(e.target.value)}
                className="w-20 bg-gray-950 border border-gray-800 rounded-lg px-2 py-1 text-white text-center focus:outline-none focus:border-neon-purple"
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-6 border-t border-gray-800">
          <button
            type="submit"
            disabled={updateMutation.isPending}
            className="px-6 py-2.5 bg-neon-cyan text-gray-900 font-semibold rounded-lg hover:bg-opacity-90 transition-colors disabled:opacity-50 flex items-center gap-2 cursor-pointer"
          >
            {updateMutation.isPending && <RefreshCw className="w-4 h-4 animate-spin" />}
            {t('detection.save')}
          </button>
        </div>
      </form>
    </div>
  );
};
