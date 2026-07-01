/* eslint-disable @typescript-eslint/no-explicit-any, local/no-inline-user-strings */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { PermissionGuard } from './PermissionGuard';
import { useCurrentUser } from '../../hooks/useAuth';

vi.mock('../../hooks/useAuth', () => ({
  useCurrentUser: vi.fn(),
}));

describe('PermissionGuard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading spinner when user data is loading', () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: undefined,
      isLoading: true,
    } as any);

    render(
      <MemoryRouter>
        <PermissionGuard permission="admin.roles.manage">
          <div>Protected Content</div>
        </PermissionGuard>
      </MemoryRouter>
    );

    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
  });

  it('redirects to sign-in if no user is authenticated', () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: null,
      isLoading: false,
    } as any);

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route
            path="/protected"
            element={
              <PermissionGuard permission="admin.roles.manage">
                <div>Protected Content</div>
              </PermissionGuard>
            }
          />
          <Route path="/sign-in" element={<div>Sign In Page</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Sign In Page')).toBeInTheDocument();
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
  });

  it('renders children if user has the specific permission', () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: {
        data: {
          id: 'user-1',
          role: 'member',
          permissions: ['admin.roles.manage'],
        },
      },
      isLoading: false,
    } as any);

    render(
      <MemoryRouter>
        <PermissionGuard permission="admin.roles.manage">
          <div>Protected Content</div>
        </PermissionGuard>
      </MemoryRouter>
    );

    expect(screen.getByText('Protected Content')).toBeInTheDocument();
  });

  it('redirects legacy admin user without the specific permission', () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: {
        data: {
          id: 'user-1',
          role: 'admin',
          permissions: [],
        },
      },
      isLoading: false,
    } as any);

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route
            path="/protected"
            element={
              <PermissionGuard permission="admin.roles.manage">
                <div>Protected Content</div>
              </PermissionGuard>
            }
          />
          <Route path="/" element={<div>Home Page</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Home Page')).toBeInTheDocument();
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
  });

  it('redirects to home if user is logged in but lacks the permission', () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: {
        data: {
          id: 'user-1',
          role: 'member',
          permissions: ['query.submit'],
        },
      },
      isLoading: false,
    } as any);

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route
            path="/protected"
            element={
              <PermissionGuard permission="admin.roles.manage">
                <div>Protected Content</div>
              </PermissionGuard>
            }
          />
          <Route path="/" element={<div>Home Page</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Home Page')).toBeInTheDocument();
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
  });
});
