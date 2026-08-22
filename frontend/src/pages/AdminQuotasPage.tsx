import React, { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useCurrentUser } from '../hooks/useAuth';
import { useAdminRoles } from '../hooks/useAdminRoles';
import { useAdminQuotas } from '../hooks/useAdminQuotas';
import {
  useQuotaMutationRecovery,
  type QuotaMutationRecovery,
} from '../hooks/useQuotaMutationRecovery';
import { isQuotaSynchronizationPending } from '../api/quotas';
import { formatDateTime, formatNumber } from '../i18n/format';
import { normalizeAppLanguage } from '../i18n/locale';
import type {
  QuotaDimensionStatus,
  RoleQuotaConfig,
  RoleQuotaStatus,
  RoleQuotaUpsert,
} from '../api/quotas';
import { hasPermission, PERMISSIONS } from '../auth/permissions';
import { Shield, RefreshCw, Trash2, Edit2, CheckCircle2, XCircle, X, ShieldAlert } from 'lucide-react';
import { ClientQueryState } from '../components/common/ClientQueryState';

interface Toast {
  id: string;
  type: 'success' | 'error';
  message: string;
}

const ALLOWED_ERROR_KEYS = new Set([
  'error.forbidden',
  'error.unauthorized',
  'error.notFound',
  'error.service_unavailable',
  'error.validation.invalidUUID',
  'error.validation.generic',
]);

function extractErrorKey(error: unknown): string | null {
  if (!error || typeof error !== 'object') {
    return null;
  }
  const errorRecord = error as Record<string, unknown>;
  if (typeof errorRecord.message_key === 'string' && errorRecord.message_key) {
    return errorRecord.message_key;
  }
  if (typeof errorRecord.error === 'string' && errorRecord.error) {
    return errorRecord.error;
  }

  if (errorRecord.detail) {
    if (typeof errorRecord.detail === 'string' && errorRecord.detail.startsWith('error.')) {
      return errorRecord.detail;
    }
    if (typeof errorRecord.detail === 'object') {
      const detailKey = extractErrorKey(errorRecord.detail);
      if (detailKey) return detailKey;
    }
  }

  if (errorRecord.body && typeof errorRecord.body === 'object') {
    const bodyKey = extractErrorKey(errorRecord.body);
    if (bodyKey) return bodyKey;
  }

  return null;
}

type ParsedQuotaLimit =
  | { isValid: true; limit: number | null }
  | { isValid: false };

function parseQuotaLimit(rawLimit: string): ParsedQuotaLimit {
  if (rawLimit === '') {
    return { isValid: true, limit: null };
  }
  const limit = Number(rawLimit);
  if (!Number.isSafeInteger(limit) || limit < 0) {
    return { isValid: false };
  }
  return { isValid: true, limit };
}

interface PanelStateProps {
  message: string;
  variant: 'empty' | 'error';
  retry?: () => void;
}

const PanelState: React.FC<PanelStateProps> = ({ message, variant, retry }) => {
  const { t } = useTranslation();
  return (
    <div
      className={`px-4 py-10 text-center text-sm ${
        variant === 'error' ? 'text-red-400' : 'text-gray-500'
      }`}
      role={variant === 'error' ? 'alert' : 'status'}
    >
      <p>{message}</p>
      {retry && (
        <button
          type="button"
          onClick={retry}
          className="mt-4 min-h-10 rounded-lg border border-red-500/30 px-4 py-2 font-semibold text-red-300 hover:border-red-400 hover:text-red-200"
        >
          {t('common.retry')}
        </button>
      )}
    </div>
  );
};

function renderQuotaDimension(
  dimension: QuotaDimensionStatus,
  uncappedLabel: string,
  remainingLabel: string
) {
  const used = formatNumber(dimension.used);
  const limit = formatNumber(dimension.limit);
  const remaining = formatNumber(dimension.remaining);
  if (dimension.limit === null) {
    return (
      <span>
        <bdi dir="ltr">{used}</bdi> /{' '}
        <span className="text-gray-500 italic">{uncappedLabel}</span>
      </span>
    );
  }
  return (
    <span>
      <bdi dir="ltr">{used}</bdi> / <bdi dir="ltr">{limit}</bdi> (
      <span className="text-xs text-gray-400">
        {remainingLabel}: <bdi dir="ltr">{remaining}</bdi>
      </span>
      )
    </span>
  );
}

