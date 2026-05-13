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
});
