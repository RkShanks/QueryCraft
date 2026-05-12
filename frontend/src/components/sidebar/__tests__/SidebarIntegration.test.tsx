import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { Sidebar } from '../Sidebar';
import { useUIStore } from '../../../stores/uiStore';
import { createWrapper } from '../../../test/utils';

const mockSessions = [
  {
    id: 'sess-1',
    preview_text: 'First session',
    created_at: new Date().toISOString(),
    last_activity_at: new Date().toISOString(),
  },
  {
    id: 'sess-2',
    preview_text: 'Second session',
    created_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    last_activity_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
  },
];

vi.mock('../../../hooks/useSessions', () => ({
  useSessionsList: vi.fn(),
  useDeleteSession: vi.fn(),
}));

import { useSessionsList, useDeleteSession } from '../../../hooks/useSessions';

const mockMutate = vi.fn();

function setup(sessions = mockSessions) {
  (useSessionsList as ReturnType<typeof vi.fn>).mockReturnValue({
    data: { items: sessions, total: sessions.length },
    isLoading: false,
  });
  (useDeleteSession as ReturnType<typeof vi.fn>).mockReturnValue({
    mutate: mockMutate,
  });
  return render(<Sidebar />, { wrapper: createWrapper() });
}

describe('Sidebar Integration', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    useUIStore.getState().setActiveSessionId('sess-1');
    if (useUIStore.getState().sidebarCollapsed) {
      useUIStore.getState().toggleSidebar();
    }
    mockMutate.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('New Chat clears workspace (resets activeSessionId to null)', () => {
    setup();
    expect(useUIStore.getState().activeSessionId).toBe('sess-1');

    const newChatBtn = screen.getByTestId('sidebar-new-chat');
    fireEvent.click(newChatBtn);

    expect(useUIStore.getState().activeSessionId).toBeNull();
  });

  it('delete → undo → restore flow: clicking undo prevents DELETE API call', () => {
    setup();

    // Click delete on first session
    const deleteBtn = screen.getByTestId('session-delete-sess-1');
    fireEvent.click(deleteBtn);

    // Toast should appear
    expect(screen.getByText(/delete session/i)).toBeInTheDocument();

    // Click undo
    const undoBtn = screen.getByText('Undo');
    fireEvent.click(undoBtn);

    // Advance past 5s
    act(() => {
      vi.advanceTimersByTime(6000);
    });

    // DELETE should never have been called
    expect(mockMutate).not.toHaveBeenCalled();

    // Toast should be gone
    expect(screen.queryByText(/delete session/i)).not.toBeInTheDocument();
  });

  it('delete → expiry → DELETE API is called', () => {
    setup();

    // Click delete on first session
    const deleteBtn = screen.getByTestId('session-delete-sess-1');
    fireEvent.click(deleteBtn);

    // Toast should appear
    expect(screen.getByText(/delete session/i)).toBeInTheDocument();

    // Let timer expire
    act(() => {
      vi.advanceTimersByTime(5000);
    });

    // DELETE should have been called
    expect(mockMutate).toHaveBeenCalledTimes(1);
    expect(mockMutate).toHaveBeenCalledWith('sess-1');

    // Toast should be gone after expiry callback
    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(screen.queryByText(/delete session/i)).not.toBeInTheDocument();
  });

  it('multiple delete toasts stack', () => {
    setup();

    fireEvent.click(screen.getByTestId('session-delete-sess-1'));
    fireEvent.click(screen.getByTestId('session-delete-sess-2'));

    // Both toasts should be visible
    const toasts = screen.getAllByText(/delete session/i);
    expect(toasts).toHaveLength(2);
  });

  it('clicking session item after New Chat sets active session', () => {
    setup();

    // New Chat
    fireEvent.click(screen.getByTestId('sidebar-new-chat'));
    expect(useUIStore.getState().activeSessionId).toBeNull();

    // Click session
    fireEvent.click(screen.getByTestId('session-item-sess-2'));
    expect(useUIStore.getState().activeSessionId).toBe('sess-2');
  });
});
