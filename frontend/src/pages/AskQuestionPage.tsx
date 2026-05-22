import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { QueryInput } from '../components/query/QueryInput';
import { ResultTable } from '../components/query/ResultTable';
import { EvaluatorRejectionBanner } from '../components/query/EvaluatorRejectionBanner';
import { RefinePromptBanner } from '../components/query/RefinePromptBanner';
import { TimeoutBanner } from '../components/query/TimeoutBanner';
import { useQuerySubmit } from '../hooks/useQuerySubmit';
import type { EvaluatorRejection } from '../api/generated/types.gen';
import { History, Database, AlertCircle, CheckCircle2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { listUserConnections } from '../api/generated/sdk.gen';

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

export const AskQuestionPage: React.FC = () => {
  const { t } = useTranslation();
  const [questionInput, setQuestionInput] = useState('');
  const lastSubmittedQuestionRef = useRef('');

  const [alert, setAlert] = useState<{
    id: string;
    title: string;
    description: string;
    variant: 'default' | 'destructive' | 'success';
  } | null>(null);

  const showAlert = React.useCallback((
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

  const {
    submitQuestion,
    rejectQuery,
    regenerateQuery,
    acceptQuery,
    isSubmitting,
    result,
    refinePrompt,
    evaluatorRejection,
    timeout,
    error,
    reset,
  } = useQuerySubmit();

  const { data: userConnectionsResponse } = useQuery({
    queryKey: ['userConnections'],
    queryFn: () => listUserConnections({ throwOnError: true }).then((res) => res.data),
  });

  const availableConnections = userConnectionsResponse?.connections ?? [];
  const connectionId = availableConnections[0]?.id ?? null;

  const handleQuestionSubmit = async (question: string) => {
    setQuestionInput(question);
    lastSubmittedQuestionRef.current = question;
    try {
      await submitQuestion(question, null, connectionId);
    } catch {
      // Error state is already managed by useQuerySubmit
    }
  };

  const handleAccept = async (id: string) => {
    try {
      await acceptQuery(id);
      showAlert(
        t('query.accept.success.title'),
        t('query.accept.success.message'),
        'success'
      );
    } catch {
      showAlert(
        t('query.error.accept.title'),
        t('query.error.accept.message'),
        'destructive'
      );
    }
  };

  const handleReject = async (id: string) => {
    try {
      await rejectQuery(id);
    } catch (err: unknown) {
      const e = err as { error?: string };
      if (e.error === 'concurrent') {
        showAlert(
          t('query.error.concurrent'),
          '',
          'destructive'
        );
      }
    }
  };

  const handleRegenerate = async (id: string) => {
    try {
      await regenerateQuery(id);
    } catch (err: unknown) {
      const e = err as { error?: string };
      if (e.error === 'concurrent') {
        showAlert(
          t('query.error.concurrent'),
          '',
          'destructive'
        );
      }
    }
  };

  const handleRefine = () => {
    setQuestionInput('');
    reset();
  };

  const handleRetry = () => {
    const q = lastSubmittedQuestionRef.current;
    if (q) {
      submitQuestion(q, null, connectionId);
    }
  };

  const shownErrorRef = useRef<string | null>(null);

  useEffect(() => {
    if (!error) {
      shownErrorRef.current = null;
      return;
    }
    const errorKey = error.kind;
    if (shownErrorRef.current === errorKey) return;
    shownErrorRef.current = errorKey;

    const timer = setTimeout(() => {
      if (error.kind === 'concurrent') {
        showAlert(
          t('query.error.concurrent'),
          '',
          'destructive'
        );
      } else if (error.kind === 'llmUnavailable') {
        showAlert(
          t('query.error.llmUnavailable'),
          '',
          'destructive'
        );
      } else if (error.kind === 'connectionRequired') {
        showAlert(
          t('error.no_database_available'),
          '',
          'destructive'
        );
      }
    }, 0);
    return () => clearTimeout(timer);
  }, [error, t, showAlert]);

  const alertStyles = {
    default: 'bg-gray-800 text-white',
    destructive: 'bg-red-600 text-white',
    success: 'bg-green-600 text-white',
  };

  return (
    <div className="ask-question-page min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b px-6 py-4 flex justify-between items-center shadow-sm sticky top-0 z-10">
        <div className="flex items-center gap-2">
          <Database className="w-6 h-6 text-indigo-600" />
          <h1 className="text-xl font-bold text-gray-900 tracking-tight">{t('app.title')}</h1>
        </div>
        <nav className="flex items-center gap-4">
          <Link
            to="/history"
            className="flex items-center gap-1.5 text-sm font-medium text-gray-600 hover:text-indigo-600 transition-colors"
          >
            <History className="w-4 h-4" />
            {t('nav.history')}
          </Link>
        </nav>
      </header>

      {alert && (
        <div
          role="alert"
          className={`fixed top-4 inset-x-4 md:inset-x-auto md:end-4 md:w-96 z-50 p-4 rounded-md shadow-lg flex items-start gap-3 ${alertStyles[alert.variant]}`}
        >
          {alert.variant === 'success' && <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" />}
          {alert.variant === 'destructive' && <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />}
          <div className="flex-1">
            <p className="font-semibold text-sm">{alert.title}</p>
            {alert.description && <p className="text-sm opacity-90">{alert.description}</p>}
          </div>
          <button
            onClick={() => setAlert(null)}
            className="text-current opacity-70 hover:opacity-100"
            aria-label={t('common.close')}
          >
            ×
          </button>
        </div>
      )}

      <main className="flex-1 max-w-5xl w-full mx-auto p-6 md:p-10 flex flex-col gap-8">
        <section className="bg-white p-8 rounded-2xl shadow-sm border border-gray-100 transition-all hover:shadow-md">
          <h2 className="text-lg font-semibold mb-4 text-gray-800">
            {t('query.ask.title')}
          </h2>
          <QueryInput
            onSubmit={handleQuestionSubmit}
            isSubmitting={isSubmitting}
            value={questionInput}
            onChange={setQuestionInput}
          />
        </section>

        {isSubmitting && (
          <div className="flex flex-col items-center justify-center py-12 animate-pulse">
            <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mb-4"></div>
            <p className="text-gray-500 font-medium">
              {t('query.status.processing')}
            </p>
          </div>
        )}

        {evaluatorRejection && !isSubmitting && (
          <section className="animate-in fade-in slide-in-from-bottom-6 duration-700">
            <EvaluatorRejectionBanner
              {...mapEvaluatorRejection(evaluatorRejection)}
            />
          </section>
        )}

        {timeout && !isSubmitting && (
          <section className="animate-in fade-in slide-in-from-bottom-6 duration-700">
            <TimeoutBanner timeout={timeout} onRetry={handleRetry} />
          </section>
        )}

        {refinePrompt && !isSubmitting && (
          <section className="animate-in fade-in slide-in-from-bottom-6 duration-700">
            <RefinePromptBanner
              refinePrompt={{
                reason:
                  refinePrompt.message_key === 'query.refine.message'
                    ? 'max_retries'
                    : 'evaluator_blocked',
              }}
              onRefine={handleRefine}
            />
          </section>
        )}

        {result && !isSubmitting && result.kind === 'result' && (
          <section className="animate-in fade-in slide-in-from-bottom-6 duration-700">
            <ResultTable
              result={result}
              onAccept={handleAccept}
              isAccepting={isSubmitting}
              onReject={handleReject}
              onRegenerate={handleRegenerate}
              canRegenerate={!result.is_last_auto_retry}
            />
          </section>
        )}
      </main>
    </div>
  );
};
