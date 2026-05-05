import { useState, useCallback, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { submitQuestion, acceptQuery, listHistory, rejectQuery, regenerateQuery } from '../api/generated/sdk.gen';
import type { SubmitQuestionData, AcceptQueryData, RejectQueryData, RegenerateQueryData } from '../api/generated/types.gen';
import type { QueryResult, RefinePrompt, EvaluatorRejection } from '../api/generated/types.gen';

export const useSubmitQuestion = () => {
  return useMutation({
    mutationFn: (data: SubmitQuestionData['body']) => submitQuestion({ body: data, throwOnError: true }).then(res => res.data),
  });
};

export const useAcceptQuery = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: AcceptQueryData['body']) => acceptQuery({ body: data, throwOnError: true }).then(res => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['history'] });
    },
  });
};

export const useHistory = () => {
  return useQuery({
    queryKey: ['history'],
    queryFn: () => listHistory({ throwOnError: true }).then(res => res.data),
  });
};

type ErrorKind = 'concurrent' | 'llmUnavailable' | 'attemptInvalid' | 'network';

export interface UseQuerySubmitReturn {
  submitQuestion: (q: string) => Promise<void>;
  rejectQuery: (attemptId: string) => Promise<void>;
  regenerateQuery: (attemptId: string) => Promise<void>;
  acceptQuery: (attemptId: string) => Promise<void>;
  isSubmitting: boolean;
  result: QueryResult | null;
  refinePrompt: RefinePrompt | null;
  evaluatorRejection: EvaluatorRejection | null;
  timeout: boolean;
  error: { kind: ErrorKind } | null;
  resetError: () => void;
}

function isApiError(err: unknown): err is Record<string, unknown> {
  return err !== null && typeof err === 'object';
}

export const useQuerySubmit = (): UseQuerySubmitReturn => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [refinePrompt, setRefinePrompt] = useState<RefinePrompt | null>(null);
  const [evaluatorRejection, setEvaluatorRejection] = useState<EvaluatorRejection | null>(null);
  const [timeout, setTimeout] = useState(false);
  const [error, setError] = useState<{ kind: ErrorKind } | null>(null);
  const submittingRef = useRef(false);

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

  const submitQuestionFn = useCallback(async (q: string) => {
    if (submittingRef.current) {
      throw new Error('submit_in_progress');
    }
    submittingRef.current = true;
    setIsSubmitting(true);
    clearStates();

    try {
      const res = await submitQuestion({ body: { question: q }, throwOnError: true });
      const data = res.data;
      if (data && typeof data === 'object' && 'kind' in data && data.kind === 'result') {
        setResult(data as QueryResult);
      }
    } catch (err: unknown) {
      handleError(err);
      throw err;
    } finally {
      submittingRef.current = false;
      setIsSubmitting(false);
    }
  }, [clearStates, handleError]);

  const rejectQueryFn = useCallback(async (attemptId: string) => {
    if (submittingRef.current) {
      throw new Error('submit_in_progress');
    }
    submittingRef.current = true;
    setIsSubmitting(true);
    clearStates();

    try {
      const res = await rejectQuery({ body: { attempt_id: attemptId }, throwOnError: true });
      const data = res.data;
      if (data && typeof data === 'object' && 'kind' in data) {
        if (data.kind === 'result') {
          setResult(data as QueryResult);
        } else if (data.kind === 'refine') {
          setRefinePrompt(data as RefinePrompt);
        }
      }
    } catch (err: unknown) {
      handleError(err);
      throw err;
    } finally {
      submittingRef.current = false;
      setIsSubmitting(false);
    }
  }, [clearStates, handleError]);

  const regenerateQueryFn = useCallback(async (attemptId: string) => {
    if (submittingRef.current) {
      throw new Error('submit_in_progress');
    }
    submittingRef.current = true;
    setIsSubmitting(true);
    clearStates();

    try {
      const res = await regenerateQuery({ body: { attempt_id: attemptId }, throwOnError: true });
      const data = res.data;
      if (data && typeof data === 'object' && 'kind' in data) {
        if (data.kind === 'result') {
          setResult(data as QueryResult);
        } else if (data.kind === 'refine') {
          setRefinePrompt(data as RefinePrompt);
        }
      }
    } catch (err: unknown) {
      handleError(err);
      throw err;
    } finally {
      submittingRef.current = false;
      setIsSubmitting(false);
    }
  }, [clearStates, handleError]);

  const acceptQueryFn = useCallback(async (attemptId: string) => {
    if (submittingRef.current) {
      throw new Error('submit_in_progress');
    }
    submittingRef.current = true;
    setIsSubmitting(true);
    clearStates();

    try {
      await acceptQuery({ body: { attempt_id: attemptId }, throwOnError: true });
    } catch (err: unknown) {
      handleError(err);
      throw err;
    } finally {
      submittingRef.current = false;
      setIsSubmitting(false);
    }
  }, [clearStates, handleError]);

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
  };
};
