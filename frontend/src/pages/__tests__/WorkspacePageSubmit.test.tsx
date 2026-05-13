import { describe, it, expect, beforeEach } from 'vitest';
import { screen, waitFor, act, fireEvent } from '@testing-library/react';
import { WorkspacePage } from '../WorkspacePage';
import { renderWithClient } from '../../test/utils';
import { useUIStore } from '../../stores/uiStore';
import { setSubmitScenario } from '../../test/handlers';

beforeEach(() => {
  useUIStore.setState({
    activeSessionId: null,
    sidebarCollapsed: false,
    hoveredSessionId: null,
    promptDraft: '',
  });
});

async function typeAndSubmit(text: string): Promise<void> {
  const input = screen.getByRole('textbox');
  fireEvent.change(input, { target: { value: text } });
  fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });
}

describe('WorkspacePage first-submit UX', () => {
  it('renders empty state when no active session', () => {
    renderWithClient(<WorkspacePage />);
    expect(screen.getByText('Start a new conversation')).toBeInTheDocument();
  });

  it('preserves the submitted turn after first submit creates a new session', async () => {
    renderWithClient(<WorkspacePage />);

    expect(screen.getByText('Start a new conversation')).toBeInTheDocument();

    await typeAndSubmit('How many actors?');

    await waitFor(() => {
      expect(screen.getByTestId('assistant-loading')).toBeInTheDocument();
    });

    expect(screen.getByText('How many actors?')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId('assistant-response-card')).toBeInTheDocument();
    });

    expect(screen.queryByText('Start a new conversation')).not.toBeInTheDocument();

    const state = useUIStore.getState();
    expect(state.activeSessionId).toBe('550e8400-e29b-41d4-a716-446655440003');
  }, 10000);

  it('clears local turns on New Chat (activeSessionId set to null)', async () => {
    renderWithClient(<WorkspacePage />);

    await typeAndSubmit('Some question?');

    await waitFor(() => {
      expect(screen.getByTestId('assistant-response-card')).toBeInTheDocument();
    }, { timeout: 5000 });

    await act(async () => {
      useUIStore.getState().setActiveSessionId(null);
    });

    await waitFor(() => {
      expect(screen.getByText('Start a new conversation')).toBeInTheDocument();
    }, { timeout: 5000 });
  }, 15000);

  it('passes result.attempt_id to AssistantResponseCard for feedback/regenerate', async () => {
    renderWithClient(<WorkspacePage />);

    await typeAndSubmit('How many actors?');

    await waitFor(() => {
      expect(screen.getByTestId('assistant-response-card')).toBeInTheDocument();
    }, { timeout: 5000 });

    const sendBtn = screen.getByTestId('prompt-send');
    expect(sendBtn).toBeDisabled();
  }, 10000);

  it('second submit (follow-up) in same session preserves both turns', async () => {
    renderWithClient(<WorkspacePage />);

    await typeAndSubmit('First question?');

    await waitFor(() => {
      expect(screen.getAllByTestId('assistant-response-card')).toHaveLength(1);
    }, { timeout: 5000 });

    await typeAndSubmit('Second question?');

    await waitFor(() => {
      expect(screen.getAllByTestId('assistant-response-card')).toHaveLength(2);
    }, { timeout: 5000 });

    expect(screen.getByText('First question?')).toBeInTheDocument();
    expect(screen.getByText('Second question?')).toBeInTheDocument();

    expect(screen.queryByText('Start a new conversation')).not.toBeInTheDocument();
  }, 15000);
});

describe('WorkspacePage submit scenarios', () => {
  it('shows evaluator rejection card when evaluator rejects', async () => {
    setSubmitScenario('evaluator_rejected');
    renderWithClient(<WorkspacePage />);

    await typeAndSubmit('Bad query?');

    await waitFor(() => {
      expect(screen.getByTestId('rejection-banner')).toBeInTheDocument();
    }, { timeout: 5000 });
  }, 10000);
});
