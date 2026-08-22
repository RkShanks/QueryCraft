import { useState, useCallback, useRef, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { submitQuestion, acceptQuery, rejectQuery, regenerateQuery } from '../api/generated/sdk.gen';
import type { SubmitQuestionData, AcceptQueryData } from '../api/generated/types.gen';
import type { QueryResult, RefinePrompt, EvaluatorRejection } from '../api/generated/types.gen';
import { useUIStore } from '../stores/uiStore';
import {
  didSessionDeletionStart,
  getSessionDeletionVersion,
  isSessionUnavailable,
  SessionDeletionError,
  subscribeToSessionDeletion,
} from '../sessionDeletionLifecycle';
import {
  isAbortFailure,
  RequestAbortedError,
  RequestScope,
  type DisposableRequestScope,
} from '../api/requestScope';
import { PERMISSIONS } from '../auth/permissions';
import { requirePermission, usePermission } from './usePermission';

interface ActiveRequest {
  scope: DisposableRequestScope;
  sessionId: string | null;
}

export const useSubmitQuestion = () => {
  const canSubmitQuery = usePermission(PERMISSIONS.QUERY_SUBMIT);
  return useMutation({
    mutationFn: (data: SubmitQuestionData['body']) => {
      requirePermission(canSubmitQuery, PERMISSIONS.QUERY_SUBMIT);
      return submitQuestion({ body: data, throwOnError: true }).then((res) => res.data);
    },
  });
};

export const useAcceptQuery = () => {
  const queryClient = useQueryClient();
  const canSubmitQuery = usePermission(PERMISSIONS.QUERY_SUBMIT);
  return useMutation({
    mutationFn: (data: AcceptQueryData['body']) => {
      requirePermission(canSubmitQuery, PERMISSIONS.QUERY_SUBMIT);
      return acceptQuery({ body: data, throwOnError: true }).then((res) => res.data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['history'] });
    },
  });
};

type ErrorKind = 'concurrent' | 'llmUnavailable' | 'attemptInvalid' | 'network' | 'connectionRequired' | 'quotaExceeded' | 'serviceUnavailable' | 'hostileInputBlocked';

export interface UseQuerySubmitReturn {
  submitQuestion: (q: string, sessionId?: string | null, connectionId?: string | null) => Promise<unknown>;
  rejectQuery: (attemptId: string) => Promise<void>;
  regenerateQuery: (attemptId: string) => Promise<unknown>;
  acceptQuery: (attemptId: string, sessionId?: string | null) => Promise<void>;
  isSubmitting: boolean;
  result: QueryResult | null;
  refinePrompt: RefinePrompt | null;
  evaluatorRejection: EvaluatorRejection | null;
  timeout: boolean;
  error: { kind: ErrorKind; resetAt?: string } | null;
  resetError: () => void;
  reset: () => void;
}

function isApiError(err: unknown): err is Record<string, unknown> {
  return err !== null && typeof err === 'object';
}

