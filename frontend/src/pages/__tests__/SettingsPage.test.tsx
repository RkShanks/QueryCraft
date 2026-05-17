import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { SettingsPage } from '../SettingsPage';
import { renderWithClient } from '../../test/utils';
import { useAdminSettings, useUpdateAdminSettings } from '../../hooks/useAdminSettings';

vi.mock('../../hooks/useAdminSettings', () => ({
  useAdminSettings: vi.fn(),
  useUpdateAdminSettings: vi.fn(),
}));

function mockSettings(data: { llm_context_cap?: number; max_regenerate_attempts?: number } = {}) {
  vi.mocked(useAdminSettings).mockReturnValue({
    data: { llm_context_cap: 3, max_regenerate_attempts: 3, ...data },
    isLoading: false,
    error: null,
  } as ReturnType<typeof useAdminSettings>);
}

function mockMutation(overrides: Record<string, unknown> = {}) {
  vi.mocked(useUpdateAdminSettings).mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isSuccess: false,
    isError: false,
    error: null,
    reset: vi.fn(),
    ...overrides,
  } as unknown as ReturnType<typeof useUpdateAdminSettings>);
}

describe('SettingsPage', () => {
  beforeEach(() => {
    mockSettings();
    mockMutation();
  });

  it('renders settings page with both fields and save button', () => {
    renderWithClient(<SettingsPage />);
    expect(screen.getByTestId('settings-llm-context-cap')).toBeInTheDocument();
    expect(screen.getByTestId('settings-max-regenerate-attempts')).toBeInTheDocument();
    expect(screen.getByTestId('settings-save-btn')).toBeInTheDocument();
  });

  it('displays loading spinner when settings are loading', () => {
    vi.mocked(useAdminSettings).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as ReturnType<typeof useAdminSettings>);
    renderWithClient(<SettingsPage />);
    expect(screen.getByTestId('settings-page-loading')).toBeInTheDocument();
  });

  it('displays error message when settings fail to load', () => {
    vi.mocked(useAdminSettings).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Failed to load'),
    } as ReturnType<typeof useAdminSettings>);
    renderWithClient(<SettingsPage />);
    expect(screen.getByTestId('settings-page-error')).toBeInTheDocument();
  });

  it('calls mutate with both values on save', () => {
    const mutate = vi.fn();
    mockMutation({ mutate });
    renderWithClient(<SettingsPage />);
    const capInput = screen.getByTestId('settings-llm-context-cap') as HTMLInputElement;
    const regenInput = screen.getByTestId('settings-max-regenerate-attempts') as HTMLInputElement;
    fireEvent.change(capInput, { target: { value: '5' } });
    fireEvent.change(regenInput, { target: { value: '4' } });
    fireEvent.click(screen.getByTestId('settings-save-btn'));
    expect(mutate).toHaveBeenCalledWith({ llm_context_cap: 5, max_regenerate_attempts: 4 });
  });

  it('rejects out-of-range context cap and shows validation error', () => {
    const mutate = vi.fn();
    mockMutation({ mutate });
    renderWithClient(<SettingsPage />);
    const input = screen.getByTestId('settings-llm-context-cap') as HTMLInputElement;
    fireEvent.change(input, { target: { value: '15' } });
    fireEvent.click(screen.getByTestId('settings-save-btn'));
    expect(screen.getByTestId('settings-context-cap-error')).toBeInTheDocument();
    expect(mutate).not.toHaveBeenCalled();
  });

  it('rejects negative context cap and shows validation error', () => {
    const mutate = vi.fn();
    mockMutation({ mutate });
    renderWithClient(<SettingsPage />);
    const input = screen.getByTestId('settings-llm-context-cap') as HTMLInputElement;
    fireEvent.change(input, { target: { value: '-1' } });
    fireEvent.click(screen.getByTestId('settings-save-btn'));
    expect(screen.getByTestId('settings-context-cap-error')).toBeInTheDocument();
    expect(mutate).not.toHaveBeenCalled();
  });

  it('rejects out-of-range max regenerate attempts', () => {
    const mutate = vi.fn();
    mockMutation({ mutate });
    renderWithClient(<SettingsPage />);
    const regenInput = screen.getByTestId('settings-max-regenerate-attempts') as HTMLInputElement;
    fireEvent.change(regenInput, { target: { value: '15' } });
    fireEvent.click(screen.getByTestId('settings-save-btn'));
    expect(screen.getByTestId('settings-max-regen-error')).toBeInTheDocument();
    expect(mutate).not.toHaveBeenCalled();
  });

  it('rejects below-1 max regenerate attempts', () => {
    const mutate = vi.fn();
    mockMutation({ mutate });
    renderWithClient(<SettingsPage />);
    const regenInput = screen.getByTestId('settings-max-regenerate-attempts') as HTMLInputElement;
    fireEvent.change(regenInput, { target: { value: '0' } });
    fireEvent.click(screen.getByTestId('settings-save-btn'));
    expect(screen.getByTestId('settings-max-regen-error')).toBeInTheDocument();
    expect(mutate).not.toHaveBeenCalled();
  });

  it('shows success message after save', () => {
    mockMutation({ isSuccess: true });
    renderWithClient(<SettingsPage />);
    expect(screen.getByTestId('settings-success-msg')).toBeInTheDocument();
  });

  it('shows error message when save fails', () => {
    mockMutation({ isError: true });
    renderWithClient(<SettingsPage />);
    expect(screen.getByTestId('settings-error-msg')).toBeInTheDocument();
  });
});
