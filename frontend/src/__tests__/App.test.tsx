import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../App';
import { useAdminSettings, useUpdateAdminSettings } from '../hooks/useAdminSettings';

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
});



