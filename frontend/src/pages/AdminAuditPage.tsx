import React, { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAdminAudit } from '../hooks/useAdminAudit';
import { Shield, CheckCircle2, XCircle, AlertTriangle, X, RefreshCw, Download } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createAuditFilterContext,
  searchAuditEntries,
  exportAuditEntries,
  getAuditRetention,
  AuditDownloadError,
  type AuditExportRequest,
  type AuditFilterContextRequest,
  type AuditFilterContextResponse,
  type AuditSearchParams,
  type AuditSearchResponse,
} from '../api/audit';
import {
  AUDIT_EXPORT_TIMEOUT_MS,
  ORDINARY_REQUEST_TIMEOUT_MS,
  RequestScope,
  isAbortFailure,
  isClientDeadlineError,
} from '../api/requestScope';
import { PERMISSIONS } from '../auth/permissions';
import { requirePermission, usePermission } from '../hooks/usePermission';
import { ClientQueryState } from '../components/common/ClientQueryState';
import { formatDateTime } from '../i18n/format';

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

/**
 * CHUNK-22 / IS-GAP-034 — the filters that were successfully applied to a
 * displayed result set. Draft form inputs and requested searches are separate
 * states; only a settled response carries its own applied filters so results,
 * the visible summary and every export request stay bound to one dataset.
 */
type AuditFilterField = AuditFilterContextResponse['applied_fields'][number];

interface AuditFilterAuthority {
  filterContext: string | null;
  appliedFields: AuditFilterField[];
}

const UNFILTERED_AUTHORITY: AuditFilterAuthority = {
  filterContext: null,
  appliedFields: [],
};

const AUDIT_SEARCH_QUERY_KEY = 'adminAuditEntries';

interface AuditSearchSnapshot {
  filterContext: string | null;
  appliedFields: AuditFilterField[];
  response: AuditSearchResponse;
}

function contextToSearchParams(
  filterContext: string | null,
  page: number
): AuditSearchParams {
  return {
    filter_context: filterContext ?? undefined,
    page,
    page_size: 10,
  };
}

const APPLIED_FILTER_FIELD_LABELS: ReadonlyArray<
  readonly [AuditFilterField, 'audit.search.date_from' | 'audit.search.date_to' | 'audit.search.action_type' | 'audit.search.actor' | 'audit.search.outcome' | 'audit.search.resource_type']
> = [
  ['start_date', 'audit.search.date_from'],
  ['end_date', 'audit.search.date_to'],
  ['action_type', 'audit.search.action_type'],
  ['actor_identity', 'audit.search.actor'],
  ['outcome', 'audit.search.outcome'],
  ['resource_type', 'audit.search.resource_type'],
];

const RESPONSIVE_AUDIT_CELL_CLASS =
  'flex min-w-0 items-start justify-between gap-4 before:shrink-0 before:text-xs before:font-semibold before:uppercase before:tracking-wider before:text-gray-500 before:content-[attr(data-label)] lg:table-cell lg:px-4 lg:py-3 lg:before:hidden';

