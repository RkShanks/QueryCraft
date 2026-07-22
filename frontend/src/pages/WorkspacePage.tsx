import React, { useState, useCallback, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { useUIStore } from '../stores/uiStore';
import { useSessionDetail } from '../hooks/useSessions';
import { useQuerySubmit } from '../hooks/useQuerySubmit';
import { UserBubble } from '../components/chat/UserBubble';
import { AssistantResponseCard } from '../components/chat/AssistantResponseCard';
import { PromptInput } from '../components/chat/PromptInput';
import { MessageSquare } from '../components/icons';
import { deleteHistoryEntry, listUserConnections } from '../api/generated/sdk.gen';
import type { QueryResult, RefinePrompt, EvaluatorRejection, AttemptSummary, UserConnectionResponse } from '../api/generated/types.gen';
import { useQuery } from '@tanstack/react-query';
import { useConnectionSelection } from '../hooks/useConnectionSelection';
import { ConnectionErrorCard } from '../components/chat/ConnectionErrorCard';
import type { ConnectionErrorKind } from '../components/chat/ConnectionErrorCard';
import { EvaluatorRejectionBanner } from '../components/query/EvaluatorRejectionBanner';
import { QuotaExceededBanner } from '../components/query/QuotaExceededBanner';
import { HostileInputBlockedBanner } from '../components/query/HostileInputBlockedBanner';
import './WorkspacePage.css';

interface ConversationTurn {
  id: string;
  question: string;
  sql?: string;
  result?: QueryResult;
  refinePrompt?: RefinePrompt;
  evaluatorRejection?: EvaluatorRejection;
  isLoading?: boolean;
  savedQueryId?: string;
  attemptId?: string;
  connectionName?: string;
  databaseType?: string;
  connectionError?: ConnectionErrorKind;
  quotaExceeded?: { resetAt?: string };
  hostileInputBlocked?: boolean;
}

function buildHistoryTurn(a: AttemptSummary, connections: UserConnectionResponse[]): ConversationTurn {
  const turn: ConversationTurn = {
    id: a.id,
    question: a.question_text,
    sql: a.generated_sql,
    savedQueryId: a.id,
  };
  if (a.database_connection_name && a.database_type) {
    turn.connectionName = a.database_connection_name;
    turn.databaseType = a.database_type;
  } else if (a.database_connection_id) {
    const meta = getConnectionMeta(a.database_connection_id, connections);
    turn.connectionName = meta.name;
    turn.databaseType = meta.type;
  }
  if (a.result_columns && a.result_rows) {
    turn.result = {
      kind: 'result',
      attempt_id: a.id,
      session_id: undefined,
      question: a.question_text,
      generated_sql: a.generated_sql,
      columns: a.result_columns,
      rows: a.result_rows,
      row_count: a.result_row_count ?? 0,
      attempt_number: 1,
      is_last_auto_retry: false,
      accepted_query_id: a.id,
    } as QueryResult;
  }
  return turn;
}

function getConnectionMeta(
  connectionId: string | null,
  connections: UserConnectionResponse[]
): { name?: string; type?: string } {
  if (!connectionId) return {};
  const conn = connections.find((c) => c.id === connectionId);
  if (!conn) return {};
  return { name: conn.display_name, type: conn.database_type };
}

function mapApiErrorToConnectionErrorKind(err: Record<string, unknown>): ConnectionErrorKind | null {
  const code = (err.error as string) || (err.detail as Record<string, unknown>)?.error as string;
  if (!code) return null;
  switch (code) {
    case 'connection_disabled':
      return 'disabled';
    case 'connection_unhealthy':
      return 'unhealthy';
    case 'connection_no_schema':
      return 'noSchema';
    case 'no_database_available':
      return 'noConnections';
    case 'query_execution_failed':
      return 'queryExecutionFailed';
    case 'timeout':
      return 'timeout';
    default:
      return null;
  }
}

function mapEvaluatorRejection(
  rejection: EvaluatorRejection
): { violations: Array<{ type: string; detail?: string }> } {
  const typeMap: Record<string, string> = {
    read_only: 'read_only',
    ReadOnly: 'read_only',
    single_statement: 'single_statement',
    SingleStatement: 'single_statement',
    schema_validation: 'schema_validation',
    SchemaValidation: 'schema_validation',
    unsafe_pattern: 'unsafe_pattern',
    UnsafePattern: 'unsafe_pattern',
  };

  return {
    violations: rejection.violations.map((v) => {
      const type = typeMap[v.rule] || v.rule;
      let detail: string | undefined;
      if (type === 'schema_validation') {
        detail = (v.message_params?.table || v.message_params?.column || v.message_params?.identifier) as string | undefined;
      } else if (type === 'unsafe_pattern') {
        detail = (v.message_params?.pattern || v.message_params?.name) as string | undefined;
      } else if (type === 'syntax') {
        detail = (v.message_params?.details || v.message_params?.error) as string | undefined;
      }
      return { type, detail };
    }),
  };
}

export const WorkspacePage: React.FC = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const activeSessionId = useUIStore((state) => state.activeSessionId);
  const { data: sessionDetail, isLoading } = useSessionDetail(activeSessionId ?? '');
  const querySubmit = useQuerySubmit();

  const [alert, setAlert] = useState<{
    id: string;
    title: string;
    description: string;
    variant: 'default' | 'destructive' | 'success';
  } | null>(null);

  const showAlert = useCallback((
    title: string,
    description: string,
    variant: 'default' | 'destructive' | 'success' = 'default'
  ) => {
    const id = Math.random().toString(36).substring(2, 9);
    setAlert({ id, title, description, variant });
    setTimeout(() => {
      setAlert((prev) => (prev?.id === id ? null : prev));
    }, 5000);
  }, []);

  // Fetch available connections for T-460
  const { data: userConnectionsResponse } = useQuery({
    queryKey: ['userConnections'],
    queryFn: () => listUserConnections({ throwOnError: true }).then((res) => res.data),
  });
  const availableConnections = React.useMemo(
    () => userConnectionsResponse?.connections ?? [],
    [userConnectionsResponse]
  );

  const {
    selectedConnectionId,
    setSelectedConnectionId,
  } = useConnectionSelection({
    sessionId: activeSessionId,
    initialConnectionId: sessionDetail?.connection_id ?? null,
    availableConnections,
  });

  const [searchParams, setSearchParams] = useSearchParams();
  const [loadedQuestion, setLoadedQuestion] = useState('');

  const urlQuestion = searchParams.get('question');
  const urlConnectionId = searchParams.get('connectionId');

  useEffect(() => {
    if (urlQuestion || urlConnectionId) {
      if (urlConnectionId && urlConnectionId !== selectedConnectionId) {
        setSelectedConnectionId(urlConnectionId);
      }
      if (urlQuestion) {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setLoadedQuestion(urlQuestion);
      }
      setSearchParams({}, { replace: true });
    }
  }, [urlQuestion, urlConnectionId, selectedConnectionId, setSelectedConnectionId, setSearchParams]);

  const [localTurns, setLocalTurns] = useState<ConversationTurn[]>([]);
  const [deletedSavedIds, setDeletedSavedIds] = useState<Set<string>>(new Set());
  const [renderedSessionId, setRenderedSessionId] = useState(activeSessionId);
  const prevSessionIdRef = useRef(activeSessionId);
  const pendingSubmitRef = useRef(false);

  useEffect(() => {
    const prevId = prevSessionIdRef.current;
    prevSessionIdRef.current = activeSessionId;

    if (renderedSessionId === activeSessionId) return;

    const isSubmitCreatedSession = prevId === null && activeSessionId !== null && pendingSubmitRef.current;

    if (isSubmitCreatedSession) {
      pendingSubmitRef.current = false;
      setRenderedSessionId(activeSessionId);
    } else {
      setRenderedSessionId(activeSessionId);
      setLocalTurns([]);
      setDeletedSavedIds(new Set());
    }
  }, [activeSessionId, renderedSessionId]);

  const localSavedIdsWithActiveAttempt = React.useMemo(
    () =>
      new Set(
        localTurns
          .filter((t) => t.savedQueryId && t.attemptId && !deletedSavedIds.has(t.savedQueryId))
          .map((t) => t.savedQueryId as string)
      ),
    [localTurns, deletedSavedIds]
  );
  const historyAttempts = (sessionDetail?.attempts ?? []).filter(
    (a) => !deletedSavedIds.has(a.id) && !localSavedIdsWithActiveAttempt.has(a.id)
  );
  const historyAttemptIds = React.useMemo(() => new Set(historyAttempts.map((a) => a.id)), [historyAttempts]);
  const dedupedLocalTurns = React.useMemo(
    () =>
      localTurns.filter(
        (t) =>
          !(t.savedQueryId && historyAttemptIds.has(t.savedQueryId)) &&
          !(t.savedQueryId && deletedSavedIds.has(t.savedQueryId))
      ),
    [localTurns, historyAttemptIds, deletedSavedIds]
  );

  const allTurns: ConversationTurn[] = [
    ...[...historyAttempts].reverse().map((a) => buildHistoryTurn(a, availableConnections)),
    ...dedupedLocalTurns,
  ];

  const showEmptyState = activeSessionId === null && allTurns.length === 0;
  const showLoading = isLoading && allTurns.length === 0 && !querySubmit.isSubmitting;

  const updateTurn = useCallback(
    (matchKey: string, patch: Partial<ConversationTurn>) => {
      setLocalTurns((prev) =>
        prev.map((t) => {
          const tKey = t.attemptId || t.id;
          return tKey === matchKey ? { ...t, ...patch } : t;
        })
      );
    },
    []
  );

  const handleDelete = useCallback(
    async (savedQueryId: string) => {
      // Optimistically remove from both history and local turns
      setDeletedSavedIds((prev) => new Set(prev).add(savedQueryId));
      setLocalTurns((prev) => prev.filter((t) => t.savedQueryId !== savedQueryId));
      try {
        await deleteHistoryEntry({ path: { query_id: savedQueryId } });
        queryClient.invalidateQueries({ queryKey: ['history'] });
        if (activeSessionId) {
          queryClient.invalidateQueries({ queryKey: ['sessions', activeSessionId] });
        }
      } catch {
        // Silently ignore — turn is already removed from UI
      }
    },
    [queryClient, activeSessionId]
  );

  const handleRegenerate = useCallback(
    async (attemptId: string) => {
      updateTurn(attemptId, { isLoading: true });

      try {
        const data = await querySubmit.regenerateQuery(attemptId);
        if (data && typeof data === 'object' && 'kind' in data) {
          if (data.kind === 'result') {
            const result = data as QueryResult;
            updateTurn(attemptId, {
              isLoading: false,
              result,
              sql: result.generated_sql,
              attemptId: result.attempt_id,
              savedQueryId: result.accepted_query_id,
              refinePrompt: undefined,
              evaluatorRejection: undefined,
            });
            if (activeSessionId) {
              queryClient.invalidateQueries({ queryKey: ['sessions', activeSessionId] });
            }
          } else if (data.kind === 'refine') {
            updateTurn(attemptId, {
              isLoading: false,
              refinePrompt: data as RefinePrompt,
              result: undefined,
              sql: '',
              evaluatorRejection: undefined,
            });
          }
        }
      } catch {
        updateTurn(attemptId, { isLoading: false });
      }
    },
    [querySubmit, updateTurn, queryClient, activeSessionId]
  );

  const handleSubmit = useCallback(
    async (question: string) => {
      if (!selectedConnectionId) {
        const turnId = `turn-${Date.now()}`;
        setLocalTurns((prev) => [
          ...prev,
          {
            id: turnId,
            question,
            evaluatorRejection: {
              message_key: 'query.error.noDatabaseSelected',
              violations: [
                {
                  rule: 'connection_required',
                  message_key: 'query.error.noDatabaseSelectedMessage',
                },
              ],
            } as EvaluatorRejection,
          },
        ]);
        return;
      }

      if (activeSessionId === null) {
        pendingSubmitRef.current = true;
      }

      const turnId = `turn-${Date.now()}`;
      const meta = getConnectionMeta(selectedConnectionId, availableConnections);
      setLocalTurns((prev) => [
        ...prev,
        {
          id: turnId,
          question,
          isLoading: true,
          connectionName: meta.name,
          databaseType: meta.type,
        },
      ]);

      try {
        const data = (await querySubmit.submitQuestion(question, activeSessionId, selectedConnectionId)) as unknown;
        const record = data as Record<string, unknown>;
        if (activeSessionId) {
          queryClient.invalidateQueries({ queryKey: ['sessions', activeSessionId] });
        }
        if (record && typeof record === 'object' && 'kind' in record && record.kind === 'result') {
          const result = data as QueryResult;
          setLocalTurns((prev) =>
            prev.map((t) =>
              t.id === turnId
                ? {
                    ...t,
                    isLoading: false,
                    result,
                    sql: result.generated_sql,
                    attemptId: result.attempt_id,
                    savedQueryId: result.accepted_query_id,
                  }
                : t
            )
          );
        } else if (record && typeof record === 'object' && 'kind' in record && record.kind === 'refine') {
          setLocalTurns((prev) =>
            prev.map((t) =>
              t.id === turnId ? { ...t, isLoading: false, refinePrompt: data as RefinePrompt } : t
            )
          );
        } else {
          setLocalTurns((prev) => prev.map((t) => (t.id === turnId ? { ...t, isLoading: false } : t)));
        }
      } catch (err: unknown) {
        const apiErr = (err && typeof err === 'object') ? (err as Record<string, unknown>) : {};
        const messageKey = (apiErr.message_key as string) || (apiErr.detail as Record<string, unknown>)?.message_key as string;
        const errCode = (apiErr.error as string) || (apiErr.detail as Record<string, unknown>)?.error as string;

        if (messageKey === 'error.hostile_input_blocked' || errCode === 'hostile_input_blocked') {
          setLocalTurns((prev) =>
            prev.map((t) =>
              t.id === turnId ? { ...t, isLoading: false, hostileInputBlocked: true } : t
            )
          );
          return;
        }

        if (messageKey === 'error.quota_exceeded' || errCode === 'quota_exceeded') {
          const resetAt = (apiErr.reset_at as string) || (apiErr.detail as Record<string, unknown>)?.reset_at as string;
          setLocalTurns((prev) =>
            prev.map((t) =>
              t.id === turnId ? { ...t, isLoading: false, quotaExceeded: { resetAt } } : t
            )
          );
          return;
        }

        if (messageKey === 'error.service_unavailable' || errCode === 'service_unavailable') {
          setLocalTurns((prev) => prev.filter((t) => t.id !== turnId));
          showAlert(t('error.service_unavailable'), '', 'destructive');
          return;
        }

        if ('violations' in apiErr) {
          setLocalTurns((prev) =>
            prev.map((t) =>
              t.id === turnId ? { ...t, isLoading: false, evaluatorRejection: apiErr as unknown as EvaluatorRejection } : t
            )
          );
        } else if ('kind' in apiErr && apiErr.kind === 'refine') {
          setLocalTurns((prev) =>
            prev.map((t) =>
              t.id === turnId ? { ...t, isLoading: false, refinePrompt: apiErr as unknown as RefinePrompt } : t
            )
          );
        } else {
          const code = (apiErr.error as string) || (apiErr.detail as Record<string, unknown>)?.error as string;
          if (code === 'concurrent') {
            setLocalTurns((prev) => prev.filter((t) => t.id !== turnId));
            showAlert(t('query.error.concurrent'), '', 'destructive');
          } else if (code === 'llm_unavailable' || code === 'llmUnavailable') {
            setLocalTurns((prev) => prev.filter((t) => t.id !== turnId));
            showAlert(t('query.error.llmUnavailable'), '', 'destructive');
          } else {
            const connErr = mapApiErrorToConnectionErrorKind(apiErr);
            if (connErr) {
              setLocalTurns((prev) =>
                prev.map((t) => (t.id === turnId ? { ...t, isLoading: false, connectionError: connErr } : t))
              );
            } else {
              setLocalTurns((prev) => prev.map((t) => (t.id === turnId ? { ...t, isLoading: false } : t)));
            }
          }
        }
      }
    },
    [activeSessionId, querySubmit, selectedConnectionId, availableConnections, queryClient, showAlert, t]
  );

  return (
    <div className="workspace-page" data-testid="workspace-page">
      <div className="workspace-conversation">
        {showEmptyState ? (
          <div className="workspace-empty-state">
            <MessageSquare className="w-12 h-12 workspace-empty-icon" />
            <h2 className="workspace-empty-title">{t('workspace.emptyState')}</h2>
            <p className="workspace-empty-subtitle">{t('workspace.placeholder')}</p>
          </div>
        ) : showLoading ? (
          <div className="workspace-loading">
            <div className="workspace-spinner" />
            <p>{t('history.loading')}</p>
          </div>
        ) : (
          <div className="workspace-messages">
            {allTurns.map((turn) => (
              <div key={turn.id} className="workspace-message-pair">
                <UserBubble text={turn.question} />
                {turn.isLoading ? (
                  <div
                    className="workspace-assistant-loading"
                    data-testid="assistant-loading"
                    role="status"
                    aria-live="polite"
                  >
                    <div className="workspace-spinner-small" />
                    <span>{t('query.status.processing')}</span>
                  </div>
                ) : turn.connectionError ? (
                  <ConnectionErrorCard kind={turn.connectionError} />
                ) : turn.evaluatorRejection ? (
                  <div className="workspace-rejection-banner w-full" data-testid="rejection-banner">
                    <EvaluatorRejectionBanner {...mapEvaluatorRejection(turn.evaluatorRejection)} />
                  </div>
                ) : turn.quotaExceeded ? (
                  <div className="workspace-rejection-banner w-full" data-testid="quota-exceeded-banner">
                    <QuotaExceededBanner resetAt={turn.quotaExceeded.resetAt} />
                  </div>
                ) : turn.hostileInputBlocked ? (
                  <div className="workspace-rejection-banner w-full" data-testid="hostile-input-blocked-banner">
                    <HostileInputBlockedBanner />
                  </div>
                ) : turn.refinePrompt ? (
                  <div className="workspace-refine-banner" data-testid="refine-banner" role="alert">
                    <p>{t('query.refine.message')}</p>
                  </div>
                ) : (
                  <AssistantResponseCard
                    sql={turn.sql ?? ''}
                    result={turn.result}
                    attemptId={turn.attemptId}
                    savedQueryId={turn.savedQueryId}
                    connectionName={turn.connectionName}
                    databaseType={turn.databaseType}
                    onRegenerate={turn.attemptId ? handleRegenerate : undefined}
                    onDelete={turn.savedQueryId ? handleDelete : undefined}
                  />
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      <PromptInput
        onSubmit={(text) => {
          handleSubmit(text);
          setLoadedQuestion('');
        }}
        disabled={querySubmit.isSubmitting}
        connections={availableConnections}
        selectedConnectionId={selectedConnectionId}
        onSelectConnection={setSelectedConnectionId}
        initialText={loadedQuestion}
      />
      {alert && (
        <div
          role="alert"
          className="fixed top-4 end-4 z-50 p-4 rounded-xl border border-red-500/20 bg-red-950/80 backdrop-blur-md text-red-200 shadow-2xl flex items-start gap-3 w-96 animate-in slide-in-from-top-4 duration-300"
        >
          <div className="flex-1">
            <p className="font-semibold text-sm">{alert.title}</p>
            {alert.description && <p className="text-sm opacity-90 mt-1">{alert.description}</p>}
          </div>
          <button
            onClick={() => setAlert(null)}
            className="text-current opacity-70 hover:opacity-100 transition-opacity"
            aria-label={t('common.close')}
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
};
