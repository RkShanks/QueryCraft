import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAdminAudit } from '../hooks/useAdminAudit';
import { Shield, CheckCircle2, XCircle, AlertTriangle, X, RefreshCw, Download } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import {
  searchAuditEntries,
  exportAuditEntries,
  getAuditRetention,
  type AuditExportRequest,
} from '../api/audit';
import { PERMISSIONS } from '../auth/permissions';
import { requirePermission, usePermission } from '../hooks/usePermission';

interface Toast {
  id: string;
  type: 'success' | 'error';
  message: string;
}

interface LastVerification {
  verified: boolean;
  entries_checked: number;
  first_break_at?: number | null;
  verified_at: string;
}

const RESPONSIVE_AUDIT_CELL_CLASS =
  'flex min-w-0 items-start justify-between gap-4 before:shrink-0 before:text-xs before:font-semibold before:uppercase before:tracking-wider before:text-gray-500 before:content-[attr(data-label)] lg:table-cell lg:px-4 lg:py-3 lg:before:hidden';

export const AdminAuditPage: React.FC = () => {
  const { t } = useTranslation();
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = (type: 'success' | 'error', message: string) => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  };

  const { statusQuery, verifyMutation } = useAdminAudit();
  const canVerifyAudit = usePermission(PERMISSIONS.ADMIN_AUDIT_VERIFY);

  const [isExporting, setIsExporting] = useState<'csv' | 'json' | null>(null);

  // Search Filter Form States
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [actionType, setActionType] = useState('');
  const [actorIdentity, setActorIdentity] = useState('');
  const [outcome, setOutcome] = useState('all');
  const [resourceType, setResourceType] = useState('');
  const [page, setPage] = useState(1);

  const [filters, setFilters] = useState({
    start_date: '',
    end_date: '',
    action_type: '',
    actor_identity: '',
    outcome: '',
    resource_type: '',
  });

  const buildFiltersFromInputs = () => ({
    start_date: startDate ? `${startDate}T00:00:00Z` : '',
    end_date: endDate ? `${endDate}T23:59:59Z` : '',
    action_type: actionType,
    actor_identity: actorIdentity,
    outcome: outcome === 'all' ? '' : outcome,
    resource_type: resourceType,
  });

  const buildExportRequest = (format: 'csv' | 'json'): AuditExportRequest => {
    const currentFilters = buildFiltersFromInputs();
    return {
      format,
      start_date: currentFilters.start_date || undefined,
      end_date: currentFilters.end_date || undefined,
      action_type: (currentFilters.action_type || undefined) as AuditExportRequest['action_type'],
      actor_identity: currentFilters.actor_identity || undefined,
      outcome: (currentFilters.outcome || undefined) as AuditExportRequest['outcome'],
      resource_type: currentFilters.resource_type || undefined,
    };
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    setFilters(buildFiltersFromInputs());
  };

  const handleReset = () => {
    setStartDate('');
    setEndDate('');
    setActionType('');
    setActorIdentity('');
    setOutcome('all');
    setResourceType('');
    setPage(1);
    setFilters({
      start_date: '',
      end_date: '',
      action_type: '',
      actor_identity: '',
      outcome: '',
      resource_type: '',
    });
  };

  const handleExport = async (format: 'csv' | 'json') => {
    requirePermission(canVerifyAudit, PERMISSIONS.ADMIN_AUDIT_VERIFY);
    setIsExporting(format);
    try {
      const blob = await exportAuditEntries(buildExportRequest(format));

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      link.setAttribute('download', `audit_export_${timestamp}.${format}`);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      const errorObj = err as Record<string, unknown> | undefined;
      const messageKey = (errorObj?.message_key as string) || (errorObj?.detail as Record<string, unknown>)?.message_key as string;
      const isQuotaExceeded =
        messageKey === 'error.quota_exceeded' ||
        errorObj?.status === 429 ||
        errorObj?.status_code === 429 ||
        (errorObj?.detail as Record<string, unknown>)?.status === 429;

      if (messageKey === 'error.export_limit_exceeded') {
        addToast('error', t('audit.export.limit_exceeded'));
      } else if (isQuotaExceeded) {
        addToast('error', t('audit.export.quota_exceeded'));
      } else {
        addToast('error', t('error.unknown.message'));
      }
    } finally {
      setIsExporting(null);
    }
  };

  const searchParams: Record<string, unknown> = {
    page,
    page_size: 10,
  };
  if (filters.start_date) searchParams.start_date = filters.start_date;
  if (filters.end_date) searchParams.end_date = filters.end_date;
  if (filters.action_type) searchParams.action_type = filters.action_type;
  if (filters.actor_identity) searchParams.actor_identity = filters.actor_identity;
  if (filters.outcome) searchParams.outcome = filters.outcome;
  if (filters.resource_type) searchParams.resource_type = filters.resource_type;

  const { data: searchData, isLoading: isSearchLoading, isError: isSearchError } = useQuery({
    queryKey: ['adminAuditEntries', searchParams],
    queryFn: () => searchAuditEntries(searchParams),
    placeholderData: (previousData) => previousData,
    enabled: canVerifyAudit,
  });

  const { data: retentionData, isLoading: isRetentionLoading, isError: isRetentionError } = useQuery({
    queryKey: ['adminAuditRetention'],
    queryFn: getAuditRetention,
    enabled: canVerifyAudit,
  });

  const handleVerify = () => {
    verifyMutation.mutate(undefined, {
      onSuccess: (data) => {
        if (data.verified) {
          addToast('success', t('admin.audit.verifySuccess'));
        } else {
          addToast('error', t('admin.audit.verifyFailed'));
        }
      },
      onError: () => {
        addToast('error', t('admin.audit.verifyFailed'));
      },
    });
  };

  const renderStatusDetails = () => {
    if (statusQuery.isLoading) {
      return (
        <div className="flex justify-center items-center py-12">
          <RefreshCw className="w-8 h-8 text-neon-cyan animate-spin" />
        </div>
      );
    }

    if (statusQuery.isError) {
      return (
        <div className="p-6 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 flex items-start gap-3">
          <AlertTriangle className="w-6 h-6 shrink-0 mt-0.5" />
          <div className="space-y-2">
            <h3 className="font-semibold text-white">{t('admin.audit.loadError')}</h3>
            <button
              onClick={() => statusQuery.refetch()}
              className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 text-white rounded-md hover:bg-gray-700 transition-colors text-sm font-medium cursor-pointer"
            >
              <RefreshCw className="w-4 h-4" />
              {t('query.timeout.cta')}
            </button>
          </div>
        </div>
      );
    }

    const data = statusQuery.data;
    if (!data) return null;

    const lastVerification = data.last_verification as unknown as LastVerification | undefined;

    return (
      <div className="space-y-6">
        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Total Log Entries Card */}
          <div className="p-6 bg-gray-900 border border-gray-800 rounded-xl space-y-2">
            <div className="text-gray-400 text-sm font-medium">{t('admin.audit.totalEntries')}</div>
            <div dir="ltr" className="text-3xl font-bold text-white font-mono">{data.total_entries}</div>
          </div>

          {/* Verification Status Card */}
          <div className="p-6 bg-gray-900 border border-gray-800 rounded-xl space-y-2">
            <div className="text-gray-400 text-sm font-medium">{t('admin.audit.lastVerification')}</div>
            <div>
              {!lastVerification ? (
                <span className="inline-flex items-center px-2.5 py-1.5 rounded-md text-sm font-medium bg-gray-800 text-gray-300">
                  {t('admin.audit.neverVerified')}
                </span>
              ) : lastVerification.verified ? (
                <div className="space-y-2">
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-sm font-medium bg-green-500/10 text-green-400 border border-green-500/20">
                    <CheckCircle2 className="w-4 h-4 text-green-500" />
                    {t('admin.audit.status.verified')}
                  </div>
                  <div className="text-xs text-gray-400 space-y-0.5">
                    <div>
                      {t('admin.audit.entriesChecked')}:{' '}
                      <span dir="ltr" className="text-white font-mono">{lastVerification.entries_checked}</span>
                    </div>
                    <div>
                      {t('admin.audit.verifiedAt')}:{' '}
                      <span dir="ltr" className="text-white">
                        {new Date(lastVerification.verified_at).toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-sm font-medium bg-red-500/10 text-red-400 border border-red-500/20">
                    <XCircle className="w-4 h-4 text-red-500" />
                    {t('admin.audit.status.broken')}
                  </div>
                  <div className="text-xs text-gray-400 space-y-0.5">
                    <div>
                      {t('admin.audit.firstBreakAt')}:{' '}
                      <span dir="ltr" className="text-red-400 font-bold font-mono">
                        {lastVerification.first_break_at}
                      </span>
                    </div>
                    <div>
                      {t('admin.audit.entriesChecked')}:{' '}
                      <span dir="ltr" className="text-white font-mono">{lastVerification.entries_checked}</span>
                    </div>
                    <div>
                      {t('admin.audit.verifiedAt')}:{' '}
                      <span dir="ltr" className="text-white">
                        {new Date(lastVerification.verified_at).toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Retention Status Card */}
          <div className="p-6 bg-gray-900 border border-gray-800 rounded-xl space-y-2">
            <div className="text-gray-400 text-sm font-medium">{t('audit.retention.title')}</div>
            {isRetentionLoading ? (
              <div
                className="flex justify-center py-2"
                role="status"
                aria-label={t('audit.retention.loading')}
              >
                <RefreshCw className="w-5 h-5 text-neon-cyan animate-spin" />
              </div>
            ) : isRetentionError ? (
              <div className="text-sm text-red-400">{t('admin.audit.loadError')}</div>
            ) : retentionData ? (
              <div className="text-xs text-gray-400 space-y-1">
                <div>
                  {t('audit.retention.period')}:{' '}
                  <span dir="ltr" className="text-white font-semibold font-mono">
                    {t('audit.retention.months', { count: retentionData.retention_months })}
                  </span>
                </div>
                <div>
                  {t('audit.retention.last_purge')}:{' '}
                  {retentionData.last_purge_at ? (
                    <span dir="ltr" className="text-white">
                      {new Date(retentionData.last_purge_at).toLocaleString()}
                    </span>
                  ) : (
                    <span className="text-white">{t('audit.retention.never')}</span>
                  )}
                </div>
                <div>
                  {t('audit.retention.purged_count')}:{' '}
                  <span dir="ltr" className="text-white font-mono">{retentionData.purged_count ?? 0}</span>
                </div>
              </div>
            ) : null}
          </div>
        </div>

        {/* Detailed Break Warning Panel if chain is broken */}
        {lastVerification && !lastVerification.verified && (
          <div className="p-6 bg-red-500/5 border border-red-500/20 rounded-xl space-y-4">
            <div className="flex gap-3">
              <AlertTriangle className="w-6 h-6 text-red-500 shrink-0 mt-0.5 animate-pulse" />
              <div className="space-y-1">
                <h3 className="text-lg font-semibold text-red-400">
                  {t('admin.audit.status.broken')}
                </h3>
                <p className="text-sm text-gray-300 leading-relaxed">
                  {t('admin.audit.status.brokenDesc')}
                </p>
              </div>
            </div>

            <div className="pt-2 border-t border-red-500/10 text-xs text-gray-400 leading-relaxed">
              <span className="font-semibold text-white block mb-1">
                {t('admin.audit.securityWarningTitle')}
              </span>
              {t('admin.audit.securityWarning')}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 relative">
      {/* Global Toast Container */}
      <div className="fixed top-4 start-4 end-4 z-50 flex flex-col gap-3 select-none pointer-events-none sm:top-6 sm:start-auto sm:end-6 sm:max-w-sm">
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

      <div className="flex flex-col items-stretch gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold text-text-primary flex items-center gap-2">
            <Shield className="w-6 h-6 shrink-0 text-neon-cyan" />
            {t('admin.audit.title')}
          </h1>
        </div>
        <div className="shrink-0">
          <button
            onClick={handleVerify}
            disabled={verifyMutation.isPending || statusQuery.isLoading}
            className="flex w-full items-center justify-center gap-2 px-4 py-2 bg-neon-cyan text-gray-900 rounded-md hover:bg-opacity-90 transition-colors font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed sm:w-auto"
          >
            {verifyMutation.isPending && <RefreshCw className="w-4 h-4 animate-spin" />}
            {verifyMutation.isPending ? t('admin.audit.verifying') : t('admin.audit.verifyButton')}
          </button>
        </div>
      </div>

      {renderStatusDetails()}

      {/* Persistent Search Logs Panel */}
      <div className="p-4 sm:p-6 bg-gray-900 border border-gray-800 rounded-xl space-y-6">
        <h2 className="text-xl font-semibold text-white flex items-center gap-2 border-b border-gray-800 pb-3">
          <Shield className="w-5 h-5 text-neon-cyan" />
          {t('audit.search.title')}
        </h2>

        {/* Search Form */}
        <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 gap-4 md:grid-cols-3 md:gap-6">
          {/* Date From */}
          <div className="flex flex-col gap-2">
            <label htmlFor="start_date" className="text-gray-400 text-sm font-medium">
              {t('audit.search.date_from')}
            </label>
            <input
              dir="ltr"
              type="date"
              id="start_date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="bg-gray-950 border border-gray-800 text-white rounded-md px-3 py-2 focus:outline-none focus:border-neon-cyan text-sm w-full"
            />
          </div>

          {/* Date To */}
          <div className="flex flex-col gap-2">
            <label htmlFor="end_date" className="text-gray-400 text-sm font-medium">
              {t('audit.search.date_to')}
            </label>
            <input
              dir="ltr"
              type="date"
              id="end_date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="bg-gray-950 border border-gray-800 text-white rounded-md px-3 py-2 focus:outline-none focus:border-neon-cyan text-sm w-full"
            />
          </div>

          {/* Action Type */}
          <div className="flex flex-col gap-2">
            <label htmlFor="action_type" className="text-gray-400 text-sm font-medium">
              {t('audit.search.action_type')}
            </label>
            <input
              dir="ltr"
              type="text"
              id="action_type"
              value={actionType}
              onChange={(e) => setActionType(e.target.value)}
              placeholder={t('audit.search.placeholder.action_type')}
              className="bg-gray-950 border border-gray-800 text-white rounded-md px-3 py-2 focus:outline-none focus:border-neon-cyan text-sm w-full placeholder:text-gray-600"
            />
          </div>

          {/* Actor */}
          <div className="flex flex-col gap-2">
            <label htmlFor="actor_identity" className="text-gray-400 text-sm font-medium">
              {t('audit.search.actor')}
            </label>
            <input
              dir="auto"
              type="text"
              id="actor_identity"
              value={actorIdentity}
              onChange={(e) => setActorIdentity(e.target.value)}
              placeholder={t('audit.search.placeholder.actor')}
              className="bg-gray-950 border border-gray-800 text-white rounded-md px-3 py-2 focus:outline-none focus:border-neon-cyan text-sm w-full placeholder:text-gray-600"
            />
          </div>

          {/* Outcome */}
          <div className="flex flex-col gap-2">
            <label htmlFor="outcome" className="text-gray-400 text-sm font-medium">
              {t('audit.search.outcome')}
            </label>
            <select
              id="outcome"
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
              className="bg-gray-950 border border-gray-800 text-white rounded-md px-3 py-2 focus:outline-none focus:border-neon-cyan text-sm w-full"
            >
              <option value="all">{t('audit.search.all_outcomes')}</option>
              <option value="success">{t('audit.search.outcome.success')}</option>
              <option value="failure">{t('audit.search.outcome.failure')}</option>
            </select>
          </div>

          {/* Resource Type */}
          <div className="flex flex-col gap-2">
            <label htmlFor="resource_type" className="text-gray-400 text-sm font-medium">
              {t('audit.search.resource_type')}
            </label>
            <input
              dir="ltr"
              type="text"
              id="resource_type"
              value={resourceType}
              onChange={(e) => setResourceType(e.target.value)}
              placeholder={t('audit.search.placeholder.resource_type')}
              className="bg-gray-950 border border-gray-800 text-white rounded-md px-3 py-2 focus:outline-none focus:border-neon-cyan text-sm w-full placeholder:text-gray-600"
            />
          </div>

          {/* Buttons */}
          <div
            className="mt-2 grid grid-cols-2 gap-3 md:col-span-3 sm:flex sm:flex-wrap sm:justify-end"
            role="group"
            aria-label={t('audit.search.actions')}
          >
            <button
              type="button"
              onClick={handleReset}
              className="min-w-0 px-3 py-2 border border-gray-800 text-gray-300 rounded-md hover:bg-gray-800 transition-colors text-sm font-medium cursor-pointer sm:px-4"
            >
              {t('audit.search.reset')}
            </button>
            <button
              type="button"
              onClick={() => handleExport('csv')}
              disabled={isExporting !== null}
              className="min-w-0 px-3 py-2 border border-gray-800 text-gray-300 rounded-md hover:bg-gray-800 transition-colors text-sm font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 sm:px-4"
            >
              {isExporting === 'csv' ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Download className="w-4 h-4" />
              )}
              {t('audit.export.csv')}
            </button>
            <button
              type="button"
              onClick={() => handleExport('json')}
              disabled={isExporting !== null}
              className="min-w-0 px-3 py-2 border border-gray-800 text-gray-300 rounded-md hover:bg-gray-800 transition-colors text-sm font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 sm:px-4"
            >
              {isExporting === 'json' ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Download className="w-4 h-4" />
              )}
              {t('audit.export.json')}
            </button>
            <button
              type="submit"
              className="min-w-0 px-3 py-2 bg-neon-cyan text-gray-900 rounded-md hover:bg-opacity-90 transition-colors text-sm font-medium cursor-pointer sm:px-4"
            >
              {t('audit.search.submit')}
            </button>
          </div>
        </form>

        {/* Results Table */}
        <div className="border border-gray-800 rounded-xl overflow-hidden bg-gray-950">
          {isSearchLoading ? (
            <div className="flex justify-center items-center py-12">
              <RefreshCw className="w-8 h-8 text-neon-cyan animate-spin" />
            </div>
          ) : isSearchError ? (
            <div className="p-6 text-center text-red-400">{t('admin.audit.loadError')}</div>
          ) : !searchData || searchData.entries.length === 0 ? (
            <div className="p-6 text-center text-gray-500">{t('admin.audit.emptyState')}</div>
          ) : (
            <div>
              <table
                className="block w-full text-sm text-start lg:table"
                aria-label={t('audit.search.results')}
              >
                <thead className="sr-only lg:not-sr-only lg:table-header-group">
                  <tr className="border-b border-gray-800 bg-gray-900/50">
                    <th className="px-4 py-3 text-start text-xs font-semibold text-gray-400 uppercase tracking-wider">#</th>
                    <th className="px-4 py-3 text-start text-xs font-semibold text-gray-400 uppercase tracking-wider">{t('audit.search.timestamp')}</th>
                    <th className="px-4 py-3 text-start text-xs font-semibold text-gray-400 uppercase tracking-wider">{t('audit.search.actor')}</th>
                    <th className="px-4 py-3 text-start text-xs font-semibold text-gray-400 uppercase tracking-wider">{t('audit.search.action_type')}</th>
                    <th className="px-4 py-3 text-start text-xs font-semibold text-gray-400 uppercase tracking-wider">{t('audit.search.outcome')}</th>
                    <th className="px-4 py-3 text-start text-xs font-semibold text-gray-400 uppercase tracking-wider">{t('audit.search.resource_type')}</th>
                  </tr>
                </thead>
                <tbody className="grid gap-3 p-3 lg:table-row-group lg:p-0">
                  {searchData.entries.map((entry) => (
                    <tr
                      key={entry.sequence_number}
                      className="grid grid-cols-1 gap-3 rounded-lg border border-gray-800 bg-gray-900/40 p-4 transition-colors hover:bg-gray-900/60 sm:grid-cols-2 lg:table-row lg:rounded-none lg:border-0 lg:bg-transparent lg:p-0 lg:hover:bg-gray-900/30"
                    >
                      <td
                        data-label="#"
                        className={RESPONSIVE_AUDIT_CELL_CLASS}
                      >
                        <span dir="ltr" className="min-w-0 text-end text-white font-mono lg:text-start">
                          {entry.sequence_number}
                        </span>
                      </td>
                      <td
                        data-label={t('audit.search.timestamp')}
                        className={RESPONSIVE_AUDIT_CELL_CLASS}
                      >
                        <span
                          dir="ltr"
                          className="min-w-0 break-words text-end text-gray-300 font-mono text-xs lg:text-start lg:whitespace-nowrap"
                        >
                          {new Date(entry.timestamp).toLocaleString()}
                        </span>
                      </td>
                      <td
                        data-label={t('audit.search.actor')}
                        className={RESPONSIVE_AUDIT_CELL_CLASS}
                      >
                        <span dir="auto" className="min-w-0 break-words text-end text-gray-300 lg:text-start">
                          {entry.actor_identity || '-'}
                        </span>
                      </td>
                      <td
                        data-label={t('audit.search.action_type')}
                        className={RESPONSIVE_AUDIT_CELL_CLASS}
                      >
                        <span
                          dir="ltr"
                          className="min-w-0 break-all text-end text-gray-300 font-mono text-xs lg:text-start lg:whitespace-nowrap"
                        >
                          {entry.action_type}
                        </span>
                      </td>
                      <td
                        data-label={t('audit.search.outcome')}
                        className={RESPONSIVE_AUDIT_CELL_CLASS}
                      >
                        <span
                          dir="ltr"
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${
                            entry.outcome === 'success'
                              ? 'bg-green-500/10 border-green-500/20 text-green-400'
                              : 'bg-red-500/10 border-red-500/20 text-red-400'
                          }`}
                        >
                          {entry.outcome}
                        </span>
                      </td>
                      <td
                        data-label={t('audit.search.resource_type')}
                        className={RESPONSIVE_AUDIT_CELL_CLASS}
                      >
                        <span
                          dir="ltr"
                          className="min-w-0 break-all text-end text-gray-300 font-mono text-xs lg:text-start"
                        >
                          {entry.resource_type || '-'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Pagination Controls */}
              {searchData.pagination.total_pages > 1 && (
                <div className="flex flex-col gap-3 px-4 py-3 border-t border-gray-800 bg-gray-900/20 sm:flex-row sm:items-center sm:justify-between">
                  <div className="text-gray-400 text-xs">
                    {t('audit.search.page_info', {
                      page: searchData.pagination.page,
                      totalPages: searchData.pagination.total_pages,
                    })}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                      disabled={page === 1}
                      className="px-3 py-1.5 border border-gray-800 text-gray-300 rounded hover:bg-gray-800 transition-colors text-xs font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {t('audit.search.prev_page')}
                    </button>
                    <button
                      onClick={() => setPage((prev) => Math.min(searchData.pagination.total_pages, prev + 1))}
                      disabled={page === searchData.pagination.total_pages}
                      className="px-3 py-1.5 border border-gray-800 text-gray-300 rounded hover:bg-gray-800 transition-colors text-xs font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {t('audit.search.next_page')}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
