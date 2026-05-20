import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';

const mockUseQuerySubmitState = vi.hoisted(() => ({ enabled: true }));

vi.mock('../hooks/useQuerySubmit', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../hooks/useQuerySubmit')>();
  return {
    ...actual,
    useQuerySubmit: () => {
      if (!mockUseQuerySubmitState.enabled) {
        return actual.useQuerySubmit();
      }
      const hook = actual.useQuerySubmit();
      return {
        ...hook,
        submitQuestion: (q: string, sessionId?: string | null, connectionId?: string | null) =>
          hook.submitQuestion(q, sessionId, connectionId || '550e8400-e29b-41d4-a716-446655440001'),
      };
    },
  };
});

import { AskQuestionPage } from './AskQuestionPage';
import { createWrapper } from '../test/utils';
import { server } from '../test/server';
import { http, HttpResponse, delay } from 'msw';
import {
  setSubmitScenario,
  setRejectScenario,
  setRegenerateScenario,
  resetQueryScenarios,
} from '../test/handlers';

describe('AskQuestionPage Integration', () => {
  it('should allow asking a question and displaying results', async () => {
    server.use(
      http.post('/api/v1/query/submit', async () => {
        await delay(50);
        return HttpResponse.json({
          kind: 'result',
          attempt_id: 'test-id',
          generated_sql: 'SELECT * FROM users;',
          columns: [{ name: 'id', type: 'integer' }],
          rows: [['1']],
          row_count: 1,
          question: 'How many users?',
          attempt_number: 1,
          is_last_auto_retry: false,
        });
      })
    );

    render(<AskQuestionPage />, { wrapper: createWrapper() });
    
    const textarea = screen.getByPlaceholderText(/ask a question/i);

    fireEvent.change(textarea, { target: { value: 'DROP TABLE users;' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));
    
    // Wait for result
    await waitFor(() => {
      expect(screen.getByText(/generated sql/i)).toBeInTheDocument();
    }, { timeout: 3000 });
    
    expect(screen.getByText(/select \* from users/i)).toBeInTheDocument();
  });

  it('should handle evaluator rejection', async () => {
    server.use(
      http.post('/api/v1/query/submit', () => {
        return HttpResponse.json({
          error: 'evaluator_rejection',
          message_key: 'query.evaluator.rejected',
          violations: [{ rule: 'read_only', message_key: 'evaluator.violation.dataModifying' }]
        }, { status: 422 });
      })
    );

    render(<AskQuestionPage />, { wrapper: createWrapper() });
    
    const textarea = screen.getByPlaceholderText(/ask a question/i);
    
    fireEvent.change(textarea, { target: { value: 'DROP TABLE users;' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));
    
    // Banner should appear
    expect(await screen.findByText(/generated sql was rejected for safety/i)).toBeInTheDocument();
  });

  it('should handle successful acceptance', async () => {
    render(<AskQuestionPage />, { wrapper: createWrapper() });
    
    // First get a result
    const textarea = screen.getByPlaceholderText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: 'How many users?' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));
    
    const acceptBtn = await screen.findByRole('button', { name: /accept/i });
    fireEvent.click(acceptBtn);
    
    expect(await screen.findByText(/query accepted/i)).toBeInTheDocument();
  });

  it('shows no database available alert when submitting without connectionId (T-461 regression)', async () => {
    mockUseQuerySubmitState.enabled = false;
    render(<AskQuestionPage />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: 'How many users?' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));

    await waitFor(() => {
      expect(screen.getByText(/no database available/i)).toBeInTheDocument();
    });

    mockUseQuerySubmitState.enabled = true;
  });
});

