import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAdminAudit } from '../hooks/useAdminAudit';
import { Shield, CheckCircle2, XCircle, AlertTriangle, X, RefreshCw } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { searchAuditEntries } from '../api/audit';

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

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    setFilters({
      start_date: startDate ? `${startDate}T00:00:00Z` : '',
      end_date: endDate ? `${endDate}T23:59:59Z` : '',
      action_type: actionType,
      actor_identity: actorIdentity,
      outcome: outcome === 'all' ? '' : outcome,
      resource_type: resourceType,
    });
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

  const searchParams: any = {
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
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Total Log Entries Card */}
          <div className="p-6 bg-gray-900 border border-gray-800 rounded-xl space-y-2">
            <div className="text-gray-400 text-sm font-medium">{t('admin.audit.totalEntries')}</div>
            <div className="text-3xl font-bold text-white font-mono">{data.total_entries}</div>
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
                      <span className="text-white font-mono">{lastVerification.entries_checked}</span>
                    </div>
                    <div>
                      {t('admin.audit.verifiedAt')}:{' '}
                      <span className="text-white">
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
                      <span className="text-red-400 font-bold font-mono">
                        {lastVerification.first_break_at}
                      </span>
                    </div>
                    <div>
                      {t('admin.audit.entriesChecked')}:{' '}
                      <span className="text-white font-mono">{lastVerification.entries_checked}</span>
                    </div>
                    <div>
                      {t('admin.audit.verifiedAt')}:{' '}
                      <span className="text-white">
                        {new Date(lastVerification.verified_at).toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
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
    <div className="p-6 max-w-7xl mx-auto space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500 relative">
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

      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold text-text-primary flex items-center gap-2">
            <Shield className="w-6 h-6 text-neon-cyan" />
            {t('admin.audit.title')}
          </h1>
        </div>
        <div>
          <button
            onClick={handleVerify}
            disabled={verifyMutation.isPending || statusQuery.isLoading}
            className="flex items-center gap-2 px-4 py-2 bg-neon-cyan text-gray-900 rounded-md hover:bg-opacity-90 transition-colors font-medium cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {verifyMutation.isPending && <RefreshCw className="w-4 h-4 animate-spin" />}
            {verifyMutation.isPending ? t('admin.audit.verifying') : t('admin.audit.verifyButton')}
          </button>
        </div>
      </div>

      {renderStatusDetails()}

      {/* Persistent Search Logs Panel */}
      <div className="p-6 bg-gray-900 border border-gray-800 rounded-xl space-y-6">
        <h2 className="text-xl font-semibold text-white flex items-center gap-2 border-b border-gray-800 pb-3">
          <Shield className="w-5 h-5 text-neon-cyan" />
          {t('audit.search.title')}
        </h2>

        {/* Search Form */}
        <form onSubmit={handleSearchSubmit} className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Date From */}
          <div className="flex flex-col gap-2">
            <label htmlFor="start_date" className="text-gray-400 text-sm font-medium">
              {t('audit.search.date_from')}
            </label>
            <input
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
              type="text"
              id="action_type"
              value={actionType}
              onChange={(e) => setActionType(e.target.value)}
              placeholder="e.g. query.submit"
              className="bg-gray-950 border border-gray-800 text-white rounded-md px-3 py-2 focus:outline-none focus:border-neon-cyan text-sm w-full placeholder:text-gray-600"
            />
          </div>

          {/* Actor */}
          <div className="flex flex-col gap-2">
            <label htmlFor="actor_identity" className="text-gray-400 text-sm font-medium">
              {t('audit.search.actor')}
            </label>
            <input
              type="text"
              id="actor_identity"
              value={actorIdentity}
              onChange={(e) => setActorIdentity(e.target.value)}
              placeholder="e.g. user@example.com"
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
              type="text"
              id="resource_type"
              value={resourceType}
              onChange={(e) => setResourceType(e.target.value)}
              placeholder="e.g. database"
              className="bg-gray-950 border border-gray-800 text-white rounded-md px-3 py-2 focus:outline-none focus:border-neon-cyan text-sm w-full placeholder:text-gray-600"
            />
          </div>

          {/* Buttons */}
          <div className="md:col-span-3 flex justify-end gap-3 mt-2">
            <button
              type="button"
              onClick={handleReset}
              className="px-4 py-2 border border-gray-800 text-gray-300 rounded-md hover:bg-gray-800 transition-colors text-sm font-medium cursor-pointer"
            >
              {t('audit.search.reset')}
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-neon-cyan text-gray-900 rounded-md hover:bg-opacity-90 transition-colors text-sm font-medium cursor-pointer"
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
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-start">
                <thead>
                  <tr className="border-b border-gray-800 bg-gray-900/50">
                    <th className="px-4 py-3 text-start text-xs font-semibold text-gray-400 uppercase tracking-wider">#</th>
                    <th className="px-4 py-3 text-start text-xs font-semibold text-gray-400 uppercase tracking-wider">{t('audit.search.timestamp')}</th>
                    <th className="px-4 py-3 text-start text-xs font-semibold text-gray-400 uppercase tracking-wider">{t('audit.search.actor')}</th>
                    <th className="px-4 py-3 text-start text-xs font-semibold text-gray-400 uppercase tracking-wider">{t('audit.search.action_type')}</th>
                    <th className="px-4 py-3 text-start text-xs font-semibold text-gray-400 uppercase tracking-wider">{t('audit.search.outcome')}</th>
                    <th className="px-4 py-3 text-start text-xs font-semibold text-gray-400 uppercase tracking-wider">{t('audit.search.resource_type')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/50">
                  {searchData.entries.map((entry) => (
                    <tr key={entry.sequence_number} className="hover:bg-gray-900/30 transition-colors">
                      <td className="px-4 py-3 text-start text-white font-mono">{entry.sequence_number}</td>
                      <td className="px-4 py-3 text-start text-gray-300 font-mono text-xs whitespace-nowrap">
                        {new Date(entry.timestamp).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-start text-gray-300 whitespace-nowrap">{entry.actor_identity || '-'}</td>
                      <td className="px-4 py-3 text-start text-gray-300 whitespace-nowrap font-mono text-xs">{entry.action_type}</td>
                      <td className="px-4 py-3 text-start">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${
                            entry.outcome === 'success'
                              ? 'bg-green-500/10 border-green-500/20 text-green-400'
                              : 'bg-red-500/10 border-red-500/20 text-red-400'
                          }`}
                        >
                          {entry.outcome}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-start text-gray-300 font-mono text-xs">{entry.resource_type || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Pagination Controls */}
              {searchData.pagination.total_pages > 1 && (
                <div className="flex justify-between items-center px-4 py-3 border-t border-gray-800 bg-gray-900/20">
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
