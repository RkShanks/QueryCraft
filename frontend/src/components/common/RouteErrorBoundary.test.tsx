import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { MemoryRouter, Routes, Route, useLocation, useNavigate } from 'react-router-dom';
import { useEffect, useRef } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { RouteErrorBoundary } from './RouteErrorBoundary';
import { AuthSessionContext, type AuthSessionContextValue } from '../../auth/AuthSessionContext';
import { seedAuthenticatedUser } from '../../test/utils';

function ThrowingChild({ shouldThrow }: { shouldThrow: boolean }): ReactNode {
  if (shouldThrow) {
    throw new Error('SECRET_INTERNAL_STACKTRACE_SENTINEL');
  }
  return <div>page-content-ok</div>;
}

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location-probe">{location.key}</span>;
}

function makeWrapper(auth: Pick<AuthSessionContextValue, 'currentUserQuery'> | null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  seedAuthenticatedUser(client);
  const authValue = auth
    ? ({ authClient: client, signInMutation: {}, signOutMutation: {}, ...auth } as unknown as AuthSessionContextValue)
    : null;
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <AuthSessionContext.Provider value={authValue}>
          <MemoryRouter initialEntries={['/']}>{children}</MemoryRouter>
        </AuthSessionContext.Provider>
      </QueryClientProvider>
    );
  };
}

describe('RouteErrorBoundary (CHUNK-21 / IS-GAP-037)', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders a localized sanitized fallback instead of the failed subtree', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <Routes>
        <Route
          path="/"
          element={
            <RouteErrorBoundary>
              <ThrowingChild shouldThrow />
            </RouteErrorBoundary>
          }
        />
      </Routes>,
      { wrapper: makeWrapper(null) },
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Something went wrong displaying this page.')).toBeInTheDocument();
    expect(screen.queryByText(/SECRET_INTERNAL_STACKTRACE_SENTINEL/)).not.toBeInTheDocument();
    consoleError.mockRestore();
  });

  it('offers Retry which resets the boundary and re-renders the route', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    let shouldThrow = true;
    const { rerender } = render(
      <Routes>
        <Route
          path="/"
          element={
            <RouteErrorBoundary>
              <ThrowingChild shouldThrow={shouldThrow} />
            </RouteErrorBoundary>
          }
        />
      </Routes>,
      { wrapper: makeWrapper(null) },
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    shouldThrow = false;
    rerender(
      <Routes>
        <Route
          path="/"
          element={
            <RouteErrorBoundary>
              <ThrowingChild shouldThrow={shouldThrow} />
            </RouteErrorBoundary>
          }
        />
      </Routes>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    await waitFor(() => expect(screen.getByText('page-content-ok')).toBeInTheDocument());
    consoleError.mockRestore();
  });

  it('resets automatically when navigation changes the location key', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    let shouldThrow = true;

    function Page() {
      return <ThrowingChild shouldThrow={shouldThrow} />;
    }

    function KeyedShell() {
      const location = useLocation();
      return (
        <>
          <RouteErrorBoundary key={location.key}>
            <Page />
          </RouteErrorBoundary>
          <LocationProbe />
        </>
      );
    }

    function NavDriver({ target }: { target: string | null }) {
      const navigate = useNavigate();
      useEffect(() => {
        if (target) navigate(target);
      }, [target, navigate]);
      return null;
    }

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    seedAuthenticatedUser(client);
    function tree(navigationTarget: string | null) {
      return (
        <QueryClientProvider client={client}>
          <AuthSessionContext.Provider value={null}>
            <MemoryRouter initialEntries={['/one']}>
              <NavDriver target={navigationTarget} />
              <Routes>
                <Route path="*" element={<KeyedShell />} />
              </Routes>
            </MemoryRouter>
          </AuthSessionContext.Provider>
        </QueryClientProvider>
      );
    }

    const { rerender } = render(tree(null));

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    const failedKey = screen.getByTestId('location-probe').textContent;

    shouldThrow = false;
    rerender(tree('/two'));

    await waitFor(() => {
      expect(screen.getByText('page-content-ok')).toBeInTheDocument();
    });
    // The boundary instance was replaced together with the route entry.
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    const recoveredKey = screen.getByTestId('location-probe').textContent;
    expect(recoveredKey).not.toEqual(failedKey);
    consoleError.mockRestore();
  });

  it('exposes a permission-aware safe navigation action when the identity is known', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    seedAuthenticatedUser(client, ['query.history.view']);
    const authValue = {
      authClient: client,
      signInMutation: {},
      signOutMutation: {},
      currentUserQuery: {
        data: client.getQueryData(['currentUser']),
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        error: null,
        refetch: vi.fn(),
      },
    } as unknown as AuthSessionContextValue;

    render(
      <QueryClientProvider client={client}>
        <AuthSessionContext.Provider value={authValue}>
          <MemoryRouter initialEntries={['/admin/audit']}>
            <Routes>
              <Route
                path="*"
                element={
                  <RouteErrorBoundary>
                    <ThrowingChild shouldThrow />
                  </RouteErrorBoundary>
                }
              />
            </Routes>
          </MemoryRouter>
        </AuthSessionContext.Provider>
      </QueryClientProvider>,
    );

    expect(screen.getByRole('button', { name: 'Go to your workspace home' })).toBeInTheDocument();
    consoleError.mockRestore();
  });
});