describe('AskQuestionPage US-2 State Machine', () => {
  afterEach(() => {
    resetQueryScenarios();
  });

  it('shows ResultTable on successful submit', async () => {
    render(<AskQuestionPage />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: 'How many users?' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));

    await waitFor(() => {
      expect(screen.getByText(/generated sql/i)).toBeInTheDocument();
    });
  });

  it('shows EvaluatorRejectionBanner and hides ResultTable on evaluator rejected', async () => {
    setSubmitScenario('evaluator_rejected');
    render(<AskQuestionPage />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: 'Unsafe query' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/generated sql was rejected for safety/i)).toBeInTheDocument();
    });
    expect(screen.queryByText('Generated SQL')).not.toBeInTheDocument();
  });

  it('shows TimeoutBanner on timeout submit', async () => {
    setSubmitScenario('timeout');
    render(<AskQuestionPage />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: 'Slow query' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/query took too long/i)).toBeInTheDocument();
    });
  });

  it('shows concurrent error toast on 409', async () => {
    setSubmitScenario('concurrent');
    render(<AskQuestionPage />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: 'Concurrent query' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));

    await waitFor(() => {
      expect(screen.getByText(/already being processed/i)).toBeInTheDocument();
    });
  });

  it('shows LLM unavailable toast on 502', async () => {
    setSubmitScenario('llm_unavailable');
    render(<AskQuestionPage />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: 'Any query' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));

    await waitFor(() => {
      expect(screen.getByText(/temporarily unavailable/i)).toBeInTheDocument();
    });
  });

  it('clicking Reject returns new ResultTable on success', async () => {
    render(<AskQuestionPage />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: 'How many users?' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));

    await waitFor(() => {
      expect(screen.getByText(/generated sql/i)).toBeInTheDocument();
    });

    setRejectScenario('result');
    fireEvent.click(screen.getByRole('button', { name: /reject/i }));

    await waitFor(() => {
      expect(screen.getByText(/generated sql/i)).toBeInTheDocument();
    });
  });

  it('clicking Regenerate returns new ResultTable on success', async () => {
    render(<AskQuestionPage />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: 'How many users?' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));

    await waitFor(() => {
      expect(screen.getByText(/generated sql/i)).toBeInTheDocument();
    });

    setRegenerateScenario('result');
    fireEvent.click(screen.getByRole('button', { name: /regenerate/i }));

    await waitFor(() => {
      expect(screen.getByText(/generated sql/i)).toBeInTheDocument();
    });
  });

  it('double-reject shows RefinePromptBanner', async () => {
    render(<AskQuestionPage />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: 'How many users?' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));

    await waitFor(() => {
      expect(screen.getByText(/generated sql/i)).toBeInTheDocument();
    });

    setRejectScenario('result');
    fireEvent.click(screen.getByRole('button', { name: /reject/i }));

    await waitFor(() => {
      expect(screen.getByText(/generated sql/i)).toBeInTheDocument();
    });

    setRejectScenario('refine');
    fireEvent.click(screen.getByRole('button', { name: /reject/i }));

    await waitFor(() => {
      expect(screen.getByText(/please refine your question/i)).toBeInTheDocument();
    });
  });

  it('new submit clears all banners', async () => {
    setSubmitScenario('evaluator_rejected');
    render(<AskQuestionPage />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: 'Unsafe' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));

    await waitFor(() => {
      expect(screen.getByText(/generated sql was rejected for safety/i)).toBeInTheDocument();
    });

    setSubmitScenario('result');
    fireEvent.change(textarea, { target: { value: 'Safe query' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));

    await waitFor(() => {
      expect(screen.queryByText(/generated sql was rejected for safety/i)).not.toBeInTheDocument();
      expect(screen.getByText(/generated sql/i)).toBeInTheDocument();
    });
  });

  it('Try Refining CTA resets input and clears banners', async () => {
    render(<AskQuestionPage />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText(/ask a question/i) as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'How many?' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));

    await waitFor(() => {
      expect(screen.getByText(/generated sql/i)).toBeInTheDocument();
    });

    setRejectScenario('refine');
    fireEvent.click(screen.getByRole('button', { name: /reject/i }));

    await waitFor(() => {
      expect(screen.getByText(/please refine your question/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /try refining/i }));

    await waitFor(() => {
      expect(screen.queryByText(/please refine your question/i)).not.toBeInTheDocument();
      expect(textarea.value).toBe('');
    });
  });

  it('Try Again CTA in TimeoutBanner re-submits', async () => {
    setSubmitScenario('timeout');
    render(<AskQuestionPage />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: 'Slow query' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));

    await waitFor(() => {
      expect(screen.getByText(/query took too long/i)).toBeInTheDocument();
    });

    setSubmitScenario('result');
    fireEvent.click(screen.getByRole('button', { name: /try again/i }));

    await waitFor(() => {
      expect(screen.queryByText(/query took too long/i)).not.toBeInTheDocument();
      expect(screen.getByText(/generated sql/i)).toBeInTheDocument();
    });
  });
});
