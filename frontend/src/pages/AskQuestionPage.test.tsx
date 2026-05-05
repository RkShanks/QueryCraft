import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { AskQuestionPage } from './AskQuestionPage';
import { createWrapper } from '../test/utils';
import { server } from '../test/server';
import { http, HttpResponse, delay } from 'msw';

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
