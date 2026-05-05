import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
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
    
    // Toast might take a moment to appear
    expect(await screen.findByText(/evaluator rejected/i)).toBeInTheDocument();
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
      expect(screen.getByText('query.evaluatorRejection.heading')).toBeInTheDocument();
    });
    expect(screen.queryByText(/generated sql/i)).not.toBeInTheDocument();
  });

  it('shows TimeoutBanner on timeout submit', async () => {
    setSubmitScenario('timeout');
    render(<AskQuestionPage />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: 'Slow query' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('query.timeout.heading')).toBeInTheDocument();
    });
  });

  it('shows concurrent error toast on 409', async () => {
    setSubmitScenario('concurrent');
    render(<AskQuestionPage />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: 'Concurrent query' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));

    await waitFor(() => {
      expect(screen.getByText(/concurrent/i)).toBeInTheDocument();
    });
  });

  it('shows LLM unavailable toast on 502', async () => {
    setSubmitScenario('llm_unavailable');
    render(<AskQuestionPage />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: 'Any query' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));

    await waitFor(() => {
      expect(screen.getByText(/unavailable/i)).toBeInTheDocument();
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
      expect(screen.getByText('query.refine.heading')).toBeInTheDocument();
    });
  });

  it('new submit clears all banners', async () => {
    setSubmitScenario('evaluator_rejected');
    render(<AskQuestionPage />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: 'Unsafe' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));

    await waitFor(() => {
      expect(screen.getByText('query.evaluatorRejection.heading')).toBeInTheDocument();
    });

    setSubmitScenario('result');
    fireEvent.change(textarea, { target: { value: 'Safe query' } });
    fireEvent.click(screen.getByRole('button', { name: /ask/i }));

    await waitFor(() => {
      expect(screen.queryByText('query.evaluatorRejection.heading')).not.toBeInTheDocument();
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
      expect(screen.getByText('query.refine.heading')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /try refining/i }));

    await waitFor(() => {
      expect(screen.queryByText('query.refine.heading')).not.toBeInTheDocument();
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
      expect(screen.getByText('query.timeout.heading')).toBeInTheDocument();
    });

    setSubmitScenario('result');
    fireEvent.click(screen.getByRole('button', { name: /try again/i }));

    await waitFor(() => {
      expect(screen.queryByText('query.timeout.heading')).not.toBeInTheDocument();
      expect(screen.getByText(/generated sql/i)).toBeInTheDocument();
    });
  });
});