function formatResetTime(resetAt: string, language: string): string {
  return formatDateTime(resetAt, { language: normalizeAppLanguage(language) ?? 'en' });
}

interface QuotaLimitValueProps {
  limit: number | null;
}

const QuotaLimitValue: React.FC<QuotaLimitValueProps> = ({ limit }) => {
  const { t } = useTranslation();
  return limit === null ? (
    <span className="text-gray-500 italic">{t('quota.uncapped')}</span>
  ) : (
    <bdi dir="ltr">{limit}</bdi>
  );
};

interface QuotaConfigCardProps {
  quota: RoleQuotaConfig;
  isConfigured: boolean;
  startEdit: (quota: RoleQuotaConfig) => void;
  confirmDelete: (roleId: string) => void;
  mutationsDisabled: boolean;
}

const QuotaConfigCard: React.FC<QuotaConfigCardProps> = ({
  quota,
  isConfigured,
  startEdit,
  confirmDelete,
  mutationsDisabled,
}) => {
  const { t } = useTranslation();
  return (
    <article
      className="p-4 space-y-4"
      aria-label={t('quota.config_summary', { role: quota.role_name })}
    >
      <div className="flex min-w-0 items-start justify-between gap-3">
        <h3 className="min-w-0 break-words font-semibold text-white">
          {quota.role_name}
        </h3>
        <div className="flex shrink-0 items-center justify-end gap-2">
          <button
            onClick={() => startEdit(quota)}
            disabled={mutationsDisabled}
            className="p-2 hover:bg-gray-850 rounded text-gray-400 hover:text-white transition-colors"
            title={t('common.edit')}
          >
            <Edit2 className="w-4 h-4" />
          </button>
          {isConfigured && (
            <button
              onClick={() => confirmDelete(quota.role_id)}
              disabled={mutationsDisabled}
              className="p-2 hover:bg-gray-850 rounded text-gray-400 hover:text-red-500 transition-colors"
              title={t('quota.reset_to_uncapped')}
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            {t('quota.query_limit')}
          </dt>
          <dd className="mt-1 text-gray-200">
            <QuotaLimitValue limit={quota.daily_query_limit} />
          </dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            {t('quota.execution_limit')}
          </dt>
          <dd className="mt-1 text-gray-200">
            <QuotaLimitValue limit={quota.daily_execution_limit} />
          </dd>
        </div>
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            {t('quota.export_limit')}
          </dt>
          <dd className="mt-1 text-gray-200">
            <QuotaLimitValue limit={quota.daily_export_limit} />
          </dd>
        </div>
      </dl>
    </article>
  );
};

interface QuotaRecoveryAlertProps {
  isRetrying: boolean;
  retry: () => void;
}

const QuotaRecoveryAlert: React.FC<QuotaRecoveryAlertProps> = ({
  isRetrying,
  retry,
}) => {
  const { t } = useTranslation();
  return (
    <section
      role="alert"
      aria-labelledby="quota-recovery-title"
      className="flex min-w-0 flex-col gap-4 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-amber-200 sm:flex-row sm:items-center"
    >
      <ShieldAlert className="h-5 w-5 shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <h2 id="quota-recovery-title" className="font-semibold text-amber-100">
          {t('quota.recovery.title')}
        </h2>
        <p className="mt-1 break-words text-sm text-amber-200/90">
          {t('quota.recovery.description')}
        </p>
      </div>
      <button
        type="button"
        onClick={retry}
        disabled={isRetrying}
        className="inline-flex w-full shrink-0 items-center justify-center gap-2 rounded-lg border border-amber-400/40 px-4 py-2 text-sm font-semibold text-amber-100 transition-colors hover:bg-amber-400/10 disabled:opacity-50 sm:w-auto"
      >
        <RefreshCw className={`h-4 w-4 ${isRetrying ? 'animate-spin' : ''}`} />
        {t('common.retry')}
      </button>
    </section>
  );
};

interface QuotaStatusCardProps {
  quotaStatus: RoleQuotaStatus;
}

const QuotaStatusCard: React.FC<QuotaStatusCardProps> = ({ quotaStatus }) => {
  const { t, i18n } = useTranslation();
  const dimensionSummaries: Array<{
    labelKey: string;
    dimension: QuotaDimensionStatus;
  }> = [
    { labelKey: 'quota.query_limit', dimension: quotaStatus.dimensions.queries },
    { labelKey: 'quota.execution_limit', dimension: quotaStatus.dimensions.executions },
    { labelKey: 'quota.export_limit', dimension: quotaStatus.dimensions.exports },
  ];
  return (
    <article
      className="p-4 space-y-4"
      aria-label={t('quota.status_summary', { role: quotaStatus.role_name })}
    >
      <h3 className="font-semibold text-white">{quotaStatus.role_name}</h3>
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
        {dimensionSummaries.map(({ labelKey, dimension }) => (
          <div key={labelKey}>
            <dt className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              {t(labelKey)}
            </dt>
            <dd className="mt-1 text-gray-200">
              {renderQuotaDimension(
                dimension,
                t('quota.uncapped'),
                t('quota.remaining')
              )}
            </dd>
          </div>
        ))}
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            {t('quota.reset_column')}
          </dt>
          <dd dir="ltr" className="mt-1 text-xs font-mono text-gray-300">
            {formatResetTime(quotaStatus.reset_at, i18n.language)}
          </dd>
        </div>
      </dl>
    </article>
  );
};

export const AdminQuotasPage: React.FC = () => {
  const { t, i18n } = useTranslation();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [editingQuota, setEditingQuota] = useState<RoleQuotaConfig | null>(null);
  const [queryLimit, setQueryLimit] = useState<string>('');
  const [executionLimit, setExecutionLimit] = useState<string>('');
  const [exportLimit, setExportLimit] = useState<string>('');
  const [validationError, setValidationError] = useState<string | null>(null);

  const addToast = (type: 'success' | 'error', message: string) => {
    const toastId = `${Date.now()}-${Math.random()}`;
    setToasts((previousToasts) => [...previousToasts, { id: toastId, type, message }]);
    setTimeout(() => {
      setToasts((previousToasts) =>
        previousToasts.filter((toast) => toast.id !== toastId)
      );
    }, 5000);
  };

  const getErrorMessage = (error: unknown, fallbackKey: string): string => {
    const errorKey = extractErrorKey(error);
    if (errorKey && ALLOWED_ERROR_KEYS.has(errorKey)) {
      return t(errorKey);
    }
    return t(fallbackKey);
  };

  const { data: userResponse } = useCurrentUser();
  const user = userResponse?.data;
  const {
    operation: recoveryOperation,
    remember: rememberRecovery,
    clear: clearRecovery,
  } = useQuotaMutationRecovery(user?.id);
  const mutationInFlight = useRef(false);
  const attemptedMutation = useRef<QuotaMutationRecovery | null>(null);

  const hasRolesPermission = hasPermission(user, PERMISSIONS.ADMIN_ROLES_MANAGE);

  const rolesQuery = useAdminRoles({
    enabled: !!hasRolesPermission,
  }).listQuery;

  const { listQuery, statusQuery, upsertMutation, deleteMutation } = useAdminQuotas({
    onUpsertSuccess: () => {
      mutationInFlight.current = false;
      attemptedMutation.current = null;
      clearRecovery();
      addToast('success', t('common.saveSuccess'));
      setEditingQuota(null);
      setValidationError(null);
    },
    onUpsertError: (error) => {
      mutationInFlight.current = false;
      const attempted = attemptedMutation.current;
      attemptedMutation.current = null;
      if (attempted && isQuotaSynchronizationPending(error)) {
        rememberRecovery(attempted);
        setEditingQuota(null);
        setValidationError(null);
        return;
      }
      addToast('error', getErrorMessage(error, 'admin.settings.error'));
    },
    onDeleteSuccess: () => {
      mutationInFlight.current = false;
      attemptedMutation.current = null;
      clearRecovery();
      addToast('success', t('admin.quotas.deleteSuccess'));
    },
    onDeleteError: (error) => {
      mutationInFlight.current = false;
      const attempted = attemptedMutation.current;
      attemptedMutation.current = null;
      if (attempted && isQuotaSynchronizationPending(error)) {
        rememberRecovery(attempted);
        return;
      }
      addToast('error', getErrorMessage(error, 'admin.settings.error'));
    },
  });

  const runQuotaMutation = (operation: QuotaMutationRecovery) => {
    if (mutationInFlight.current) return;
    mutationInFlight.current = true;
    attemptedMutation.current = operation;
    if (operation.kind === 'upsert') {
      upsertMutation.mutate({ roleId: operation.roleId, data: operation.data });
      return;
    }
    deleteMutation.mutate(operation.roleId);
  };

  const startQuotaEdit = (quota: RoleQuotaConfig) => {
    setEditingQuota(quota);
    setQueryLimit(quota.daily_query_limit !== null ? String(quota.daily_query_limit) : '');
    setExecutionLimit(
      quota.daily_execution_limit !== null ? String(quota.daily_execution_limit) : ''
    );
    setExportLimit(
      quota.daily_export_limit !== null ? String(quota.daily_export_limit) : ''
    );
    setValidationError(null);
  };

  const cancelQuotaEdit = () => {
    setEditingQuota(null);
    setValidationError(null);
  };

  const saveQuota = (event: React.FormEvent) => {
    event.preventDefault();
    if (!editingQuota || recoveryOperation) return;

    const parsedQueryLimit = parseQuotaLimit(queryLimit);
    const parsedExecutionLimit = parseQuotaLimit(executionLimit);
    const parsedExportLimit = parseQuotaLimit(exportLimit);
    if (
      !parsedQueryLimit.isValid ||
      !parsedExecutionLimit.isValid ||
      !parsedExportLimit.isValid
    ) {
      setValidationError(t('quota.validation.non_negative_integer'));
      return;
    }

    const quotaUpdate: RoleQuotaUpsert = {
      daily_query_limit: parsedQueryLimit.limit,
      daily_execution_limit: parsedExecutionLimit.limit,
      daily_export_limit: parsedExportLimit.limit,
    };

    setValidationError(null);
    runQuotaMutation({
      kind: 'upsert',
      roleId: editingQuota.role_id,
      data: quotaUpdate,
    });
  };

  const confirmQuotaDelete = (roleId: string) => {
    if (!recoveryOperation && window.confirm(t('quota.deleteConfirm'))) {
      runQuotaMutation({ kind: 'delete', roleId });
    }
  };

  const retryQuotaMutation = () => {
    if (recoveryOperation) runQuotaMutation(recoveryOperation);
  };

  const mutationsDisabled =
    recoveryOperation !== null ||
    upsertMutation.isPending ||
    deleteMutation.isPending;

  const quotaStatuses = statusQuery.data?.status ?? [];

  const isLoading =
    listQuery.isLoading ||
    statusQuery.isLoading ||
    (hasRolesPermission && rolesQuery.isLoading);

  if (isLoading) {
    return (
      <div
        className="flex justify-center items-center h-64"
        role="status"
        aria-label={t('quota.loading')}
      >
        <RefreshCw
          className="animate-spin text-neon-cyan w-8 h-8"
          data-testid="loading-spinner"
        />
      </div>
    );
  }

  const quotas = listQuery.data?.quotas || [];
  const mergedQuotas: RoleQuotaConfig[] =
    hasRolesPermission && rolesQuery.data?.roles
      ? rolesQuery.data.roles.map((role) => {
          const q = quotas.find((item) => item.role_id === role.id);
          return (
            q || {
              role_id: role.id,
              role_name: role.name,
              daily_query_limit: null,
              daily_execution_limit: null,
              daily_export_limit: null,
            }
          );
        })
      : quotas;

  return (
    <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 relative">
      <div className="fixed top-6 start-6 end-6 sm:start-auto sm:w-full z-50 flex flex-col gap-3 max-w-sm select-none pointer-events-none">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-start gap-3 p-4 rounded-xl border shadow-2xl backdrop-blur-md animate-fade-in transition-all ${
              toast.type === 'success'
                ? 'bg-green-500/10 border-green-500/20 text-green-400'
                : 'bg-red-500/10 border-red-500/20 text-red-400'
            }`}
          >
            <div className="shrink-0 mt-0.5">
              {toast.type === 'success' ? (
                <CheckCircle2 className="w-5 h-5 text-green-500" />
              ) : (
                <XCircle className="w-5 h-5 text-red-500" />
              )}
            </div>
            <div className="flex-1 text-sm font-medium leading-relaxed">
              {toast.message}
            </div>
            <button
              onClick={() =>
                setToasts((previousToasts) =>
                  previousToasts.filter((currentToast) => currentToast.id !== toast.id)
                )
              }
              className="shrink-0 text-gray-400 hover:text-white p-0.5 rounded transition-colors"
              aria-label={t('common.close')}
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      <div className="flex justify-between items-center border-b border-gray-800 pb-4">
        <h1 className="text-2xl font-semibold text-text-primary flex items-center gap-2">
          <Shield className="w-6 h-6 text-neon-cyan" />
          {t('quota.page_title')}
        </h1>
      </div>

      {!hasRolesPermission && (
        <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-400 text-sm flex items-start gap-3">
          <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">{t('quota.discovery_warning')}</p>
          </div>
        </div>
      )}

      {recoveryOperation && (
        <QuotaRecoveryAlert
          isRetrying={upsertMutation.isPending || deleteMutation.isPending}
          retry={retryQuotaMutation}
        />
      )}

      {hasRolesPermission && rolesQuery.isError && (
        <ClientQueryState
          query={rolesQuery}
          fallbackErrorKey="error.service_unavailable"
        />
      )}

      {editingQuota && (
        <div className="p-6 bg-gray-900 border border-gray-800 rounded-xl space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
          <div className="flex justify-between items-center border-b border-gray-800 pb-4">
            <h2 className="text-lg font-semibold text-white">
              {t('quota.edit_title', { role: editingQuota.role_name })}
            </h2>
            <button
              onClick={cancelQuotaEdit}
              className="text-gray-400 hover:text-white transition-colors"
              aria-label={t('common.close')}
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <form onSubmit={saveQuota} className="space-y-4" noValidate>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label
                  htmlFor="query_limit"
                  className="block text-sm font-medium text-gray-400 mb-1"
                >
                  {t('quota.query_limit')}
                </label>
                <input
                  dir="ltr"
                  id="query_limit"
                  type="number"
                  min="0"
                  step="1"
                  value={queryLimit}
                  onChange={(event) => {
                    setQueryLimit(event.target.value);
                    setValidationError(null);
                  }}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors"
                />
              </div>

              <div>
                <label
                  htmlFor="execution_limit"
                  className="block text-sm font-medium text-gray-400 mb-1"
                >
                  {t('quota.execution_limit')}
                </label>
                <input
                  dir="ltr"
                  id="execution_limit"
                  type="number"
                  min="0"
                  step="1"
                  value={executionLimit}
                  onChange={(event) => {
                    setExecutionLimit(event.target.value);
                    setValidationError(null);
                  }}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors"
                />
              </div>

              <div>
                <label
                  htmlFor="export_limit"
                  className="block text-sm font-medium text-gray-400 mb-1"
                >
                  {t('quota.export_limit')}
                </label>
                <input
                  dir="ltr"
                  id="export_limit"
                  type="number"
                  min="0"
                  step="1"
                  value={exportLimit}
                  onChange={(event) => {
                    setExportLimit(event.target.value);
                    setValidationError(null);
                  }}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors"
                />
              </div>
            </div>

            {validationError && (
              <p className="text-sm text-red-400" role="alert">
                {validationError}
              </p>
            )}

            <div className="flex justify-end gap-3 pt-4 border-t border-gray-800">
              <button
                type="button"
                onClick={cancelQuotaEdit}
                className="px-4 py-2 border border-gray-800 rounded-lg text-gray-400 hover:text-white transition-colors"
              >
                {t('common.cancel')}
              </button>
              <button
                type="submit"
                disabled={mutationsDisabled}
                className="px-4 py-2 bg-neon-cyan text-gray-900 font-semibold rounded-lg hover:bg-opacity-90 transition-colors disabled:opacity-50"
              >
                {t('common.save')}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden shadow-xl">
        {listQuery.isError && listQuery.data === undefined ? (
          <ClientQueryState
            query={listQuery}
            fallbackErrorKey="error.service_unavailable"
            getOrdinaryErrorMessage={(error) =>
              getErrorMessage(error, 'error.service_unavailable')
            }
          />
        ) : mergedQuotas.length === 0 ? (
          <PanelState message={t('quota.empty')} variant="empty" />
        ) : (
          <>
            <div className="p-4">
              <ClientQueryState
                query={listQuery}
                fallbackErrorKey="error.service_unavailable"
              />
            </div>
            <div className="lg:hidden divide-y divide-gray-800/50">
              {mergedQuotas.map((quota) => (
                <QuotaConfigCard
                  key={quota.role_id}
                  quota={quota}
                  isConfigured={quotas.some(
                    (configuredQuota) => configuredQuota.role_id === quota.role_id
                  )}
                  startEdit={startQuotaEdit}
                  confirmDelete={confirmQuotaDelete}
                  mutationsDisabled={mutationsDisabled}
                />
              ))}
            </div>
            <div
              className="hidden lg:block overflow-x-auto"
              data-testid="quota-config-table-scroll"
            >
              <table className="w-full min-w-[720px] text-start border-collapse">
                <thead>
                  <tr className="border-b border-gray-800 text-gray-400 text-xs font-semibold uppercase tracking-wider bg-gray-950">
                    <th className="py-3 px-4 text-start">{t('quota.role_column')}</th>
                    <th className="py-3 px-4 text-start">{t('quota.query_limit')}</th>
                    <th className="py-3 px-4 text-start">
                      {t('quota.execution_limit')}
                    </th>
                    <th className="py-3 px-4 text-start">{t('quota.export_limit')}</th>
                    <th className="py-3 px-4 text-end">
                      {t('admin.roles.table.actions')}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/50 text-sm text-gray-300">
                  {mergedQuotas.map((quota) => {
                    const isConfigured = quotas.some(
                      (configuredQuota) => configuredQuota.role_id === quota.role_id
                    );
                    return (
                      <tr
                        key={quota.role_id}
                        className="hover:bg-gray-850/30 transition-colors"
                      >
                        <td className="py-3 px-4 font-semibold text-white">
                          {quota.role_name}
                        </td>
                        <td className="py-3 px-4">
                          <QuotaLimitValue limit={quota.daily_query_limit} />
                        </td>
                        <td className="py-3 px-4">
                          <QuotaLimitValue limit={quota.daily_execution_limit} />
                        </td>
                        <td className="py-3 px-4">
                          <QuotaLimitValue limit={quota.daily_export_limit} />
                        </td>
                        <td className="py-3 px-4 text-end">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => startQuotaEdit(quota)}
                              disabled={mutationsDisabled}
                              className="p-1.5 hover:bg-gray-850 rounded text-gray-400 hover:text-white transition-colors"
                              title={t('common.edit')}
                              data-testid={`edit-quota-${quota.role_id}`}
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            {isConfigured && (
                              <button
                                onClick={() => confirmQuotaDelete(quota.role_id)}
                                disabled={mutationsDisabled}
                                className="p-1.5 hover:bg-gray-850 rounded text-gray-400 hover:text-red-500 transition-colors"
                                title={t('quota.reset_to_uncapped')}
                                data-testid={`delete-quota-${quota.role_id}`}
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      <div className="space-y-4">
        <h2 className="text-xl font-semibold text-white flex items-center gap-2">
          {t('quota.status_title')}
        </h2>
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden shadow-xl">
          {statusQuery.isError && quotaStatuses.length === 0 ? (
            <ClientQueryState
              query={statusQuery}
              fallbackErrorKey="error.service_unavailable"
              getOrdinaryErrorMessage={(error) =>
                getErrorMessage(error, 'error.service_unavailable')
              }
            />
          ) : quotaStatuses.length === 0 ? (
            <PanelState message={t('quota.status_empty')} variant="empty" />
          ) : (
            <>
              <div className="p-4">
                <ClientQueryState
                  query={statusQuery}
                  fallbackErrorKey="error.service_unavailable"
                  isPartial={statusQuery.data?.next_cursor != null}
                />
              </div>
              <div className="lg:hidden divide-y divide-gray-800/50">
                {quotaStatuses.map((quotaStatus) => (
                  <QuotaStatusCard
                    key={quotaStatus.role_id}
                    quotaStatus={quotaStatus}
                  />
                ))}
              </div>
              <div
                className="hidden lg:block overflow-x-auto"
                data-testid="quota-status-table-scroll"
              >
                <table className="w-full min-w-[760px] text-start border-collapse">
                  <thead>
                    <tr className="border-b border-gray-800 text-gray-400 text-xs font-semibold uppercase tracking-wider bg-gray-950">
                      <th className="py-3 px-4 text-start">
                        {t('quota.role_column')}
                      </th>
                      <th className="py-3 px-4 text-start">
                        {t('quota.query_limit')}
                      </th>
                      <th className="py-3 px-4 text-start">
                        {t('quota.execution_limit')}
                      </th>
                      <th className="py-3 px-4 text-start">
                        {t('quota.export_limit')}
                      </th>
                      <th className="py-3 px-4 text-end">
                        {t('quota.reset_column')}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800/50 text-sm text-gray-300">
                    {quotaStatuses.map((quotaStatus) => {
                      const formattedReset = quotaStatus.reset_at
                        ? formatResetTime(quotaStatus.reset_at, i18n.language)
                        : '';

                      return (
                        <tr
                          key={quotaStatus.role_id}
                          className="hover:bg-gray-850/30 transition-colors"
                        >
                          <td className="py-3 px-4 font-semibold text-white">
                            {quotaStatus.role_name}
                          </td>
                          <td className="py-3 px-4">
                            {renderQuotaDimension(
                              quotaStatus.dimensions.queries,
                              t('quota.uncapped'),
                              t('quota.remaining')
                            )}
                          </td>
                          <td className="py-3 px-4">
                            {renderQuotaDimension(
                              quotaStatus.dimensions.executions,
                              t('quota.uncapped'),
                              t('quota.remaining')
                            )}
                          </td>
                          <td className="py-3 px-4">
                            {renderQuotaDimension(
                              quotaStatus.dimensions.exports,
                              t('quota.uncapped'),
                              t('quota.remaining')
                            )}
                          </td>
                          <td dir="ltr" className="py-3 px-4 text-end font-mono text-xs">
                            {formattedReset}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              {(statusQuery.hasNextPage || statusQuery.isFetchNextPageError) && (
                <div className="flex flex-col items-center gap-3 border-t border-gray-800 p-4">
                  {statusQuery.isFetchNextPageError && (
                    <p className="text-center text-sm text-red-400" role="alert">
                      {getErrorMessage(statusQuery.error, 'error.service_unavailable')}
                    </p>
                  )}
                  <button
                    type="button"
                    onClick={() => void statusQuery.fetchNextPage()}
                    disabled={statusQuery.isFetchingNextPage}
                    className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-gray-700 px-4 py-2 text-sm font-semibold text-gray-200 transition-colors hover:border-neon-cyan hover:text-neon-cyan disabled:cursor-wait disabled:opacity-50 sm:w-auto"
                  >
                    {statusQuery.isFetchingNextPage
                      ? t('quota.loading_more_status')
                      : statusQuery.isFetchNextPageError
                        ? t('common.retry')
                        : t('quota.load_more_status')}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};
