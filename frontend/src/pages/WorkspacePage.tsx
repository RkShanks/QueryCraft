import React, { useState, useCallback, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
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
}

function buildHistoryTurn(a: AttemptSummary, connections: UserConnectionResponse[]): ConversationTurn {
  const turn: ConversationTurn = {
    id: a.id,
    question: a.question_text,
    sql: a.generated_sql,
    savedQueryId: a.id,
  };
  // Look up connection metadata from available connections using database_connection_id
  if (a.database_connection_id) {
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

export const WorkspacePage: React.FC = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const activeSessionId = useUIStore((state) => state.activeSessionId);
  const { data: sessionDetail, isLoading } = useSessionDetail(activeSessionId ?? '');
  const querySubmit = useQuerySubmit();

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

  const historyAttempts = (sessionDetail?.attempts ?? []).filter((a) => !deletedSavedIds.has(a.id));
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
    ...historyAttempts.map((a) => buildHistoryTurn(a, availableConnections)),
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
      } catch {
        // Silently ignore — turn is already removed from UI
      }
    },
    [queryClient]
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
    [querySubmit, updateTurn]
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
        const apiErr = err as Record<string, unknown>;
        if ('violations' in apiErr) {
          setLocalTurns((prev) =>
            prev.map((t) =>
              t.id === turnId ? { ...t, isLoading: false, evaluatorRejection: apiErr as EvaluatorRejection } : t
            )
          );
        } else if ('kind' in apiErr && apiErr.kind === 'refine') {
          setLocalTurns((prev) =>
            prev.map((t) =>
              t.id === turnId ? { ...t, isLoading: false, refinePrompt: apiErr as RefinePrompt } : t
            )
          );
        } else {
          setLocalTurns((prev) => prev.map((t) => (t.id === turnId ? { ...t, isLoading: false } : t)));
        }
      }
    },
    [activeSessionId, querySubmit, selectedConnectionId, availableConnections]
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
                  <div className="workspace-assistant-loading" data-testid="assistant-loading">
                    <div className="workspace-spinner-small" />
                    <span>{t('query.status.processing')}</span>
                  </div>
                ) : turn.evaluatorRejection ? (
                  <div className="workspace-rejection-banner" data-testid="rejection-banner">
                    <p>{t('query.evaluator.rejected')}</p>
                  </div>
                ) : turn.refinePrompt ? (
                  <div className="workspace-refine-banner" data-testid="refine-banner">
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
        onSubmit={handleSubmit}
        disabled={querySubmit.isSubmitting}
        connections={availableConnections}
        selectedConnectionId={selectedConnectionId}
        onSelectConnection={setSelectedConnectionId}
      />
    </div>
  );
};
