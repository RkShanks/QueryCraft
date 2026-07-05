/* eslint-disable @typescript-eslint/no-explicit-any */
import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach, beforeAll, afterEach, afterAll, vi } from 'vitest';
import { SignInPage } from './SignInPage';
import { createWrapper } from '../test/utils';
import { http, HttpResponse } from 'msw';
import { server } from '../test/server';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mockLanguageState = { language: 'en' };

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: any) => {
      // Direct translations mapping for English/Arabic
      let val: string;
      if (mockLanguageState.language === 'ar') {
        if (key === 'app.title') val = 'QueryCraft';
        else if (key === 'app.subtitle') val = 'منصة تحليلات النص إلى SQL';
        else if (key === 'auth.signIn.title') val = 'تسجيل الدخول';
        else if (key === 'auth.signIn.sso.button') val = 'تسجيل الدخول باستخدام {{provider}}';
        else if (key === 'error.ssoNotConfigured') val = 'لم يتم تكوين SSO بعد.';
        else if (key === 'error.ssoNoRole') val = 'لا توجد أدوار مخصصة لمجموعات SSO الخاصة بك.';
        else if (key === 'error.ssoValidationFailed') val = 'فشل التحقق من صحة SSO.';
        else if (key === 'common.or') val = 'أو';
        else val = key;
      } else {
        if (key === 'app.title') val = 'QueryCraft';
        else if (key === 'app.subtitle') val = 'Text-to-SQL Analytics Platform';
        else if (key === 'auth.signIn.title') val = 'Sign In';
        else if (key === 'auth.signIn.sso.button') val = 'Sign in with {{provider}}';
        else if (key === 'error.ssoNotConfigured') val = 'SSO is not configured.';
        else if (key === 'error.ssoNoRole') val = "User SSO groups don't map to any role.";
        else if (key === 'error.ssoValidationFailed') val = 'SSO validation failed.';
        else if (key === 'common.or') val = 'Or';
        else val = key;
      }

      if (options && typeof options === 'object') {
        val = val.replace(/\{\{(\w+)\}\}/g, (_, match) => String(options[match] ?? `{{${match}}}`));
      }
      return val;
    },
    i18n: {
      changeLanguage: (lng: string) => {
        mockLanguageState.language = lng;
        return Promise.resolve();
      },
      language: mockLanguageState.language,
    },
  }),
  initReactI18next: {
    type: '3rdParty',
    init: () => {},
  },
}));

describe('SignInPage', () => {
  beforeEach(() => {
    // Reset language to default English before each test
    mockLanguageState.language = 'en';

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

  it('sets dir="rtl" and renders Arabic localized text when language is ar', async () => {
    mockLanguageState.language = 'ar';

    render(<SignInPage />, { wrapper: createWrapper() });

    // Wait for the page to finish loading and show Arabic heading
    await screen.findByRole('heading', { name: 'تسجيل الدخول' });

    // Assert that the root component container has dir="rtl"
    const rootContainer = screen.getByRole('heading', { name: 'تسجيل الدخول' }).closest('[dir]');
    expect(rootContainer).toHaveAttribute('dir', 'rtl');

    // Assert that Arabic warning is displayed
    expect(screen.getByText('لم يتم تكوين SSO بعد.')).toBeInTheDocument();
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

    const configureActiveSsoProviders = () => {
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
    };

    it('renders localized SSO provider buttons when configured', async () => {
      configureActiveSsoProviders();

      render(<SignInPage />, { wrapper: createWrapper() });

      const oidcButton = await screen.findByRole('button', { name: /Sign in with Corporate OIDC/i });
      const samlButton = await screen.findByRole('button', { name: /Sign in with Okta SAML/i });

      expect(oidcButton).toBeInTheDocument();
      expect(samlButton).toBeInTheDocument();
      expect(screen.queryByText('auth.signIn.sso.button')).not.toBeInTheDocument();
      expect(screen.queryByText(/SSO is not configured/i)).not.toBeInTheDocument();
    });

    it('renders Arabic SSO provider buttons without raw i18n keys', async () => {
      mockLanguageState.language = 'ar';
      configureActiveSsoProviders();

      render(<SignInPage />, { wrapper: createWrapper() });

      const oidcButton = await screen.findByRole('button', { name: /Corporate OIDC/i });
      const samlButton = await screen.findByRole('button', { name: /Okta SAML/i });

      expect(oidcButton).toHaveTextContent('تسجيل الدخول باستخدام Corporate OIDC');
      expect(samlButton).toHaveTextContent('تسجيل الدخول باستخدام Okta SAML');
      expect(screen.queryByText('auth.signIn.sso.button')).not.toBeInTheDocument();
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
