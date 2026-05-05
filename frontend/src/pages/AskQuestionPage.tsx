import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { QueryInput } from '../components/query/QueryInput';
import { ResultTable } from '../components/query/ResultTable';
import { 
  useSubmitQuestion, 
  useAcceptQuery 
} from '../hooks/useQuerySubmit';
import type { QueryResult } from '../api/generated/types.gen';
import { History, Database, AlertCircle, CheckCircle2 } from 'lucide-react';
import { Link } from 'react-router-dom';

export const AskQuestionPage: React.FC = () => {
  const { t } = useTranslation();
  const [result, setResult] = useState<QueryResult | null>(null);
  const [alert, setAlert] = useState<{ id: string; title: string; description: string; variant: 'default' | 'destructive' | 'success' } | null>(null);

  const showAlert = (title: string, description: string, variant: 'default' | 'destructive' | 'success' = 'default') => {
    const id = Math.random().toString(36).substring(2, 9);
    setAlert({ id, title, description, variant });
    setTimeout(() => {
      setAlert((prev) => (prev?.id === id ? null : prev));
    }, 5000);
  };

  const submitMutation = useSubmitQuestion();
  const acceptMutation = useAcceptQuery();

  const handleQuestionSubmit = async (question: string) => {
    setResult(null);
    try {
      const data = await submitMutation.mutateAsync({ question });
      setResult(data as QueryResult);
    } catch (error: unknown) {
      const err = error as { status?: number; error?: string; response?: { status?: number } };
      if (err.error === 'evaluator_rejection' || err.status === 422 || err.response?.status === 422) {
        showAlert(
          t('error.evaluator.title', { defaultValue: 'Evaluator Rejected' }),
          t('error.evaluator.message', { defaultValue: 'The generated SQL was rejected by safety rules.' }),
          'destructive'
        );
      } else {
        showAlert(
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
      showAlert(
        t('query.accept.success.title', { defaultValue: 'Success' }),
        t('query.accept.success.message', { defaultValue: 'Query accepted and saved to history.' }),
        'success'
      );
      setResult(null);
    } catch {
      showAlert(
        t('error.accept.title', { defaultValue: 'Error' }),
        t('error.accept.message', { defaultValue: 'Failed to accept query.' }),
        'destructive'
      );
    }
  };

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

      {alert && (
        <div 
          role="alert" 
          className={`fixed top-4 inset-x-4 md:inset-x-auto md:right-4 md:w-96 z-50 p-4 rounded-md shadow-lg flex items-start gap-3 ${alertStyles[alert.variant]}`}
        >
          {alert.variant === 'success' && <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" />}
          {alert.variant === 'destructive' && <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />}
          <div className="flex-1">
            <p className="font-semibold text-sm">{alert.title}</p>
            <p className="text-sm opacity-90">{alert.description}</p>
          </div>
          <button 
            onClick={() => setAlert(null)}
            className="text-current opacity-70 hover:opacity-100"
            aria-label={t('common.close', { defaultValue: 'Close' })}
          >
            ×
          </button>
        </div>
      )}

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
              isAccepting={acceptMutation.isPending}
            />
          </section>
        )}
      </main>
    </div>
  );
};
