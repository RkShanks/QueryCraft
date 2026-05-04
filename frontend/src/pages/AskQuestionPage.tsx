import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { QueryInput } from '../components/query/QueryInput';
import { ResultTable } from '../components/query/ResultTable';
import { 
  useSubmitQuestion, 
  useAcceptQuery, 
  useRejectQuery, 
  useRegenerateQuery 
} from '../hooks/useQuerySubmit';
import type { QueryResult, RefinePrompt } from '../api/generated/types.gen';
import { 
  ToastProvider, 
  ToastViewport, 
  Toast, 
  ToastTitle, 
  ToastDescription, 
  ToastClose 
} from '../components/ui/Toast';
import { History, Database, AlertCircle, CheckCircle2 } from 'lucide-react';
import { Link } from 'react-router-dom';

export const AskQuestionPage: React.FC = () => {
  const { t } = useTranslation();
  const [result, setResult] = useState<QueryResult | null>(null);
  const [refinePrompt, setRefinePrompt] = useState<RefinePrompt | null>(null);
  const [toasts, setToasts] = useState<{ id: string; title: string; description: string; variant: 'default' | 'destructive' | 'success' }[]>([]);

  const addToast = (title: string, description: string, variant: 'default' | 'destructive' | 'success' = 'default') => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, title, description, variant }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  };

  const submitMutation = useSubmitQuestion();
  const acceptMutation = useAcceptQuery();
  const rejectMutation = useRejectQuery();
  const regenMutation = useRegenerateQuery();

  const handleQuestionSubmit = async (question: string) => {
    setResult(null);
    setRefinePrompt(null);
    try {
      const data = await submitMutation.mutateAsync({ question });
      setResult(data as QueryResult);
    } catch (error: unknown) {
      const err = error as { status?: number; error?: string; response?: { status?: number } };
      if (err.error === 'evaluator_rejection' || err.status === 422 || err.response?.status === 422) {
        addToast(
          t('error.evaluator.title', { defaultValue: 'Evaluator Rejected' }),
          t('error.evaluator.message', { defaultValue: 'The generated SQL was rejected by safety rules.' }),
          'destructive'
        );
      } else {
        addToast(
          t('error.unknown.title', { defaultValue: 'Error' }),
          t('error.unknown.message', { defaultValue: 'An unexpected error occurred.' }),
          'destructive'
        );
      }
    }
  };

  const handleAccept = async (id: string) => {
    try {
      await acceptMutation.mutateAsync({ attempt_id: id });
      addToast(
        t('query.accept.success.title', { defaultValue: 'Success' }),
        t('query.accept.success.message', { defaultValue: 'Query accepted and saved to history.' }),
        'success'
      );
      setResult(null);
    } catch {
      addToast(
        t('error.accept.title', { defaultValue: 'Error' }),
        t('error.accept.message', { defaultValue: 'Failed to accept query.' }),
        'destructive'
      );
    }
  };

  const handleReject = async (id: string) => {
    try {
      const data = await rejectMutation.mutateAsync({ attempt_id: id });
      if (data.kind === 'result') {
        setResult(data as QueryResult);
        addToast(
          t('query.reject.retry.title', { defaultValue: 'Retried' }),
          t('query.reject.retry.message', { defaultValue: 'SQL regenerated after rejection.' }),
          'default'
        );
      } else {
        setRefinePrompt(data as RefinePrompt);
        setResult(null);
      }
    } catch {
      addToast(t('error.reject.title', { defaultValue: 'Error' }), t('error.reject.message', { defaultValue: 'Failed to reject query.' }), 'destructive');
    }
  };

  const handleRegenerate = async (id: string) => {
    try {
      const data = await regenMutation.mutateAsync({ attempt_id: id });
      if (data.kind === 'result') {
        setResult(data as QueryResult);
        addToast(t('query.regen.success.title', { defaultValue: 'Success' }), t('query.regen.message', { defaultValue: 'SQL regenerated.' }), 'success');
      } else {
        setRefinePrompt(data as RefinePrompt);
        setResult(null);
      }
    } catch {
      addToast(t('error.regen.title', { defaultValue: 'Error' }), t('error.regen.message', { defaultValue: 'Failed to regenerate query.' }), 'destructive');
    }
  };

  return (
    <ToastProvider>
      <div className="ask-question-page min-h-screen bg-gray-50 flex flex-col">
        <header className="bg-white border-b px-6 py-4 flex justify-between items-center shadow-sm sticky top-0 z-10">
          <div className="flex items-center gap-2">
            <Database className="w-6 h-6 text-indigo-600" />
            <h1 className="text-xl font-bold text-gray-900 tracking-tight">QueryCraft</h1>
          </div>
          <nav className="flex items-center gap-4">
            <Link 
              to="/history" 
              className="flex items-center gap-1.5 text-sm font-medium text-gray-600 hover:text-indigo-600 transition-colors"
            >
              <History className="w-4 h-4" />
              {t('nav.history', { defaultValue: 'History' })}
            </Link>
          </nav>
        </header>

        <main className="flex-1 max-w-5xl w-full mx-auto p-6 md:p-10 flex flex-col gap-8">
          <section className="bg-white p-8 rounded-2xl shadow-sm border border-gray-100 transition-all hover:shadow-md">
            <h2 className="text-lg font-semibold mb-4 text-gray-800">
              {t('query.ask.title', { defaultValue: 'What would you like to know?' })}
            </h2>
            <QueryInput 
              onSubmit={handleQuestionSubmit} 
              isSubmitting={submitMutation.isPending} 
            />
          </section>

          {submitMutation.isPending && (
            <div className="flex flex-col items-center justify-center py-12 animate-pulse">
              <div className="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mb-4"></div>
              <p className="text-gray-500 font-medium">
                {t('query.status.processing', { defaultValue: 'Analyzing your question...' })}
              </p>
            </div>
          )}

          {result && !submitMutation.isPending && (
            <section className="animate-in fade-in slide-in-from-bottom-6 duration-700">
              <ResultTable 
                result={result} 
                onAccept={handleAccept}
                onReject={handleReject}
                onRegenerate={handleRegenerate}
                isAccepting={acceptMutation.isPending}
              />
            </section>
          )}

          {refinePrompt && !submitMutation.isPending && (
            <section className="bg-amber-50 border border-amber-200 p-6 rounded-xl animate-in fade-in zoom-in-95 duration-500">
              <div className="flex gap-3">
                <AlertCircle className="w-6 h-6 text-amber-600 shrink-0" />
                <div>
                  <h3 className="font-bold text-amber-900">
                    {t('query.refine.title', { defaultValue: 'Clarification Needed' })}
                  </h3>
                  <p className="text-amber-800 mt-1">
                    {t(refinePrompt.message_key, { defaultValue: 'Please provide more details.' })}
                  </p>
                </div>
              </div>
            </section>
          )}
        </main>

        {toasts.map((toast) => (
          <Toast key={toast.id} variant={toast.variant} open={true}>
            <div className="grid gap-1">
              <ToastTitle className="flex items-center gap-2">
                {toast.variant === 'success' && <CheckCircle2 className="w-4 h-4" />}
                {toast.variant === 'destructive' && <AlertCircle className="w-4 h-4" />}
                {toast.title}
              </ToastTitle>
              <ToastDescription>{toast.description}</ToastDescription>
            </div>
            <ToastClose />
          </Toast>
        ))}
        <ToastViewport />
      </div>
    </ToastProvider>
  );
};
