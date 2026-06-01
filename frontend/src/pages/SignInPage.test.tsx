/* eslint-disable @typescript-eslint/no-explicit-any */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach, beforeAll, afterEach, afterAll, vi } from 'vitest';
import { SignInPage } from './SignInPage';
import { createWrapper } from '../test/utils';
import { http, HttpResponse } from 'msw';
import { server } from '../test/server';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

describe('SignInPage', () => {
  beforeEach(() => {
    // Add default mocks for /api/v1/auth/me to return 401 (unauthenticated)
    // and /api/v1/auth/sso/providers to return empty list by default.
    // Uses wildcard matching to avoid origin-mismatch issues.
    server.use(
      http.get('*/api/v1/auth/me', () => {
        return new HttpResponse(null, { status: 401 });
      }),
      http.get('*/api/v1/auth/sso/providers', () => {
        return HttpResponse.json({ providers: [] });
      })
    );
  });

  it('renders branded premium layout with title and subtitle', async () => {
    render(<SignInPage />, { wrapper: createWrapper() });
    
    // Wait for the page to finish loading and show the sign in text
    await screen.findByRole('heading', { name: /Sign In/i });

    expect(screen.getByRole('heading', { name: /QueryCraft/i, level: 1 })).toBeInTheDocument();
    expect(screen.getByText(/Text-to-SQL Analytics Platform/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Sign In/i, level: 2 })).toBeInTheDocument();
  });

  describe('SSO Sign-In Flows', () => {
    let originalLocation: Location;
    let mockLocation: URL;

    beforeAll(() => {
      originalLocation = window.location;
      mockLocation = new URL('http://localhost:3000/sign-in');
      delete (window as any).location;
      (window as any).location = {
        ...originalLocation,
        assign: vi.fn(),
        replace: vi.fn(),
        get href() {
          return mockLocation.href;
        },
        set href(val: string) {
          mockLocation.href = new URL(val, mockLocation.origin).href;
        },
        get search() {
          return mockLocation.search;
        },
        get pathname() {
          return mockLocation.pathname;
        },
      } as any;
    });

    afterEach(() => {
      mockLocation = new URL('http://localhost:3000/sign-in');
    });

    afterAll(() => {
      (window as any).location = originalLocation;
    });

    it('renders SSO provider buttons when configured', async () => {
      server.use(
        http.get('*/api/v1/auth/sso/providers', () => {
          return HttpResponse.json({
            providers: [
              {
                protocol: 'oidc',
                display_name: 'Corporate OIDC',
                login_url: '/api/v1/auth/sso/oidc/login',
              },
              {
                protocol: 'saml',
                display_name: 'Okta SAML',
                login_url: '/api/v1/auth/sso/saml/login',
              },
            ],
          });
        })
      );

      render(<SignInPage />, { wrapper: createWrapper() });

      const oidcButton = await screen.findByRole('button', { name: /Sign in with Corporate OIDC/i });
      const samlButton = await screen.findByRole('button', { name: /Sign in with Okta SAML/i });

      expect(oidcButton).toBeInTheDocument();
      expect(samlButton).toBeInTheDocument();
      expect(screen.queryByText(/SSO is not configured/i)).not.toBeInTheDocument();
    });

    it('redirects to provider login URL on click', async () => {
      server.use(
        http.get('*/api/v1/auth/sso/providers', () => {
          return HttpResponse.json({
            providers: [
              {
                protocol: 'oidc',
                display_name: 'Corporate OIDC',
                login_url: '/api/v1/auth/sso/oidc/login',
              },
            ],
          });
        })
      );

      render(<SignInPage />, { wrapper: createWrapper() });

      const oidcButton = await screen.findByRole('button', { name: /Sign in with Corporate OIDC/i });
      oidcButton.click();

      expect(window.location.href).toContain('/api/v1/auth/sso/oidc/login');
    });

    it('renders error alert when no SSO providers are configured', async () => {
      server.use(
        http.get('*/api/v1/auth/sso/providers', () => {
          return HttpResponse.json({ providers: [] });
        })
      );

      render(<SignInPage />, { wrapper: createWrapper() });

      const warningText = await screen.findByText(/SSO is not configured/i);
      expect(warningText).toBeInTheDocument();
    });

    it('displays mapped error message from query parameter', async () => {
      const testQueryClient = new QueryClient({
        defaultOptions: {
          queries: {
            retry: false,
          },
        },
      });

      render(
        <MemoryRouter initialEntries={['/sign-in?error=sso_no_role']}>
          <QueryClientProvider client={testQueryClient}>
            <SignInPage />
          </QueryClientProvider>
        </MemoryRouter>
      );

      const errorText = await screen.findByText(/User SSO groups don't map to any role/i);
      expect(errorText).toBeInTheDocument();
    });
  });
});
