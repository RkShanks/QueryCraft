import React, { useState, useCallback, useEffect, useLayoutEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { useUIStore } from '../stores/uiStore';
import { useSessionDetail } from '../hooks/useSessions';
import { useQuerySubmit } from '../hooks/useQuerySubmit';
import { useQueryLimits } from '../hooks/useQueryLimits';
import {
  didSessionDeletionStart,
  getSessionDeletionVersion,
  isSessionDeletionError,
  isSessionUnavailable,
} from '../sessionDeletionLifecycle';
import { UserBubble } from '../components/chat/UserBubble';
import { AssistantResponseCard } from '../components/chat/AssistantResponseCard';
import { PromptInput, type QuestionLimitState } from '../components/chat/PromptInput';
import { MessageSquare } from '../components/icons';
import { deleteHistoryEntry, getHistoryEntry } from '../api/generated/sdk.gen';
import type { QueryResult, RefinePrompt, EvaluatorRejection, AttemptSummary, UserConnectionResponse } from '../api/generated/types.gen';
import { useConnectionSelection } from '../hooks/useConnectionSelection';
import { useUserConnections } from '../hooks/useUserConnections';
import { ClientQueryState } from '../components/common/ClientQueryState';
import { PERMISSIONS } from '../auth/permissions';
import { requirePermission, usePermission } from '../hooks/usePermission';
import { ConnectionErrorCard } from '../components/chat/ConnectionErrorCard';
import type { ConnectionErrorKind } from '../components/chat/ConnectionErrorCard';
import { EvaluatorRejectionBanner } from '../components/query/EvaluatorRejectionBanner';
import { QuotaExceededBanner } from '../components/query/QuotaExceededBanner';
import { HostileInputBlockedBanner } from '../components/query/HostileInputBlockedBanner';
import { isClientContractError } from '../api/responseValidation';
import { isRequestAbortedError } from '../api/requestScope';
import './WorkspacePage.css';

type TurnRecoveryKind =
  | 'deleteFailed'
  | 'deleteUncertain'
  | 'regenerateFailed'
  | 'regenerateTerminal';

interface TurnRecoveryState {
  kind: TurnRecoveryKind;
}

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
  sourceSessionId?: string | null;
  immutableConnectionId?: string;
  isRegenerating?: boolean;
  isConnectionRetrying?: boolean;
  recovery?: TurnRecoveryState;
}

interface DeleteSnapshot {
  turn: ConversationTurn;
  localIndex: number;
  wasDeleted: boolean;
  sessionId: string | null;
}

function getApiErrorCode(error: unknown): string | undefined {
  if (!error || typeof error !== 'object') return undefined;
  const record = error as Record<string, unknown>;
  const detail = record.detail;
  return (record.error as string | undefined) ??
    (detail && typeof detail === 'object'
      ? (detail as Record<string, unknown>).error as string | undefined
      : undefined);
}

function isDefiniteServerFailure(error: unknown): boolean {
  return !isClientContractError(error) && getApiErrorCode(error) !== undefined;
}

function isTerminalAttemptError(error: unknown): boolean {
  const code = getApiErrorCode(error);
  return code === 'attempt_invalid' || code === 'attempt_expired';
}

function isCurrentSessionContext(sessionId: string | null, deletionVersion: number): boolean {
  if (useUIStore.getState().activeSessionId !== sessionId) return false;
  return !sessionId ||
    (!isSessionUnavailable(sessionId) && !didSessionDeletionStart(sessionId, deletionVersion));
}

function isCurrentRetryContext(
  sessionId: string | null,
  deletionVersion: number,
  resultSessionId?: string
): boolean {
  if (sessionId) return isCurrentSessionContext(sessionId, deletionVersion);
  const currentSessionId = useUIStore.getState().activeSessionId;
  return resultSessionId ? currentSessionId === resultSessionId : currentSessionId === null;
}

