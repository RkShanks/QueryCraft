import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useCurrentUser } from '../hooks/useAuth';
import { useAdminRoles } from '../hooks/useAdminRoles';
import { useAdminQuotas } from '../hooks/useAdminQuotas';
import type { RoleQuotaConfig, RoleQuotaUpsert, QuotaDimensionStatus } from '../api/quotas';
import { hasPermission } from '../auth/permissions';
import { Shield, RefreshCw, Trash2, Edit2, CheckCircle2, XCircle, X, ShieldAlert } from 'lucide-react';

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

export const AdminQuotasPage: React.FC = () => {
  const { t } = useTranslation();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [editingQuota, setEditingQuota] = useState<RoleQuotaConfig | null>(null);

  // Form states
  const [queryLimit, setQueryLimit] = useState<string>('');
  const [executionLimit, setExecutionLimit] = useState<string>('');
  const [exportLimit, setExportLimit] = useState<string>('');

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

  // 1. Permission check
  const { data: userResponse } = useCurrentUser();
  const user = userResponse?.data;

  const hasRolesPermission = hasPermission(user, 'admin.roles.manage');

  // 2. Fetch roles only if permitted
  const rolesQuery = useAdminRoles({
    enabled: !!hasRolesPermission,
  }).listQuery;

  // 3. Fetch quotas & status
  const { listQuery, statusQuery, upsertMutation, deleteMutation } = useAdminQuotas({
    onUpsertSuccess: () => {
      addToast('success', t('common.saveSuccess') || 'Changes saved successfully');
      setEditingQuota(null);
    },
    onUpsertError: (err) => {
      addToast('error', getErrorMessage(err, 'admin.settings.error'));
    },
    onDeleteSuccess: () => {
      addToast('success', t('admin.quotas.deleteSuccess') || 'Quota removed successfully');
    },
    onDeleteError: (err) => {
      addToast('error', getErrorMessage(err, 'admin.settings.error'));
    },
  });

  const handleEdit = (quota: RoleQuotaConfig) => {
    setEditingQuota(quota);
    setQueryLimit(quota.daily_query_limit !== null ? String(quota.daily_query_limit) : '');
    setExecutionLimit(quota.daily_execution_limit !== null ? String(quota.daily_execution_limit) : '');
    setExportLimit(quota.daily_export_limit !== null ? String(quota.daily_export_limit) : '');
  };

  const handleCancel = () => {
    setEditingQuota(null);
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingQuota) return;

    const parseVal = (val: string): number | null => {
      if (val === '') return null;
      const parsed = parseInt(val, 10);
      return isNaN(parsed) ? null : parsed;
    };

    const data: RoleQuotaUpsert = {
      daily_query_limit: parseVal(queryLimit),
      daily_execution_limit: parseVal(executionLimit),
      daily_export_limit: parseVal(exportLimit),
    };

    upsertMutation.mutate({
      roleId: editingQuota.role_id,
      data,
    });
  };

  const handleDelete = (roleId: string) => {
    if (window.confirm(t('admin.connections.deleteConfirm') || 'Are you sure?')) {
      deleteMutation.mutate(roleId);
    }
  };

  // Loading states
  const isLoading =
    listQuery.isLoading ||
    statusQuery.isLoading ||
    (hasRolesPermission && rolesQuery.isLoading);

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <RefreshCw className="animate-spin text-neon-cyan w-8 h-8" data-testid="loading-spinner" />
      </div>
    );
  }

  // Merging client-side
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
    <div className="p-6 max-w-7xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 relative">
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
          {t('quota.page_title')}
        </h1>
      </div>

      {/* Discovery Warning Banner */}
      {!hasRolesPermission && (
        <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-400 text-sm flex items-start gap-3">
          <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold">{t('quota.discovery_warning')}</p>
          </div>
        </div>
      )}

      {editingQuota && (
        <div className="p-6 bg-gray-900 border border-gray-800 rounded-xl space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
          <div className="flex justify-between items-center border-b border-gray-800 pb-4">
            <h2 className="text-lg font-semibold text-white">
              {t('admin.roles.form.editPolicy')} - {editingQuota.role_name}
            </h2>
            <button onClick={handleCancel} className="text-gray-400 hover:text-white transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>

          <form onSubmit={handleSave} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label htmlFor="query_limit" className="block text-sm font-medium text-gray-400 mb-1">
                  {t('quota.query_limit')}
                </label>
                <input
                  id="query_limit"
                  type="number"
                  min="0"
                  value={queryLimit}
                  onChange={(e) => setQueryLimit(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors"
                />
              </div>

              <div>
                <label htmlFor="execution_limit" className="block text-sm font-medium text-gray-400 mb-1">
                  {t('quota.execution_limit')}
                </label>
                <input
                  id="execution_limit"
                  type="number"
                  min="0"
                  value={executionLimit}
                  onChange={(e) => setExecutionLimit(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors"
                />
              </div>

              <div>
                <label htmlFor="export_limit" className="block text-sm font-medium text-gray-400 mb-1">
                  {t('quota.export_limit')}
                </label>
                <input
                  id="export_limit"
                  type="number"
                  min="0"
                  value={exportLimit}
                  onChange={(e) => setExportLimit(e.target.value)}
                  className="w-full bg-gray-950 border border-gray-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-neon-cyan transition-colors"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-gray-800">
              <button
                type="button"
                onClick={handleCancel}
                className="px-4 py-2 border border-gray-800 rounded-lg text-gray-400 hover:text-white transition-colors"
              >
                {t('common.cancel')}
              </button>
              <button
                type="submit"
                disabled={upsertMutation.isPending}
                className="px-4 py-2 bg-neon-cyan text-gray-900 font-semibold rounded-lg hover:bg-opacity-90 transition-colors disabled:opacity-50"
              >
                {t('common.save')}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Quotas List Table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden shadow-xl">
        <table className="w-full text-start border-collapse">
          <thead>
            <tr className="border-b border-gray-800 text-gray-400 text-xs font-semibold uppercase tracking-wider bg-gray-950">
              <th className="py-3 px-4 text-start">{t('quota.role_column')}</th>
              <th className="py-3 px-4 text-start">{t('quota.query_limit')}</th>
              <th className="py-3 px-4 text-start">{t('quota.execution_limit')}</th>
              <th className="py-3 px-4 text-start">{t('quota.export_limit')}</th>
              <th className="py-3 px-4 text-end">{t('admin.roles.table.actions') || 'Actions'}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50 text-sm text-gray-300">
            {mergedQuotas.map((q) => {
              const isConfigured = quotas.some((item) => item.role_id === q.role_id);
              return (
                <tr key={q.role_id} className="hover:bg-gray-850/30 transition-colors">
                  <td className="py-3 px-4 font-semibold text-white">{q.role_name}</td>
                  <td className="py-3 px-4">
                    {q.daily_query_limit !== null ? q.daily_query_limit : <span className="text-gray-500 italic">{t('quota.uncapped')}</span>}
                  </td>
                  <td className="py-3 px-4">
                    {q.daily_execution_limit !== null ? q.daily_execution_limit : <span className="text-gray-500 italic">{t('quota.uncapped')}</span>}
                  </td>
                  <td className="py-3 px-4">
                    {q.daily_export_limit !== null ? q.daily_export_limit : <span className="text-gray-500 italic">{t('quota.uncapped')}</span>}
                  </td>
                  <td className="py-3 px-4 text-end">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => handleEdit(q)}
                        className="p-1.5 hover:bg-gray-850 rounded text-gray-400 hover:text-white transition-colors"
                        title={t('common.edit')}
                        data-testid={`edit-quota-${q.role_id}`}
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      {isConfigured && (
                        <button
                          onClick={() => handleDelete(q.role_id)}
                          className="p-1.5 hover:bg-gray-850 rounded text-gray-400 hover:text-red-500 transition-colors"
                          title={t('common.delete')}
                          data-testid={`delete-quota-${q.role_id}`}
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

      {/* Quota Consumption Status Sub-Panel */}
      <div className="space-y-4">
        <h2 className="text-xl font-semibold text-white flex items-center gap-2">
          {t('quota.status_title')}
        </h2>
        <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden shadow-xl">
          <table className="w-full text-start border-collapse">
            <thead>
              <tr className="border-b border-gray-800 text-gray-400 text-xs font-semibold uppercase tracking-wider bg-gray-950">
                <th className="py-3 px-4 text-start">{t('quota.role_column')}</th>
                <th className="py-3 px-4 text-start">{t('quota.query_limit')}</th>
                <th className="py-3 px-4 text-start">{t('quota.execution_limit')}</th>
                <th className="py-3 px-4 text-start">{t('quota.export_limit')}</th>
                <th className="py-3 px-4 text-end">{t('quota.reset_at').split(':')[0]}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/50 text-sm text-gray-300">
              {(statusQuery.data?.status || []).map((s) => {
                const renderDim = (dim: QuotaDimensionStatus) => {
                  if (dim.limit === null) {
                    return (
                      <span>
                        {dim.used} / <span className="text-gray-500 italic">{t('quota.uncapped')}</span>
                      </span>
                    );
                  }
                  return (
                    <span>
                      {dim.used} / {dim.limit} (
                      <span className="text-xs text-gray-400">
                        {t('quota.remaining')}: {dim.remaining}
                      </span>
                      )
                    </span>
                  );
                };

                const formattedReset = s.reset_at ? new Date(s.reset_at).toLocaleString() : '';

                return (
                  <tr key={s.role_id} className="hover:bg-gray-850/30 transition-colors">
                    <td className="py-3 px-4 font-semibold text-white">{s.role_name}</td>
                    <td className="py-3 px-4">{renderDim(s.dimensions.queries)}</td>
                    <td className="py-3 px-4">{renderDim(s.dimensions.executions)}</td>
                    <td className="py-3 px-4">{renderDim(s.dimensions.exports)}</td>
                    <td className="py-3 px-4 text-end font-mono text-xs">{formattedReset}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