export const AdminAuditPage: React.FC = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastTimersRef = useRef(new Set<ReturnType<typeof setTimeout>>());
  const exportScopeRef = useRef<RequestScope | null>(null);
  const contextScopeRef = useRef<RequestScope | null>(null);
  const contextRequestGenerationRef = useRef(0);
  const mountedRef = useRef(true);

  useEffect(() => {
    const timers = toastTimersRef.current;
    mountedRef.current = true;
    return () => {
      // Navigation/unmount cleanup: abort an in-flight export and clear all
      // pending toast timers exactly once.
      mountedRef.current = false;
      exportScopeRef.current?.abort();
      exportScopeRef.current?.dispose();
      exportScopeRef.current = null;
      contextRequestGenerationRef.current += 1;
      contextScopeRef.current?.abort();
      contextScopeRef.current?.dispose();
      contextScopeRef.current = null;
      void queryClient.cancelQueries({ queryKey: [AUDIT_SEARCH_QUERY_KEY] });
      queryClient.removeQueries({ queryKey: [AUDIT_SEARCH_QUERY_KEY] });
      for (const timer of timers) clearTimeout(timer);
      timers.clear();
    };
  }, [queryClient]);

  const addToast = (type: 'success' | 'error', message: string) => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((prev) => [...prev, { id, type, message }]);
    const timer = setTimeout(() => {
      toastTimersRef.current.delete(timer);
      if (mountedRef.current) {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }
    }, 5000);
    toastTimersRef.current.add(timer);
  };

  const { statusQuery, verifyMutation } = useAdminAudit();
  const canVerifyAudit = usePermission(PERMISSIONS.ADMIN_AUDIT_VERIFY);

  const [isExporting, setIsExporting] = useState<'csv' | 'json' | null>(null);

  // Search Filter Form States (draft inputs — never authoritative for export).
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [actionType, setActionType] = useState('');
  const [actorIdentity, setActorIdentity] = useState('');
  const [outcome, setOutcome] = useState('all');
  const [resourceType, setResourceType] = useState('');
  const [page, setPage] = useState(1);
  const [requestedAuthority, setRequestedAuthority] = useState<AuditFilterAuthority>(UNFILTERED_AUTHORITY);
  const [isCreatingContext, setIsCreatingContext] = useState(false);
  // Last displayed snapshot kept so failed searches keep showing the prior
  // applied dataset instead of an empty table.
  const [retainedSnapshot, setRetainedSnapshot] = useState<AuditSearchSnapshot>();

  const buildFiltersFromInputs = (): AuditFilterContextRequest => ({
    start_date: startDate ? `${startDate}T00:00:00Z` : undefined,
    end_date: endDate ? `${endDate}T23:59:59Z` : undefined,
    action_type: (actionType || undefined) as AuditFilterContextRequest['action_type'],
    actor_identity: actorIdentity || undefined,
    outcome: (outcome === 'all' ? undefined : outcome) as AuditFilterContextRequest['outcome'],
    resource_type: resourceType || undefined,
  });

  const clearDraftFilters = () => {
    setStartDate('');
    setEndDate('');
    setActionType('');
    setActorIdentity('');
    setOutcome('all');
    setResourceType('');
  };

  const cancelExport = () => {
    exportScopeRef.current?.abort();
  };

  const buildExportRequest = (
    format: 'csv' | 'json',
    filterContext: string | null
  ): AuditExportRequest => ({
    format,
    filter_context: filterContext ?? undefined,
  });

  const handleExport = async (format: 'csv' | 'json') => {
    requirePermission(canVerifyAudit, PERMISSIONS.ADMIN_AUDIT_VERIFY);
    if (exportScopeRef.current) return;
    setIsExporting(format);
    // One owned scope per export with the documented longer audit deadline.
    const scope = new RequestScope({ timeoutMs: AUDIT_EXPORT_TIMEOUT_MS });
    exportScopeRef.current = scope;
    try {
      const download = await exportAuditEntries(
        buildExportRequest(format, exportFilterContext),
        scope.signal
      );
      if (scope.aborted || !mountedRef.current) return;

      let url: string | null = null;
      let link: HTMLAnchorElement | null = null;
      try {
        url = window.URL.createObjectURL(download.blob);
        link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', download.filename);
        document.body.appendChild(link);
        link.click();
      } finally {
        if (link && link.parentNode) {
          link.parentNode.removeChild(link);
        }
        if (url !== null) {
          window.URL.revokeObjectURL(url);
        }
      }
    } catch (err: unknown) {
      if (!mountedRef.current || isAbortFailure(err)) {
        if (mountedRef.current) {
          const timedOut = isClientDeadlineError(err) || scope.reason === 'deadline';
          addToast('error', timedOut ? t('audit.export.timeout') : t('audit.export.canceled'));
        }
        return;
      }
      if (
        err instanceof AuditDownloadError ||
        (err as Record<string, unknown> | undefined)?.name === 'AuditDownloadError'
      ) {
        addToast('error', t('audit.export.failed'));
        return;
      }
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
      scope.dispose();
      if (exportScopeRef.current === scope) {
        exportScopeRef.current = null;
      }
      if (mountedRef.current) {
        setIsExporting(null);
      }
    }
  };

  const searchQuery = useQuery({
    queryKey: [AUDIT_SEARCH_QUERY_KEY, requestedAuthority.filterContext, page],
    queryFn: async ({ signal }): Promise<AuditSearchSnapshot> => {
      const response = await searchAuditEntries(
        contextToSearchParams(requestedAuthority.filterContext, page),
        signal
      );
      return {
        filterContext: requestedAuthority.filterContext,
        appliedFields: requestedAuthority.appliedFields,
        response,
      };
    },
    placeholderData: (previousData) => previousData,
    enabled: canVerifyAudit,
    gcTime: 0,
  });

  const retentionQuery = useQuery({
    queryKey: ['adminAuditRetention'],
    queryFn: ({ signal }) => getAuditRetention(signal),
    enabled: canVerifyAudit,
  });

  // The displayed dataset: a settled or placeholder response for the current
  // request, otherwise the retained prior dataset after a failed search.
  const snapshot: AuditSearchSnapshot | undefined = searchQuery.data ?? retainedSnapshot;
  const searchData = snapshot?.response;
  const searchPagination = searchData?.pagination;
  const retentionData = retentionQuery.data;

  const retainDisplayedSnapshot = () => {
    setRetainedSnapshot(searchQuery.data ?? retainedSnapshot);
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (contextScopeRef.current) return;
    retainDisplayedSnapshot();
    setPage(1);
    const requestGeneration = contextRequestGenerationRef.current + 1;
    contextRequestGenerationRef.current = requestGeneration;
    const scope = new RequestScope({ timeoutMs: ORDINARY_REQUEST_TIMEOUT_MS });
    contextScopeRef.current = scope;
    setIsCreatingContext(true);
    const pendingContext = createAuditFilterContext(buildFiltersFromInputs(), scope.signal);
    clearDraftFilters();
    void pendingContext
      .then((context) => {
        if (!mountedRef.current || scope.aborted || contextRequestGenerationRef.current !== requestGeneration) return;
        setRequestedAuthority({
          filterContext: context.filter_context,
          appliedFields: context.applied_fields,
        });
      })
      .catch((error: unknown) => {
        if (!mountedRef.current || (isAbortFailure(error) && scope.reason !== 'deadline')) return;
        addToast('error', t('audit.search.context_error'));
      })
      .finally(() => {
        scope.dispose();
        if (contextScopeRef.current === scope) contextScopeRef.current = null;
        if (mountedRef.current && contextRequestGenerationRef.current === requestGeneration) {
          setIsCreatingContext(false);
        }
      });
  };

  const handleReset = () => {
    contextRequestGenerationRef.current += 1;
    contextScopeRef.current?.abort();
    contextScopeRef.current?.dispose();
    contextScopeRef.current = null;
    setIsCreatingContext(false);
    retainDisplayedSnapshot();
    clearDraftFilters();
    setPage(1);
    setRequestedAuthority(UNFILTERED_AUTHORITY);
  };

  const hasUnappliedChanges = Boolean(
    searchData !== undefined &&
      (startDate || endDate || actionType || actorIdentity || outcome !== 'all' || resourceType)
  );
  const exportFilterContext = snapshot?.filterContext ?? requestedAuthority.filterContext;
  const appliedFields = snapshot?.appliedFields ?? [];
  const appliedFilterEntries = APPLIED_FILTER_FIELD_LABELS
    .filter(([field]) => appliedFields.includes(field))
    .map(([, labelKey]) => labelKey);

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

    if (statusQuery.isError && statusQuery.data === undefined) {
      return (
        <ClientQueryState query={statusQuery} fallbackErrorKey="admin.audit.loadError" />
      );
    }

    const data = statusQuery.data;
    if (!data) return null;

    const lastVerification = data.last_verification as unknown as LastVerification | undefined;

    return (
      <div className="space-y-6">
        <ClientQueryState query={statusQuery} fallbackErrorKey="admin.audit.loadError" />
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
                        {formatDateTime(lastVerification.verified_at)}
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
                        {formatDateTime(lastVerification.verified_at)}
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
            {retentionQuery.isLoading ? (
              <div
                className="flex justify-center py-2"
                role="status"
                aria-label={t('audit.retention.loading')}
              >
                <RefreshCw className="w-5 h-5 text-neon-cyan animate-spin" />
              </div>
            ) : retentionQuery.isError && retentionData === undefined ? (
              <ClientQueryState
                query={retentionQuery}
                fallbackErrorKey="admin.audit.loadError"
              />
            ) : retentionData ? (
              <div className="space-y-2 text-xs text-gray-400">
                <ClientQueryState
                  query={retentionQuery}
                  fallbackErrorKey="admin.audit.loadError"
                />
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
                      {formatDateTime(retentionData.last_purge_at)}
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
            {isExporting !== null && (
              <button
                type="button"
                onClick={cancelExport}
                data-testid="audit-export-cancel"
                aria-label={t('audit.export.cancel')}
                className="min-w-0 px-3 py-2 border border-red-500/30 text-red-300 rounded-md hover:bg-red-500/10 transition-colors text-sm font-medium cursor-pointer sm:px-4"
              >
                <span className="flex items-center justify-center gap-2">
                  <XCircle className="w-4 h-4" aria-hidden="true" />
                  {t('audit.export.cancel')}
                </span>
              </button>
            )}
            <button
              type="submit"
              disabled={isCreatingContext}
              className="min-w-0 px-3 py-2 bg-neon-cyan text-gray-900 rounded-md hover:bg-opacity-90 transition-colors text-sm font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed sm:px-4"
            >
              {isCreatingContext ? t('audit.search.creating_context') : t('audit.search.submit')}
            </button>
          </div>
        </form>

        {/* Applied filter summary — always describes the displayed dataset (CHUNK-22). */}
        <div className="space-y-2">
          <div
            data-testid="audit-applied-filters"
            className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-400"
          >
            <span className="font-semibold text-gray-300">{t('audit.search.applied_filters')}:</span>
            {appliedFilterEntries.length === 0 ? (
              <span>{t('audit.search.all_entries')}</span>
            ) : (
              appliedFilterEntries.map((labelKey) => (
                <span
                  key={labelKey}
                  className="inline-flex min-w-0 max-w-full items-center gap-1 rounded border border-gray-800 bg-gray-950 px-2 py-0.5"
                >
                  <span className="shrink-0 text-gray-400">{t(labelKey)}:</span>
                  <span className="text-gray-200">{t('audit.search.applied')}</span>
                </span>
              ))
            )}
          </div>
          {hasUnappliedChanges && (
            <p
              data-testid="audit-draft-filters-notice"
              aria-live="polite"
              className="text-xs leading-relaxed text-amber-300"
            >
              {t('audit.export.draft_notice')}
            </p>
          )}
        </div>

        {/* Results Table */}
        <div className="border border-gray-800 rounded-xl overflow-hidden bg-gray-950">
          {searchQuery.isLoading ? (
            <div className="flex justify-center items-center py-12">
              <RefreshCw className="w-8 h-8 text-neon-cyan animate-spin" />
            </div>
          ) : searchQuery.isError && searchData === undefined ? (
            <ClientQueryState query={searchQuery} fallbackErrorKey="admin.audit.loadError" />
          ) : (
            <div>
              <div className="p-4">
                <ClientQueryState
                  query={searchQuery}
                  fallbackErrorKey="admin.audit.loadError"
                  hasData={searchData !== undefined}
                  isPartial={Boolean(
                    searchData &&
                      searchData.pagination.page * searchData.pagination.page_size <
                        searchData.pagination.total_entries
                  )}
                />
              </div>
              {!searchData || searchData.entries.length === 0 ? (
                <div className="p-6 text-center text-gray-500">{t('admin.audit.emptyState')}</div>
              ) : <table
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
                          {formatDateTime(entry.timestamp)}
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
              </table>}

              {/* Pagination Controls */}
              {searchPagination && searchPagination.total_pages > 1 && (
                <div className="flex flex-col gap-3 px-4 py-3 border-t border-gray-800 bg-gray-900/20 sm:flex-row sm:items-center sm:justify-between">
                  <div className="text-gray-400 text-xs">
                    {t('audit.search.page_info', {
                      page: searchPagination.page,
                      totalPages: searchPagination.total_pages,
                    })}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        retainDisplayedSnapshot();
                        setPage((prev) => Math.max(1, prev - 1));
                      }}
                      disabled={page === 1}
                      className="px-3 py-1.5 border border-gray-800 text-gray-300 rounded hover:bg-gray-800 transition-colors text-xs font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {t('audit.search.prev_page')}
                    </button>
                    <button
                      onClick={() => {
                        retainDisplayedSnapshot();
                        setPage((prev) =>
                          Math.min(searchPagination.total_pages, prev + 1)
                        );
                      }}
                      disabled={page === searchPagination.total_pages}
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
