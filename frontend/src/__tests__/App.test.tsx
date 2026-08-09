import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../App';
import { useAdminSettings, useUpdateAdminSettings } from '../hooks/useAdminSettings';
import { server } from '../test/server';
import { http, HttpResponse } from 'msw';
import { queryClient } from '../providers/QueryProvider';

const mockUseTranslation = vi.fn().mockReturnValue({
  t: (key: string) => key,
  i18n: {
    changeLanguage: vi.fn(),
    language: 'en',
  },
});

vi.mock('react-i18next', () => ({
  useTranslation: () => mockUseTranslation(),
  initReactI18next: {
    type: '3rdParty',
    init: () => {},
  },
}));

vi.mock('../hooks/useAdminSettings', () => ({
  useAdminSettings: vi.fn(),
  useUpdateAdminSettings: vi.fn(),
}));

describe('App /settings route', () => {
  beforeEach(() => {
    queryClient.clear();
    vi.mocked(useAdminSettings).mockReturnValue({
      data: { llm_context_cap: 3 },
      isLoading: false,
      error: null,
    } as ReturnType<typeof useAdminSettings>);
    vi.mocked(useUpdateAdminSettings).mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isSuccess: false,
      isError: false,
      error: null,
      reset: vi.fn(),
    } as unknown as ReturnType<typeof useUpdateAdminSettings>);
  });

  it('renders SettingsPage at /settings under AuthGuard', async () => {
    window.history.pushState({}, '', '/settings');
    render(<App />);
    expect(await screen.findByTestId('settings-page')).toBeInTheDocument();
    expect(await screen.findByTestId('settings-llm-context-cap')).toBeInTheDocument();
  });

  it('sets document.documentElement.dir and lang to "rtl" and "ar" when language is Arabic', async () => {
    mockUseTranslation.mockReturnValue({
      t: (key: string) => key,
      i18n: {
        changeLanguage: vi.fn(),
        language: 'ar',
      },
    });

    render(<App />);
    expect(document.documentElement.dir).toBe('rtl');
    expect(document.documentElement.lang).toBe('ar');
  });

  it('sets document.documentElement.dir and lang to "ltr" and "en" when language is English', async () => {
    mockUseTranslation.mockReturnValue({
      t: (key: string) => key,
      i18n: {
        changeLanguage: vi.fn(),
        language: 'en',
      },
    });

    render(<App />);
    expect(document.documentElement.dir).toBe('ltr');
    expect(document.documentElement.lang).toBe('en');
  });

  it('lands an authenticated no-permission user on access denied without feature requests', async () => {
    let featureRequestCount = 0;
    server.use(
      http.get('/api/v1/auth/me', () =>
        HttpResponse.json({
          id: 'no-permission-user',
          username: 'restricted',
          display_name: 'Restricted User',
          role: 'admin',
          role_name: 'admin',
          permissions: [],
          auth_provider: 'local',
        })
      ),
      http.get('/api/v1/sessions', () => {
        featureRequestCount += 1;
        return HttpResponse.json({ items: [], total: 0 });
      }),
      http.get('/api/v1/connections', () => {
        featureRequestCount += 1;
        return HttpResponse.json({ connections: [] });
      })
    );
    window.history.replaceState({}, '', '/');

    render(<App />);

    expect(await screen.findByText('accessDenied.title')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'nav.signOut' })).toBeInTheDocument();
    expect(window.location.pathname).toBe('/access-denied');
    expect(featureRequestCount).toBe(0);
  });
});

