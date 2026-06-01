import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from 'vitest';
import { SignInPage } from './SignInPage';
import { createWrapper } from '../test/utils';
import { http, HttpResponse } from 'msw';
import { server } from '../test/server';

describe('SignInPage', () => {
  beforeAll(() => {
    server.use(
      http.get('/api/v1/auth/me', () => {
        return new HttpResponse(null, { status: 401 });
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
      mockLocation = new URL('http://localhost/sign-in');
      delete (window as any).location;
      window.location = {
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
      mockLocation = new URL('http://localhost/sign-in');
    });

    afterAll(() => {
      window.location = originalLocation;
    });

    it('renders SSO provider buttons when configured', async () => {
      server.use(
        http.get('/api/v1/auth/sso/providers', () => {
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
        http.get('/api/v1/auth/sso/providers', () => {
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

      expect(window.location.href).toBe('http://localhost/api/v1/auth/sso/oidc/login');
    });

    it('renders error alert when no SSO providers are configured', async () => {
      server.use(
        http.get('/api/v1/auth/sso/providers', () => {
          return HttpResponse.json({ providers: [] });
        })
      );

      render(<SignInPage />, { wrapper: createWrapper() });

      const warningText = await screen.findByText(/SSO is not configured/i);
      expect(warningText).toBeInTheDocument();
    });

    it('displays mapped error message from query parameter', async () => {
      // Setup URL search param
      mockLocation = new URL('http://localhost/sign-in?error=sso_no_role');

      server.use(
        http.get('/api/v1/auth/sso/providers', () => {
          return HttpResponse.json({ providers: [] });
        })
      );

      render(<SignInPage />, { wrapper: createWrapper() });

      const errorText = await screen.findByText(/User SSO groups don't map to any role/i);
      expect(errorText).toBeInTheDocument();
    });
  });
});
