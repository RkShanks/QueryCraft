import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Sidebar } from '../Sidebar';
import { useUIStore } from '../../../stores/uiStore';
import { createWrapper } from '../../../test/utils';

const mockSessions = [
  {
    id: 'sess-today-1',
    preview_text: 'Today session',
    created_at: new Date().toISOString(),
    last_activity_at: new Date().toISOString(),
  },
  {
    id: 'sess-3days',
    preview_text: 'Three days ago',
    created_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    last_activity_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    id: 'sess-10days',
    preview_text: 'Ten days ago',
    created_at: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString(),
    last_activity_at: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString(),
  },
];

vi.mock('../../../hooks/useSessions', () => ({
  useSessionsList: vi.fn(),
  useDeleteSession: vi.fn(),
}));

import { useSessionsList } from '../../../hooks/useSessions';

function setup(sessions = mockSessions, isLoading = false) {
  (useSessionsList as ReturnType<typeof vi.fn>).mockReturnValue({
    data: { items: sessions, total: sessions.length },
    isLoading,
  });
  return render(<Sidebar />, { wrapper: createWrapper() });
}

describe('Sidebar', () => {
  beforeEach(() => {
    useUIStore.getState().setActiveSessionId(null);
    if (useUIStore.getState().sidebarCollapsed) {
      useUIStore.getState().toggleSidebar();
    }
    vi.clearAllMocks();
  });

  it('renders chronological session groups (Today / Previous 7 Days / Older)', () => {
    setup();
    expect(screen.getByText('Today')).toBeInTheDocument();
    expect(screen.getByText('Previous 7 Days')).toBeInTheDocument();
    expect(screen.getByText('Older')).toBeInTheDocument();

    expect(screen.getByText('Today session')).toBeInTheDocument();
    expect(screen.getByText('Three days ago')).toBeInTheDocument();
    expect(screen.getByText('Ten days ago')).toBeInTheDocument();
  });

  it('renders empty state when no sessions', () => {
    setup([]);
    expect(screen.getByText(/no sessions yet/i)).toBeInTheDocument();
    expect(screen.queryByText('Today')).not.toBeInTheDocument();
  });

  it('renders loading state', () => {
    setup([], true);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('clicking New Chat resets activeSessionId to null', () => {
    setup();
    useUIStore.getState().setActiveSessionId('sess-today-1');
    expect(useUIStore.getState().activeSessionId).toBe('sess-today-1');

    fireEvent.click(screen.getByTestId('sidebar-new-chat'));
    expect(useUIStore.getState().activeSessionId).toBeNull();
  });

  it('clicking session item sets active session', () => {
    setup();
    fireEvent.click(screen.getByTestId('session-item-sess-today-1'));
    expect(useUIStore.getState().activeSessionId).toBe('sess-today-1');
  });

  it('active session has active styling', () => {
    useUIStore.getState().setActiveSessionId('sess-today-1');
    setup();
    const activeItem = screen.getByTestId('session-item-sess-today-1');
    expect(activeItem.className).toContain('session-item-active');
  });

  it('clicking delete button shows undo toast', () => {
    setup();
    const deleteBtn = screen.getByTestId('session-delete-sess-today-1');
    fireEvent.click(deleteBtn);
    expect(screen.getByText(/delete session/i)).toBeInTheDocument();
  });

  it('toggles sidebar collapse', () => {
    setup();
    const toggleBtn = screen.getByTestId('sidebar-toggle');
    expect(useUIStore.getState().sidebarCollapsed).toBe(false);
    fireEvent.click(toggleBtn);
    expect(useUIStore.getState().sidebarCollapsed).toBe(true);
  });

  it('hides group titles when collapsed', () => {
    setup();
    useUIStore.getState().toggleSidebar();
    setup();
    expect(screen.queryByText('Today')).not.toBeInTheDocument();
    expect(screen.queryByText('Previous 7 Days')).not.toBeInTheDocument();
    expect(screen.queryByText('Older')).not.toBeInTheDocument();
  });

  it('renders logo text', () => {
    setup();
    expect(screen.getByText('QueryCraft')).toBeInTheDocument();
  });

  it('only shows groups that have items', () => {
    const onlyToday = [mockSessions[0]];
    setup(onlyToday);
    expect(screen.getByText('Today')).toBeInTheDocument();
    expect(screen.queryByText('Previous 7 Days')).not.toBeInTheDocument();
    expect(screen.queryByText('Older')).not.toBeInTheDocument();
  });
});
