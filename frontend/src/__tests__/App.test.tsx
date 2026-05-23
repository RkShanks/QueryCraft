import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../App';
import { useAdminSettings, useUpdateAdminSettings } from '../hooks/useAdminSettings';

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
    const i18n = (await import('../i18n')).default;
    render(<App />);
    
    await i18n.changeLanguage('ar');
    expect(document.documentElement.dir).toBe('rtl');
    expect(document.documentElement.lang).toBe('ar');

    // Cleanup
    await i18n.changeLanguage('en');
    expect(document.documentElement.dir).toBe('ltr');
    expect(document.documentElement.lang).toBe('en');
  });
});

