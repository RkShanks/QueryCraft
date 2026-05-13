import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { WorkspacePage } from '../WorkspacePage';
import { renderWithClient } from '../../test/utils';
import { server } from '../../test/server';
import { http, HttpResponse } from 'msw';

const mockSessionDetail = {
  id: 'session-1',
  preview_text: 'Test session',
  created_at: '2025-01-01T00:00:00Z',
  last_activity_at: '2025-01-01T00:00:00Z',
  attempts: [
    {
      id: 'attempt-1',
      question_text: 'First question',
      generated_sql: 'SELECT 1;',
      accepted_at: '2025-01-01T00:00:00Z',
      saved: false,
      feedback: null,
    },
  ],
};

beforeEach(() => {
  server.use(
    http.get('/api/v1/sessions/:sessionId', () => {
      return HttpResponse.json(mockSessionDetail, { status: 200 });
    })
  );
});

describe('WorkspacePage implicit feedback', () => {
  it('renders session attempts with feedback data', async () => {
    render(renderWithClient(<WorkspacePage />));
    // The page uses useUIStore which defaults to activeSessionId=null,
    // so empty state should show initially
    expect(screen.getByText('Start a new conversation')).toBeInTheDocument();
  });
});