export const useQuerySubmit = (): UseQuerySubmitReturn => {
  const queryClient = useQueryClient();
  const canSubmitQuery = usePermission(PERMISSIONS.QUERY_SUBMIT);
  const setActiveSessionId = useUIStore((state) => state.setActiveSessionId);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [refinePrompt, setRefinePrompt] = useState<RefinePrompt | null>(null);
  const [evaluatorRejection, setEvaluatorRejection] = useState<EvaluatorRejection | null>(null);
  const [timeout, setTimeout] = useState(false);
  const [error, setError] = useState<{ kind: ErrorKind; resetAt?: string } | null>(null);
  const submittingRef = useRef(false);

  // One owned request scope per in-flight operation. Aborted requests suppress
  // frontend settlement only; the backend keeps authoritative semantics.
  const activeRequestRef = useRef<ActiveRequest | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      activeRequestRef.current?.scope.abort();
      activeRequestRef.current?.scope.dispose();
      activeRequestRef.current = null;
    };
  }, []);

  useEffect(() => {
    return subscribeToSessionDeletion((sessionId) => {
      const active = activeRequestRef.current;
      if (active && active.sessionId === sessionId) {
        active.scope.abort();
      }
    });
  }, []);

  const clearStates = useCallback(() => {
    setResult(null);
    setRefinePrompt(null);
    setEvaluatorRejection(null);
    setTimeout(false);
    setError(null);
  }, []);

  const resetError = useCallback(() => {
    setError(null);
    setEvaluatorRejection(null);
    setTimeout(false);
  }, []);

  const handleError = useCallback((err: unknown) => {
    if (!isApiError(err)) {
      setError({ kind: 'network' });
      return;
    }

    if ('violations' in err) {
      setEvaluatorRejection(err as EvaluatorRejection);
      return;
    }

    if ('kind' in err && err.kind === 'refine') {
      setRefinePrompt(err as RefinePrompt);
      return;
    }

    const messageKey = (err.message_key as string) || (err.detail as Record<string, unknown>)?.message_key as string;
    const errCode = (err.error as string) || (err.detail as Record<string, unknown>)?.error as string;

    if (messageKey === 'error.hostile_input_blocked' || errCode === 'hostile_input_blocked') {
      setError({ kind: 'hostileInputBlocked' });
      return;
    }

    if (messageKey === 'error.quota_exceeded' || errCode === 'quota_exceeded') {
      const resetAt = (err.reset_at as string) || (err.detail as Record<string, unknown>)?.reset_at as string;
      setError({ kind: 'quotaExceeded', resetAt });
      return;
    }

    if (messageKey === 'error.service_unavailable' || errCode === 'service_unavailable') {
      setError({ kind: 'serviceUnavailable' });
      return;
    }

    const code = err.error as string | undefined;
    if (code === 'concurrent') {
      setError({ kind: 'concurrent' });
    } else if (code === 'llm_unavailable') {
      setError({ kind: 'llmUnavailable' });
    } else if (code === 'attempt_invalid') {
      setError({ kind: 'attemptInvalid' });
    } else if (code === 'timeout') {
      setTimeout(true);
    } else {
      setError({ kind: 'network' });
    }
  }, []);

  const beginRequest = useCallback((sessionId: string | null): void => {
    if (submittingRef.current) {
      throw new Error('submit_in_progress');
    }
    submittingRef.current = true;
    setIsSubmitting(true);
    clearStates();
    const scope = new RequestScope({});
    activeRequestRef.current = { scope, sessionId };
  }, [clearStates]);

  const endRequest = useCallback(() => {
    activeRequestRef.current?.scope.dispose();
    activeRequestRef.current = null;
    submittingRef.current = false;
    setIsSubmitting(false);
  }, []);

  /**
   * Rethrows browser-side aborts as one typed silent failure regardless of
   * whether the abort came from this scope or the fetch boundary itself.
   * Server errors keep their payload and are additionally mapped into state.
   */
  const classifyFailure = useCallback(
    (err: unknown, scope?: DisposableRequestScope): never => {
      if ((scope && scope.aborted) || (!scope && isAbortFailure(err))) {
        throw (scope?.throwIfAborted() as Error | null) ?? new RequestAbortedError();
      }
      if (isAbortFailure(err)) {
        throw new RequestAbortedError();
      }
      handleError(err);
      throw err;
    },
    [handleError],
  );

  /**
   * Decides how a settled response must be suppressed, if at all. Deletion
   * keeps precedence over generic aborts so the CHUNK-03 SessionDeletionError
   * contract holds; other browser-side cancellations are typed silent aborts.
   */
  const classifySuppression = useCallback(
    (
      sessionId: string | null,
      deletionVersion: number,
      scope: DisposableRequestScope,
    ): 'none' | 'aborted' | 'deleted' => {
      if (
        sessionId &&
        (isSessionUnavailable(sessionId) || didSessionDeletionStart(sessionId, deletionVersion))
      ) {
        return 'deleted';
      }
      if (!mountedRef.current || scope.aborted) return 'aborted';
      return 'none';
    },
    [],
  );

  const submitQuestionFn = useCallback(async (q: string, sessionId?: string | null, connectionId?: string | null) => {
    requirePermission(canSubmitQuery, PERMISSIONS.QUERY_SUBMIT);
    if (!connectionId) {
      setError({ kind: 'connectionRequired' });
      throw new Error('connection_required');
    }
    if (sessionId && isSessionUnavailable(sessionId)) {
      throw new SessionDeletionError();
    }
    const deletionVersion = sessionId ? getSessionDeletionVersion(sessionId) : 0;
    beginRequest(sessionId ?? null);
    const scope = activeRequestRef.current!.scope;

    try {
      const res = await submitQuestion({
        body: { question: q, session_id: sessionId ?? undefined, connection_id: connectionId },
        throwOnError: true,
        signal: scope.signal,
      });
      const suppression = classifySuppression(sessionId ?? null, deletionVersion, scope);
      if (suppression === 'aborted') {
        clearStates();
        throw scope.throwIfAborted() ?? new RequestAbortedError();
      }
      if (suppression === 'deleted') {
        clearStates();
        throw new SessionDeletionError();
      }
      const data = res.data;
      if (data && typeof data === 'object' && 'kind' in data && data.kind === 'result') {
        const queryResult = data as QueryResult;
        setResult(queryResult);
        if (queryResult.session_id && queryResult.session_id !== sessionId) {
          setActiveSessionId(queryResult.session_id);
          queryClient.invalidateQueries({ queryKey: ['sessions'] });
        }
      }
      return data;
    } catch (err: unknown) {
      if (
        err instanceof SessionDeletionError ||
        (sessionId &&
          (isSessionUnavailable(sessionId) ||
            didSessionDeletionStart(sessionId, deletionVersion)))
      ) {
        clearStates();
        throw err instanceof SessionDeletionError ? err : new SessionDeletionError();
      }
      classifyFailure(err, scope);
    } finally {
      endRequest();
    }
  }, [beginRequest, canSubmitQuery, classifyFailure, clearStates, endRequest, setActiveSessionId, queryClient]);

  const rejectQueryFn = useCallback(async (attemptId: string) => {
    requirePermission(canSubmitQuery, PERMISSIONS.QUERY_SUBMIT);
    beginRequest(null);
    const scope = activeRequestRef.current!.scope;

    try {
      const res = await rejectQuery({ body: { attempt_id: attemptId }, throwOnError: true, signal: scope.signal });
      if (classifySuppression(null, 0, scope) === 'aborted') {
        clearStates();
        throw scope.throwIfAborted()!;
      }
      const data = res.data;
      if (data && typeof data === 'object' && 'kind' in data) {
        if (data.kind === 'result') {
          setResult(data as QueryResult);
        } else if (data.kind === 'refine') {
          setRefinePrompt(data as RefinePrompt);
        }
      }
    } catch (err: unknown) {
      classifyFailure(err, scope);
    } finally {
      endRequest();
    }
  }, [beginRequest, canSubmitQuery, classifyFailure, classifySuppression, clearStates, endRequest]);

  const regenerateQueryFn = useCallback(async (attemptId: string) => {
    requirePermission(canSubmitQuery, PERMISSIONS.QUERY_SUBMIT);
    beginRequest(null);
    const scope = activeRequestRef.current!.scope;

    try {
      const res = await regenerateQuery({ body: { attempt_id: attemptId }, throwOnError: true, signal: scope.signal });
      if (classifySuppression(null, 0, scope) === 'aborted') {
        clearStates();
        throw scope.throwIfAborted()!;
      }
      const data = res.data;
      if (data && typeof data === 'object' && 'kind' in data) {
        if (data.kind === 'result') {
          setResult(data as QueryResult);
        } else if (data.kind === 'refine') {
          setRefinePrompt(data as RefinePrompt);
        }
      }
      return data;
    } catch (err: unknown) {
      classifyFailure(err, scope);
    } finally {
      endRequest();
    }
  }, [beginRequest, canSubmitQuery, classifyFailure, classifySuppression, clearStates, endRequest]);

  const acceptQueryFn = useCallback(async (attemptId: string, sessionId?: string | null) => {
    requirePermission(canSubmitQuery, PERMISSIONS.QUERY_SUBMIT);
    beginRequest(sessionId ?? null);
    const scope = activeRequestRef.current!.scope;

    try {
      await acceptQuery({
        body: { attempt_id: attemptId, session_id: sessionId ?? undefined },
        throwOnError: true,
        signal: scope.signal,
      });
      if (classifySuppression(sessionId ?? null, 0, scope) === 'aborted') {
        clearStates();
        throw scope.throwIfAborted()!;
      }
    } catch (err: unknown) {
      classifyFailure(err, scope);
    } finally {
      endRequest();
    }
  }, [beginRequest, canSubmitQuery, classifyFailure, classifySuppression, clearStates, endRequest]);

  return {
    submitQuestion: submitQuestionFn,
    rejectQuery: rejectQueryFn,
    regenerateQuery: regenerateQueryFn,
    acceptQuery: acceptQueryFn,
    isSubmitting,
    result,
    refinePrompt,
    evaluatorRejection,
    timeout,
    error,
    resetError,
    reset: clearStates,
  };
};