const recoveryMessageKeys: Record<TurnRecoveryKind, string> = {
  deleteFailed: 'workspace.recovery.deleteFailed',
  deleteUncertain: 'workspace.recovery.deleteUncertain',
  regenerateFailed: 'workspace.recovery.regenerateFailed',
  regenerateTerminal: 'workspace.recovery.regenerateTerminal',
};

const TurnRecoveryNotice: React.FC<{
  recovery: TurnRecoveryState;
  onRetry?: () => void;
}> = ({ recovery, onRetry }) => {
  const { t } = useTranslation();
  const message = t(recoveryMessageKeys[recovery.kind]);

  return (
    <div
      className="workspace-recovery-notice"
      role="alert"
      aria-label={message}
      aria-live="assertive"
    >
      <span>{message}</span>
      {onRetry && (
        <button className="workspace-recovery-button" type="button" onClick={onRetry}>
          {t('common.retry')}
        </button>
      )}
    </div>
  );
};

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
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const activeSessionId = useUIStore((state) => state.activeSessionId);
  const sessionDetailQuery = useSessionDetail(activeSessionId ?? '');
  const {
    data: sessionDetail,
    isLoading,
    isError: sessionDetailError,
    isFetchNextPageError,
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
  } = sessionDetailQuery;
  const querySubmit = useQuerySubmit();
  const queryLimitsQuery = useQueryLimits();
  const {
    data: queryLimits,
    isError: queryLimitsFailed,
    isFetching: queryLimitsFetching,
    refetch: refetchQueryLimits,
  } = queryLimitsQuery;
  const canViewHistory = usePermission(PERMISSIONS.QUERY_HISTORY_VIEW);
  const canManageConnections = usePermission(PERMISSIONS.ADMIN_CONNECTIONS_MANAGE);

  const retryQueryLimits = useCallback(() => {
    void refetchQueryLimits();
  }, [refetchQueryLimits]);
  const questionLimit: QuestionLimitState = queryLimits
    ? {
        status: 'ready',
        maxQuestionLength: queryLimits.max_question_length,
      }
    : queryLimitsFailed && !queryLimitsFetching
      ? { status: 'error', onRetry: retryQueryLimits }
      : { status: 'loading' };

  const [alert, setAlert] = useState<{
    id: string;
    title: string;
    description: string;
    variant: 'default' | 'destructive' | 'success';
  } | null>(null);
  const alertTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      // Navigation/unmount cleanup: no alert timer may fire after the route dies.
      if (alertTimerRef.current !== null) clearTimeout(alertTimerRef.current);
    };
  }, []);

  const showAlert = useCallback((
    title: string,
    description: string,
    variant: 'default' | 'destructive' | 'success' = 'default'
  ) => {
    const id = Math.random().toString(36).substring(2, 9);
    if (alertTimerRef.current !== null) clearTimeout(alertTimerRef.current);
    setAlert({ id, title, description, variant });
    alertTimerRef.current = setTimeout(() => {
      alertTimerRef.current = null;
      setAlert((prev) => (prev?.id === id ? null : prev));
    }, 5000);
  }, []);

  // Fetch available connections for T-460
  const userConnectionsQuery = useUserConnections();
  const { data: userConnectionsResponse } = userConnectionsQuery;
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
  const [savedTurnRecoveries, setSavedTurnRecoveries] = useState<
    Record<string, TurnRecoveryState>
  >({});
  const [renderedSessionId, setRenderedSessionId] = useState(activeSessionId);
  const prevSessionIdRef = useRef(activeSessionId);
  const pendingSubmitRef = useRef(false);
  const pendingDeleteIdsRef = useRef(new Set<string>());
  const pendingRegenerateIdsRef = useRef(new Set<string>());
  const pendingConnectionRetryIdsRef = useRef(new Set<string>());
  const conversationRef = useRef<HTMLDivElement>(null);
  const pendingScrollRestoreRef = useRef<{
    sessionId: string;
    previousHeight: number;
    previousTop: number;
  } | null>(null);

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
      setSavedTurnRecoveries({});
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
  const historyAttempts = React.useMemo(
    () =>
      (sessionDetail?.attempts ?? []).filter(
        (attempt) =>
          !deletedSavedIds.has(attempt.id) &&
          !localSavedIdsWithActiveAttempt.has(attempt.id)
      ),
    [deletedSavedIds, localSavedIdsWithActiveAttempt, sessionDetail?.attempts]
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

  const allTurns = React.useMemo<ConversationTurn[]>(
    () =>
      [
        ...[...historyAttempts]
          .reverse()
          .map((attempt) => buildHistoryTurn(attempt, availableConnections)),
        ...dedupedLocalTurns,
      ].map((turn) => {
        const recovery = turn.savedQueryId
          ? savedTurnRecoveries[turn.savedQueryId]
          : undefined;
        return recovery ? { ...turn, recovery } : turn;
      }),
    [availableConnections, dedupedLocalTurns, historyAttempts, savedTurnRecoveries]
  );

  const showEmptyState = activeSessionId === null && allTurns.length === 0;
  const showLoading = isLoading && allTurns.length === 0 && !querySubmit.isSubmitting;
  const showHistoryError = sessionDetailError && allTurns.length === 0 && activeSessionId !== null;

  useLayoutEffect(() => {
    const pending = pendingScrollRestoreRef.current;
    if (!pending) return;
    if (activeSessionId !== pending.sessionId) {
      pendingScrollRestoreRef.current = null;
      return;
    }
    const conversation = conversationRef.current;
    if (!conversation) return;
    conversation.scrollTop =
      pending.previousTop + conversation.scrollHeight - pending.previousHeight;
    pendingScrollRestoreRef.current = null;
  }, [activeSessionId, sessionDetail?.attempts.length]);

  const handleLoadOlder = useCallback(async () => {
    const conversation = conversationRef.current;
    const requestedSessionId = activeSessionId;
    if (!conversation || !requestedSessionId) return;
    const previousAttemptCount = sessionDetail?.attempts.length ?? 0;
    pendingScrollRestoreRef.current = {
      sessionId: requestedSessionId,
      previousHeight: conversation.scrollHeight,
      previousTop: conversation.scrollTop,
    };

    const result = await fetchNextPage();
    if (useUIStore.getState().activeSessionId !== requestedSessionId) {
      if (pendingScrollRestoreRef.current?.sessionId === requestedSessionId) {
        pendingScrollRestoreRef.current = null;
      }
      return;
    }
    const loadedAttemptCount = new Set(
      result.data?.pages.flatMap((page) => page.attempts.map((attempt) => attempt.id)) ?? []
    ).size;
    if (
      loadedAttemptCount <= previousAttemptCount &&
      pendingScrollRestoreRef.current?.sessionId === requestedSessionId
    ) {
      pendingScrollRestoreRef.current = null;
    }
  }, [activeSessionId, fetchNextPage, sessionDetail?.attempts.length]);

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

  const invalidateWorkspaceHistory = useCallback(
    (sessionId: string | null) => {
      void queryClient.invalidateQueries({ queryKey: ['history'] });
      if (sessionId) {
        void queryClient.invalidateQueries({ queryKey: ['sessions', sessionId] });
      }
    },
    [queryClient]
  );

  const restoreDeletedTurn = useCallback(
    (snapshot: DeleteSnapshot, kind: TurnRecoveryKind) => {
      setDeletedSavedIds((previous) => {
        if (snapshot.wasDeleted) return previous;
        const restored = new Set(previous);
        restored.delete(snapshot.turn.savedQueryId as string);
        return restored;
      });
      setLocalTurns((previous) => {
        if (
          snapshot.localIndex < 0 ||
          previous.some((turn) => turn.savedQueryId === snapshot.turn.savedQueryId)
        ) {
          return previous;
        }
        const restored = [...previous];
        restored.splice(Math.min(snapshot.localIndex, restored.length), 0, snapshot.turn);
        return restored;
      });
      setSavedTurnRecoveries((previous) => ({
        ...previous,
        [snapshot.turn.savedQueryId as string]: { kind },
      }));
    },
    []
  );

  const handleDelete = useCallback(
    async (savedQueryId: string) => {
      requirePermission(canViewHistory, PERMISSIONS.QUERY_HISTORY_VIEW);
      if (pendingDeleteIdsRef.current.has(savedQueryId)) return;

      const turn = allTurns.find((candidate) => candidate.savedQueryId === savedQueryId);
      if (!turn) return;
      const sessionId = activeSessionId;
      const deletionVersion = sessionId ? getSessionDeletionVersion(sessionId) : 0;
      const snapshot: DeleteSnapshot = {
        turn,
        localIndex: localTurns.findIndex((candidate) => candidate.savedQueryId === savedQueryId),
        wasDeleted: deletedSavedIds.has(savedQueryId),
        sessionId,
      };

      pendingDeleteIdsRef.current.add(savedQueryId);
      setSavedTurnRecoveries((previous) => {
        const next = { ...previous };
        delete next[savedQueryId];
        return next;
      });
      setDeletedSavedIds((prev) => new Set(prev).add(savedQueryId));

      try {
        await deleteHistoryEntry({
          path: { query_id: savedQueryId },
          throwOnError: true,
        });
        if (!isCurrentSessionContext(sessionId, deletionVersion)) return;
        invalidateWorkspaceHistory(sessionId);
      } catch (error: unknown) {
        if (!isCurrentSessionContext(sessionId, deletionVersion)) return;
        if (getApiErrorCode(error) === 'not_found') {
          invalidateWorkspaceHistory(sessionId);
          return;
        }
        if (isDefiniteServerFailure(error)) {
          restoreDeletedTurn(snapshot, 'deleteFailed');
          return;
        }

        try {
          await getHistoryEntry({
            path: { query_id: savedQueryId },
            throwOnError: true,
          });
          if (!isCurrentSessionContext(sessionId, deletionVersion)) return;
          restoreDeletedTurn(snapshot, 'deleteFailed');
        } catch (reconciliationError: unknown) {
          if (!isCurrentSessionContext(sessionId, deletionVersion)) return;
          if (getApiErrorCode(reconciliationError) === 'not_found') {
            invalidateWorkspaceHistory(sessionId);
          } else {
            restoreDeletedTurn(snapshot, 'deleteUncertain');
          }
        }
      } finally {
        pendingDeleteIdsRef.current.delete(savedQueryId);
      }
    },
    [
      activeSessionId,
      allTurns,
      canViewHistory,
      deletedSavedIds,
      invalidateWorkspaceHistory,
      localTurns,
      restoreDeletedTurn,
    ]
  );

  const handleRegenerate = useCallback(
    async (attemptId: string) => {
      if (pendingRegenerateIdsRef.current.has(attemptId)) return;
      const originalTurn = allTurns.find((turn) => turn.attemptId === attemptId);
      if (!originalTurn) return;

      const sessionId = originalTurn.sourceSessionId ?? activeSessionId;
      const deletionVersion = sessionId ? getSessionDeletionVersion(sessionId) : 0;
      pendingRegenerateIdsRef.current.add(attemptId);
      updateTurn(attemptId, { isRegenerating: true, recovery: undefined });

      try {
        const data = await querySubmit.regenerateQuery(attemptId);
        if (!isCurrentSessionContext(sessionId, deletionVersion)) return;
        if (data && typeof data === 'object' && 'kind' in data) {
          if (data.kind === 'result') {
            const result = data as QueryResult;
            updateTurn(attemptId, {
              isRegenerating: false,
              recovery: undefined,
              result,
              sql: result.generated_sql,
              attemptId: result.attempt_id,
              savedQueryId: result.accepted_query_id ?? undefined,
              refinePrompt: undefined,
              evaluatorRejection: undefined,
              sourceSessionId: result.session_id ?? sessionId,
            });
            invalidateWorkspaceHistory(sessionId);
          } else if (data.kind === 'refine') {
            updateTurn(attemptId, {
              isRegenerating: false,
              recovery: undefined,
              refinePrompt: data as RefinePrompt,
              result: undefined,
              sql: '',
              evaluatorRejection: undefined,
            });
          }
        }
      } catch (error: unknown) {
        if (!isCurrentSessionContext(sessionId, deletionVersion)) return;
        if (isTerminalAttemptError(error)) {
          if (sessionId) {
            try {
              await queryClient.refetchQueries({
                queryKey: ['sessions', sessionId],
                exact: true,
              });
            } catch {
              // The terminal state remains safe: no invalid retry is exposed.
            }
          }
          if (!isCurrentSessionContext(sessionId, deletionVersion)) return;
          updateTurn(attemptId, {
            isRegenerating: false,
            recovery: { kind: 'regenerateTerminal' },
          });
        } else {
          updateTurn(attemptId, {
            isRegenerating: false,
            recovery: { kind: 'regenerateFailed' },
          });
        }
      } finally {
        pendingRegenerateIdsRef.current.delete(attemptId);
      }
    },
    [
      activeSessionId,
      allTurns,
      invalidateWorkspaceHistory,
      queryClient,
      querySubmit,
      updateTurn,
    ]
  );

  const handleManageConnections = useCallback(() => {
    navigate('/admin/connections');
  }, [navigate]);

  const handleConnectionRetry = useCallback(
    async (turnId: string) => {
      if (pendingConnectionRetryIdsRef.current.has(turnId)) return;
      const originalTurn = allTurns.find((turn) => turn.id === turnId);
      if (!originalTurn?.immutableConnectionId || !originalTurn.question) return;

      const sessionId = originalTurn.sourceSessionId ?? null;
      const deletionVersion = sessionId ? getSessionDeletionVersion(sessionId) : 0;
      if (!isCurrentRetryContext(sessionId, deletionVersion)) return;

      pendingConnectionRetryIdsRef.current.add(turnId);
      if (sessionId === null) pendingSubmitRef.current = true;
      updateTurn(turnId, { isConnectionRetrying: true });

      try {
        const data = await querySubmit.submitQuestion(
          originalTurn.question,
          sessionId,
          originalTurn.immutableConnectionId
        );
        if (!data || typeof data !== 'object' || !('kind' in data)) {
          if (isCurrentRetryContext(sessionId, deletionVersion)) {
            updateTurn(turnId, { isConnectionRetrying: false });
          }
          return;
        }

        if (data.kind === 'result') {
          const result = data as QueryResult;
          if (!isCurrentRetryContext(sessionId, deletionVersion, result.session_id ?? undefined)) {
            return;
          }
          updateTurn(turnId, {
            isConnectionRetrying: false,
            connectionError: undefined,
            result,
            sql: result.generated_sql,
            attemptId: result.attempt_id,
            savedQueryId: result.accepted_query_id ?? undefined,
            refinePrompt: undefined,
            evaluatorRejection: undefined,
            sourceSessionId: result.session_id ?? sessionId,
          });
          invalidateWorkspaceHistory(result.session_id ?? sessionId);
        } else if (data.kind === 'refine') {
          if (!isCurrentRetryContext(sessionId, deletionVersion)) return;
          updateTurn(turnId, {
            isConnectionRetrying: false,
            connectionError: undefined,
            refinePrompt: data as RefinePrompt,
          });
        }
      } catch (error: unknown) {
        if (!isCurrentRetryContext(sessionId, deletionVersion)) return;
        const apiError = error && typeof error === 'object'
          ? error as Record<string, unknown>
          : {};
        const code = getApiErrorCode(error);
        const messageKey = (apiError.message_key as string | undefined) ??
          (apiError.detail && typeof apiError.detail === 'object'
            ? (apiError.detail as Record<string, unknown>).message_key as string | undefined
            : undefined);

        if (code === 'quota_exceeded' || messageKey === 'error.quota_exceeded') {
          const detail = apiError.detail && typeof apiError.detail === 'object'
            ? apiError.detail as Record<string, unknown>
            : {};
          updateTurn(turnId, {
            isConnectionRetrying: false,
            connectionError: undefined,
            quotaExceeded: {
              resetAt: (apiError.reset_at as string | undefined) ??
                (detail.reset_at as string | undefined),
            },
          });
          return;
        }

        if (code === 'hostile_input_blocked' || messageKey === 'error.hostile_input_blocked') {
          updateTurn(turnId, {
            question: '',
            isConnectionRetrying: false,
            connectionError: undefined,
            hostileInputBlocked: true,
          });
          return;
        }

        const connectionError = mapApiErrorToConnectionErrorKind(apiError);
        updateTurn(turnId, {
          isConnectionRetrying: false,
          connectionError: connectionError ?? originalTurn.connectionError,
        });
      } finally {
        pendingConnectionRetryIdsRef.current.delete(turnId);
      }
    },
    [allTurns, invalidateWorkspaceHistory, querySubmit, updateTurn]
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
          question: '',
          isLoading: true,
          connectionName: meta.name,
          databaseType: meta.type,
          sourceSessionId: activeSessionId,
          immutableConnectionId: selectedConnectionId,
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
                    question,
                    isLoading: false,
                    result,
                    sql: result.generated_sql,
                    attemptId: result.attempt_id,
                    savedQueryId: result.accepted_query_id ?? undefined,
                    sourceSessionId: result.session_id ?? activeSessionId,
                  }
                : t
            )
          );
        } else if (record && typeof record === 'object' && 'kind' in record && record.kind === 'refine') {
          setLocalTurns((prev) =>
            prev.map((t) =>
              t.id === turnId
                ? { ...t, question, isLoading: false, refinePrompt: data as RefinePrompt }
                : t
            )
          );
        } else {
          setLocalTurns((prev) => prev.map((t) => (t.id === turnId ? { ...t, question, isLoading: false } : t)));
        }
      } catch (err: unknown) {
        if (isSessionDeletionError(err) || isRequestAbortedError(err)) {
          setLocalTurns((prev) => prev.filter((turn) => turn.id !== turnId));
          return;
        }
        const apiErr = (err && typeof err === 'object') ? (err as Record<string, unknown>) : {};
        const messageKey = (apiErr.message_key as string) || (apiErr.detail as Record<string, unknown>)?.message_key as string;
        const errCode = (apiErr.error as string) || (apiErr.detail as Record<string, unknown>)?.error as string;

        if (messageKey === 'error.hostile_input_blocked' || errCode === 'hostile_input_blocked') {
          setLocalTurns((prev) =>
            prev.map((t) =>
              t.id === turnId
                ? { ...t, question: '', isLoading: false, hostileInputBlocked: true }
                : t
            )
          );
          return;
        }

        if (messageKey === 'error.quota_exceeded' || errCode === 'quota_exceeded') {
          const resetAt = (apiErr.reset_at as string) || (apiErr.detail as Record<string, unknown>)?.reset_at as string;
          setLocalTurns((prev) =>
            prev.map((t) =>
              t.id === turnId ? { ...t, question, isLoading: false, quotaExceeded: { resetAt } } : t
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
              t.id === turnId ? { ...t, question, isLoading: false, evaluatorRejection: apiErr as unknown as EvaluatorRejection } : t
            )
          );
        } else if ('kind' in apiErr && apiErr.kind === 'refine') {
          setLocalTurns((prev) =>
            prev.map((t) =>
              t.id === turnId ? { ...t, question, isLoading: false, refinePrompt: apiErr as unknown as RefinePrompt } : t
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
                prev.map((t) => (t.id === turnId ? { ...t, question, isLoading: false, connectionError: connErr } : t))
              );
            } else {
              setLocalTurns((prev) => prev.map((t) => (t.id === turnId ? { ...t, question, isLoading: false } : t)));
            }
          }
        }
      }
    },
    [activeSessionId, querySubmit, selectedConnectionId, availableConnections, queryClient, showAlert, t]
  );

  return (
    <div className="workspace-page" data-testid="workspace-page">
      <div className="workspace-conversation" ref={conversationRef}>
        <ClientQueryState
          query={userConnectionsQuery}
          fallbackErrorKey="admin.connections.loadError"
        />
        {activeSessionId && sessionDetail && (
          <ClientQueryState
            query={sessionDetailQuery}
            fallbackErrorKey="workspace.historyLoadError"
            isPartial={hasNextPage}
          />
        )}
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
        ) : showHistoryError ? (
          <ClientQueryState
            query={sessionDetailQuery}
            fallbackErrorKey="workspace.historyLoadError"
          />
        ) : (
          <>
            {(hasNextPage || isFetchNextPageError) && (
              <div className="workspace-history-actions">
                {isFetchNextPageError && (
                  <p className="workspace-history-inline-error" role="alert">
                    {t('workspace.historyLoadError')}
                  </p>
                )}
                {hasNextPage && (
                  <button
                    type="button"
                    className="workspace-load-older"
                    disabled={isFetchingNextPage}
                    onClick={() => void handleLoadOlder()}
                  >
                    {isFetchingNextPage ? t('workspace.loadingOlder') : t('workspace.loadOlder')}
                  </button>
                )}
              </div>
            )}
            <div className="workspace-messages">
            {allTurns.map((turn) => (
              <div key={turn.id} className="workspace-message-pair">
                {!turn.hostileInputBlocked && turn.question && <UserBubble text={turn.question} />}
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
                  <ConnectionErrorCard
                    kind={turn.connectionError}
                    onManageConnections={
                      canManageConnections ? handleManageConnections : undefined
                    }
                    onRetry={
                      turn.sourceSessionId !== undefined &&
                      turn.sourceSessionId === activeSessionId &&
                      (!turn.sourceSessionId || !isSessionUnavailable(turn.sourceSessionId)) &&
                      turn.immutableConnectionId &&
                      turn.question
                        ? () => void handleConnectionRetry(turn.id)
                        : undefined
                    }
                    isRetrying={turn.isConnectionRetrying}
                  />
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
                    isRegenerating={turn.isRegenerating}
                    onDelete={turn.savedQueryId && canViewHistory ? handleDelete : undefined}
                  />
                )}
                {turn.isRegenerating && (
                  <div
                    className="workspace-regenerating"
                    role="status"
                    aria-live="polite"
                  >
                    <div className="workspace-spinner-small" aria-hidden="true" />
                    <span>{t('workspace.recovery.regenerating')}</span>
                  </div>
                )}
                {turn.recovery && (
                  <TurnRecoveryNotice
                    recovery={turn.recovery}
                    onRetry={
                      turn.recovery.kind === 'deleteFailed' ||
                      turn.recovery.kind === 'deleteUncertain'
                        ? turn.savedQueryId
                          ? () => void handleDelete(turn.savedQueryId as string)
                          : undefined
                        : turn.recovery.kind === 'regenerateFailed' && turn.attemptId
                          ? () => void handleRegenerate(turn.attemptId as string)
                          : undefined
                    }
                  />
                )}
              </div>
            ))}
            </div>
          </>
        )}
      </div>
      <PromptInput
        onSubmit={(text) => {
          setLoadedQuestion('');
          return handleSubmit(text);
        }}
        disabled={querySubmit.isSubmitting}
        connections={availableConnections}
        selectedConnectionId={selectedConnectionId}
        onSelectConnection={setSelectedConnectionId}
        initialText={loadedQuestion}
        questionLimit={questionLimit}
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
