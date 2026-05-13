import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SettingsPage } from '../SettingsPage';
import { renderWithClient } from '../../test/utils';
import { useAdminSettings, useUpdateAdminSettings } from '../../hooks/useAdminSettings';

vi.mock('../../hooks/useAdminSettings', () => ({
  useAdminSettings: vi.fn(),
  useUpdateAdminSettings: vi.fn(),
}));

describe('SettingsPage', () => {
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

  it('renders settings page with context cap input', () => {
    render(renderWithClient(<SettingsPage />));
    expect(screen.getByTestId('settings-llm-context-cap')).toBeInTheDocument();
    expect(screen.getByTestId('settings-save-btn')).toBeInTheDocument();
  });
});
