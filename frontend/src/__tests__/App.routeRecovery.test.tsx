/* eslint-disable local/no-inline-user-strings */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PERMISSIONS } from '../auth/permissions';
import { queryClient } from '../providers/QueryProvider';
import { server } from '../test/server';
import App from '../App';

/**
 * CHUNK-21 / IS-GAP-037 — direct-URL, reload, back/forward, unknown path,
 * permission redirect and route-render-failure recovery matrix on the real
 * App router. jsdom cannot hard-reload; a fresh mount of the same URL stands
 * in for reload semantics.
 */

interface FailureRegistry {
  workspace: number;
  history: number;
}

function failures(): FailureRegistry {
  const g = globalThis as Record<string, unknown>;
  if (!g.__qc21Failures) {
    g.__qc21Failures = { workspace: 0, history: 0 } satisfies FailureRegistry;
  }
  return g.__qc21Failures as FailureRegistry;
}

vi.mock('../components/shell/AppShell', () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => (
    <div>
      <nav aria-label="authenticated-shell" data-testid="authenticated-shell" />
      {children}
    </div>
  ),
}));
vi.mock('../pages/WorkspacePage', () => ({
  WorkspacePage: () => {
    const registry = (globalThis as Record<string, unknown>).__qc21Failures as
      | FailureRegistry
      | undefined;
    if (registry && registry.workspace > 0) {
      // Latch: keep failing every (re)mount until the test clears the flag,
      // so discarded authorization-refresh mounts cannot consume the failure.
      throw new Error('WORKSPACE_RENDER_SENTINEL');
    }
    return <div>workspace-page</div>;
  },
}));
vi.mock('../pages/HistoryPage', () => ({
  default: () => {
    const registry = (globalThis as Record<string, unknown>).__qc21Failures as
      | FailureRegistry
      | undefined;
    if (registry && registry.history > 0) {
      throw new Error('HISTORY_RENDER_SENTINEL');
    }
    return <div>history-page</div>;
  },
}));
vi.mock('../pages/AskQuestionPage', () => ({ AskQuestionPage: () => <div>ask-page</div> }));
vi.mock('../pages/SettingsPage', () => ({ SettingsPage: () => <div>settings-page</div> }));
vi.mock('../pages/AdminConnectionsPage', () => ({
  AdminConnectionsPage: () => <div>connections-page</div>,
}));
vi.mock('../pages/AdminRolesPage', () => ({ AdminRolesPage: () => <div>roles-page</div> }));
vi.mock('../pages/AdminSsoPage', () => ({ AdminSsoPage: () => <div>sso-page</div> }));
vi.mock('../pages/AdminAuditPage', () => ({ AdminAuditPage: () => <div>audit-page</div> }));
vi.mock('../pages/AdminQuotasPage', () => ({ AdminQuotasPage: () => <div>quotas-page</div> }));
vi.mock('../pages/AdminDetectionPage', () => ({
  AdminDetectionPage: () => <div>detection-page</div>,
}));
vi.mock('../pages/AccessDeniedPage', () => ({
  AccessDeniedPage: () => <div>access-denied-page</div>,
}));

function authorize(permissions: readonly string[]) {
  server.use(
    http.get('/api/v1/auth/me', () =>
      HttpResponse.json({
        id: 'recovery-user',
        username: 'recovery-user',
        display_name: 'Recovery User',
        role: 'admin',
        role_name: 'admin',
        permissions: [...permissions],
      }),
    ),
  );
}

function navigate(pathname: string) {
  window.history.pushState({}, '', pathname);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

describe('App route recovery (CHUNK-21 / IS-GAP-037)', () => {
  beforeEach(() => {
    queryClient.clear();
    failures().workspace = 0;
    failures().history = 0;
  });

  it('keeps the authenticated shell and shows a sanitized localized boundary when a route render fails', async () => {
    authorize(Object.values(PERMISSIONS));
    failures().workspace = 1;
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    window.history.replaceState({}, '', '/');

    render(<App />);

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByTestId('authenticated-shell')).toBeInTheDocument();
    expect(screen.queryByText(/WORKSPACE_RENDER_SENTINEL/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Error:/)).not.toBeInTheDocument();
    consoleError.mockRestore();
  });

  it('recovers through Retry without leaving the route or the shell', async () => {
    authorize([PERMISSIONS.QUERY_SUBMIT]);
    failures().workspace = 1;
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    window.history.replaceState({}, '', '/');

    render(<App />);
    await screen.findByRole('alert');

    // The transient fault clears; deliberate retry re-renders the route.
    failures().workspace = 0;
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByText('workspace-page')).toBeInTheDocument();
    expect(window.location.pathname).toBe('/');
    consoleError.mockRestore();
  });

  it('resets the failed boundary on navigation to another route (back/forward semantics)', async () => {
    authorize([PERMISSIONS.QUERY_SUBMIT, PERMISSIONS.QUERY_HISTORY_VIEW]);
    failures().history = 0;
    failures().workspace = 1;
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    window.history.replaceState({}, '', '/');

    render(<App />);
    await screen.findByRole('alert');
    expect(screen.queryByText('workspace-page')).not.toBeInTheDocument();

    navigate('/history');
    expect(await screen.findByText('history-page')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();

    // Back to the previously failed entry starts a fresh boundary instance;
    // the persistent fault surfaces again instead of stale recovery state.
    window.history.back();
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.queryByText('history-page')).not.toBeInTheDocument();
    consoleError.mockRestore();
  });

  it('renders a failed route after direct URL entry and recovers on retry', async () => {
    authorize([PERMISSIONS.QUERY_HISTORY_VIEW]);
    failures().history = 2;
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    window.history.replaceState({}, '', '/history');

    render(<App />);
    await screen.findByRole('alert');
    expect(screen.queryByText('history-page')).not.toBeInTheDocument();

    // The fault clears; deliberate retry re-renders the route in place.
    failures().history = 0;
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('history-page')).toBeInTheDocument();
    consoleError.mockRestore();
  });

  it('keeps unknown paths on the permission-aware redirect contract', async () => {
    authorize([PERMISSIONS.QUERY_HISTORY_VIEW]);
    window.history.replaceState({}, '', '/definitely-not-a-route');

    render(<App />);

    expect(await screen.findByText('history-page')).toBeInTheDocument();
    expect(window.location.pathname).toBe('/history');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('sends an identity whose permissions vanished to access-denied rather than a broken shell', async () => {
    authorize([]);
    window.history.replaceState({}, '', '/unknown-location');

    render(<App />);

    expect(await screen.findByText('access-denied-page')).toBeInTheDocument();
    expect(window.location.pathname).toBe('/access-denied');
  });

  it('survives repeated failures across routes without unhandled rejections leaking into the tree', async () => {
    authorize(Object.values(PERMISSIONS));
    failures().workspace = 1;
    failures().history = 1;
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    window.history.replaceState({}, '', '/');
    const unhandled: unknown[] = [];
    const handler = (event: PromiseRejectionEvent) => unhandled.push(event.reason);
    window.addEventListener('unhandledrejection', handler);

    try {
      render(<App />);
      await screen.findByRole('alert');
      navigate('/history');
      await screen.findByRole('alert');
      expect(unhandled).toEqual([]);
      await waitFor(() => {
        expect(screen.getAllByRole('alert').length).toBeGreaterThan(0);
      });
    } finally {
      window.removeEventListener('unhandledrejection', handler);
      consoleError.mockRestore();
    }
  });
});
