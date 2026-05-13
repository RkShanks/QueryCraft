import React, { useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useUIStore } from '../stores/uiStore';
import { useSessionDetail } from '../hooks/useSessions';
import { useQuerySubmit } from '../hooks/useQuerySubmit';
import { useUpdateFeedback } from '../hooks/useFeedback';
import { UserBubble } from '../components/chat/UserBubble';
import { AssistantResponseCard } from '../components/chat/AssistantResponseCard';
import { PromptInput } from '../components/chat/PromptInput';
import { MessageSquare } from '../components/icons';
import type { QueryResult, RefinePrompt, EvaluatorRejection } from '../api/generated/types.gen';
import './WorkspacePage.css';

interface ConversationTurn {
  id: string;
  question: string;
  sql?: string;
  result?: QueryResult;
  refinePrompt?: RefinePrompt;
  evaluatorRejection?: EvaluatorRejection;
  isLoading?: boolean;
  currentFeedback?: number | null;
  saved?: boolean;
}

export const WorkspacePage: React.FC = () => {
  const { t } = useTranslation();
  const activeSessionId = useUIStore((state) => state.activeSessionId);
  const { data: sessionDetail, isLoading } = useSessionDetail(activeSessionId ?? '');
  const querySubmit = useQuerySubmit();
  const feedbackMutation = useUpdateFeedback();

  const [localTurns, setLocalTurns] = useState<ConversationTurn[]>([]);
  const [renderedSessionId, setRenderedSessionId] = useState(activeSessionId);

  // Reset local turns when switching sessions (setState during render is valid for resets)
  if (renderedSessionId !== activeSessionId) {
    setRenderedSessionId(activeSessionId);
    setLocalTurns([]);
  }

  const historyAttempts = sessionDetail?.attempts ?? [];
  const allTurns: ConversationTurn[] = [
    ...historyAttempts.map((a) => ({
      id: a.id,
      question: a.question_text,
      sql: a.generated_sql,
      currentFeedback: a.feedback ?? null,
      saved: a.saved,
    })),
    ...localTurns,
  ];

  const showEmptyState = activeSessionId === null && allTurns.length === 0;
  const showLoading = isLoading && allTurns.length === 0 && !querySubmit.isSubmitting;

  const handleRegenerate = useCallback(
    (attemptId: string) => {
      querySubmit.regenerateQuery(attemptId).catch(() => {});
    },
    [querySubmit]
  );

  const handleFeedback = useCallback(
    (attemptId: string, feedback: number) => {
      feedbackMutation.mutate({ attemptId, feedback });
    },
    [feedbackMutation]
  );

  const handleSubmit = useCallback(
    async (question: string) => {
      const turnId = `turn-${Date.now()}`;
      setLocalTurns((prev) => [...prev, { id: turnId, question, isLoading: true }]);

      try {
        const data = (await querySubmit.submitQuestion(question, activeSessionId)) as unknown;
        const record = data as Record<string, unknown>;
        if (record && typeof record === 'object' && 'kind' in record && record.kind === 'result') {
          const result = data as QueryResult;
          setLocalTurns((prev) =>
            prev.map((t) =>
              t.id === turnId ? { ...t, isLoading: false, result, sql: result.generated_sql } : t
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
    [activeSessionId, querySubmit]
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
                    attemptId={turn.id}
                    currentFeedback={turn.currentFeedback}
                    saved={turn.saved}
                    onRegenerate={handleRegenerate}
                    onFeedback={handleFeedback}
                  />
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      <PromptInput onSubmit={handleSubmit} disabled={querySubmit.isSubmitting} />
    </div>
  );
};
