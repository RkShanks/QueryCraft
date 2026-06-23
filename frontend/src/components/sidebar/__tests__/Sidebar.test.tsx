/* eslint-disable @typescript-eslint/no-explicit-any */
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

vi.mock('../../../hooks/useAuth', () => ({
  useSignOut: vi.fn(),
  useCurrentUser: vi.fn(() => ({
    data: {
      data: {
        id: 'user-admin',
        role: 'admin',
        permissions: ['admin.connections.manage', 'admin.roles.manage'],
      },
    },
    isLoading: false,
  })),
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

import { useSessionsList } from '../../../hooks/useSessions';
import { useSignOut, useCurrentUser } from '../../../hooks/useAuth';

function setup(sessions = mockSessions, isLoading = false) {
  (useSessionsList as ReturnType<typeof vi.fn>).mockReturnValue({
    data: { items: sessions, total: sessions.length },
    isLoading,
  });
  return render(<Sidebar />, { wrapper: createWrapper() });
}

function setupSignOutMock(overrides: Record<string, unknown> = {}) {
  const mutate = vi.fn();
  (useSignOut as ReturnType<typeof vi.fn>).mockReturnValue({
    mutate,
    isPending: false,
    isSuccess: false,
    isError: false,
    ...overrides,
  });
  return mutate;
}

describe('Sidebar', () => {
  beforeEach(() => {
    useUIStore.getState().setActiveSessionId(null);
    if (useUIStore.getState().sidebarCollapsed) {
      useUIStore.getState().toggleSidebar();
    }
    vi.clearAllMocks();
    setupSignOutMock();
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
    expect(mockNavigate).toHaveBeenCalledWith('/');
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

  it('renders sign-out button', () => {
    setup();
    expect(screen.getByTestId('sidebar-sign-out')).toBeInTheDocument();
  });

  it('clicking sign-out calls sign-out mutation', () => {
    const mutate = setupSignOutMock();
    setup();
    fireEvent.click(screen.getByTestId('sidebar-sign-out'));
    expect(mutate).toHaveBeenCalled();
  });

  it('collapsed sidebar still exposes sign-out button', () => {
    setup();
    useUIStore.getState().toggleSidebar();
    setup();
    const buttons = screen.getAllByTestId('sidebar-sign-out');
    expect(buttons.length).toBeGreaterThanOrEqual(1);
  });

  it('renders History, Settings, and Connections nav buttons in expanded sidebar', () => {
    setup();
    expect(screen.getByTestId('sidebar-nav-history')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-nav-settings')).toBeInTheDocument();
    expect(screen.getByTestId('sidebar-nav-connections')).toBeInTheDocument();
    expect(screen.getByText('History')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
    expect(screen.getByText('Connections')).toBeInTheDocument();
  });

  it('clicking History navigates to /history', () => {
    setup();
    fireEvent.click(screen.getByTestId('sidebar-nav-history'));
    expect(mockNavigate).toHaveBeenCalledWith('/history');
  });

  it('clicking Settings navigates to /settings', () => {
    setup();
    fireEvent.click(screen.getByTestId('sidebar-nav-settings'));
    expect(mockNavigate).toHaveBeenCalledWith('/settings');
  });

  it('clicking Connections navigates to /admin/connections', () => {
    setup();
    fireEvent.click(screen.getByTestId('sidebar-nav-connections'));
    expect(mockNavigate).toHaveBeenCalledWith('/admin/connections');
  });

  it('collapsed sidebar exposes History and Settings buttons by aria-label', () => {
    setup();
    useUIStore.getState().toggleSidebar();
    setup();
    const historyButtons = screen.getAllByLabelText('History');
    const settingsButtons = screen.getAllByLabelText('Settings');
    expect(historyButtons.length).toBeGreaterThanOrEqual(1);
    expect(settingsButtons.length).toBeGreaterThanOrEqual(1);
  });

  it('shows roles and hides connections when user only has admin.roles.manage permission', () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: {
        data: {
          id: 'user-roles',
          role: 'member',
          permissions: ['admin.roles.manage'],
        },
      },
      isLoading: false,
    } as any);

    setup();
    expect(screen.queryByTestId('sidebar-nav-connections')).not.toBeInTheDocument();
    expect(screen.getByTestId('sidebar-nav-roles')).toBeInTheDocument();
  });

  it('shows connections and hides roles when user only has admin.connections.manage permission', () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: {
        data: {
          id: 'user-connections',
          role: 'member',
          permissions: ['admin.connections.manage'],
        },
      },
      isLoading: false,
    } as any);

    setup();
    expect(screen.getByTestId('sidebar-nav-connections')).toBeInTheDocument();
    expect(screen.queryByTestId('sidebar-nav-roles')).not.toBeInTheDocument();
  });

  it('shows audit and hides other admin buttons when user only has admin.audit.verify permission', () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: {
        data: {
          id: 'user-audit',
          role: 'member',
          permissions: ['admin.audit.verify'],
        },
      },
      isLoading: false,
    } as any);

    setup();
    expect(screen.queryByTestId('sidebar-nav-connections')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sidebar-nav-roles')).not.toBeInTheDocument();
    expect(screen.getByTestId('sidebar-nav-audit')).toBeInTheDocument();
  });

  it('clicking Audit Verification navigates to /admin/audit', () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: {
        data: {
          id: 'user-audit',
          role: 'member',
          permissions: ['admin.audit.verify'],
        },
      },
      isLoading: false,
    } as any);

    setup();
    fireEvent.click(screen.getByTestId('sidebar-nav-audit'));
    expect(mockNavigate).toHaveBeenCalledWith('/admin/audit');
  });

  it('shows quotas and hides other admin buttons when user only has admin.quotas.manage permission', () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: {
        data: {
          id: 'user-quotas',
          role: 'member',
          permissions: ['admin.quotas.manage'],
        },
      },
      isLoading: false,
    } as any);

    setup();
    expect(screen.queryByTestId('sidebar-nav-connections')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sidebar-nav-roles')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sidebar-nav-audit')).not.toBeInTheDocument();
    expect(screen.getByTestId('sidebar-nav-quotas')).toBeInTheDocument();
  });

  it('clicking Quotas navigates to /admin/quotas', () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: {
        data: {
          id: 'user-quotas',
          role: 'member',
          permissions: ['admin.quotas.manage'],
        },
      },
      isLoading: false,
    } as any);

    setup();
    fireEvent.click(screen.getByTestId('sidebar-nav-quotas'));
    expect(mockNavigate).toHaveBeenCalledWith('/admin/quotas');
  });

  it('shows detection and hides other admin buttons when user only has admin.security.manage permission', () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: {
        data: {
          id: 'user-security',
          role: 'member',
          permissions: ['admin.security.manage'],
        },
      },
      isLoading: false,
    } as any);

    setup();
    expect(screen.queryByTestId('sidebar-nav-connections')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sidebar-nav-roles')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sidebar-nav-audit')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sidebar-nav-quotas')).not.toBeInTheDocument();
    expect(screen.getByTestId('sidebar-nav-detection')).toBeInTheDocument();
  });

  it('clicking Detection navigates to /admin/detection', () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: {
        data: {
          id: 'user-security',
          role: 'member',
          permissions: ['admin.security.manage'],
        },
      },
      isLoading: false,
    } as any);

    setup();
    fireEvent.click(screen.getByTestId('sidebar-nav-detection'));
    expect(mockNavigate).toHaveBeenCalledWith('/admin/detection');
  });
});

