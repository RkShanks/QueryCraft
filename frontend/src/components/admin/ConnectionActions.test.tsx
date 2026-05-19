import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ConnectionActions } from './ConnectionActions';
import { useConnections } from '../../hooks/useConnections';

vi.mock('../../hooks/useConnections', () => ({
  useConnections: vi.fn(),
}));

describe('ConnectionActions', () => {
  const mockDisableMutate = vi.fn();
  const mockEnableMutate = vi.fn();
  const mockDeleteMutate = vi.fn();

  const defaultMutationState = {
    mutate: vi.fn(),
    isPending: false,
    isSuccess: false,
    isError: false,
    data: null,
    error: null,
    reset: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useConnections).mockReturnValue({
      disableMutation: { ...defaultMutationState, mutate: mockDisableMutate },
      enableMutation: { ...defaultMutationState, mutate: mockEnableMutate },
      deleteMutation: { ...defaultMutationState, mutate: mockDeleteMutate },
      createMutation: defaultMutationState,
      updateMutation: defaultMutationState,
      testMutation: defaultMutationState,
      refreshSchemaMutation: defaultMutationState,
      listQuery: {} as any,
    });
  });

  it('renders Disable and Delete buttons when lifecycleState is active', () => {
    render(<ConnectionActions connectionId="conn-1" lifecycleState="active" />);

    expect(screen.getByRole('button', { name: /Disable/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Delete/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Enable/i })).not.toBeInTheDocument();
  });

  it('renders Enable and Delete buttons when lifecycleState is disabled', () => {
    render(<ConnectionActions connectionId="conn-1" lifecycleState="disabled" />);

    expect(screen.getByRole('button', { name: /Enable/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Delete/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Disable/i })).not.toBeInTheDocument();
  });

  it('invokes disable mutation when Disable button is clicked', () => {
    render(<ConnectionActions connectionId="conn-1" lifecycleState="active" />);

    fireEvent.click(screen.getByRole('button', { name: /Disable/i }));
    expect(mockDisableMutate).toHaveBeenCalledTimes(1);
    expect(mockDisableMutate).toHaveBeenCalledWith('conn-1', expect.any(Object));
  });

  it('invokes enable mutation when Enable button is clicked', () => {
    render(<ConnectionActions connectionId="conn-1" lifecycleState="disabled" />);

    fireEvent.click(screen.getByRole('button', { name: /Enable/i }));
    expect(mockEnableMutate).toHaveBeenCalledTimes(1);
    expect(mockEnableMutate).toHaveBeenCalledWith('conn-1', expect.any(Object));
  });

  it('shows localized loading state and disables buttons while disable is pending', () => {
    vi.mocked(useConnections).mockReturnValue({
      disableMutation: { ...defaultMutationState, mutate: mockDisableMutate, isPending: true },
      enableMutation: { ...defaultMutationState, mutate: mockEnableMutate },
      deleteMutation: { ...defaultMutationState, mutate: mockDeleteMutate },
    } as any);

    render(<ConnectionActions connectionId="conn-1" lifecycleState="active" />);

    const disableBtn = screen.getByRole('button', { name: /Disabling.../i });
    const deleteBtn = screen.getByRole('button', { name: /Delete/i });

    expect(disableBtn).toBeDisabled();
    expect(deleteBtn).toBeDisabled();
  });

  it('shows localized loading state and disables buttons while enable is pending', () => {
    vi.mocked(useConnections).mockReturnValue({
      disableMutation: { ...defaultMutationState, mutate: mockDisableMutate },
      enableMutation: { ...defaultMutationState, mutate: mockEnableMutate, isPending: true },
      deleteMutation: { ...defaultMutationState, mutate: mockDeleteMutate },
    } as any);

    render(<ConnectionActions connectionId="conn-1" lifecycleState="disabled" />);

    const enableBtn = screen.getByRole('button', { name: /Enabling.../i });
    const deleteBtn = screen.getByRole('button', { name: /Delete/i });

    expect(enableBtn).toBeDisabled();
    expect(deleteBtn).toBeDisabled();
  });

  it('opens confirmation dialog on first delete click and does not mutate immediately', () => {
    render(<ConnectionActions connectionId="conn-1" lifecycleState="active" />);

    fireEvent.click(screen.getByRole('button', { name: /Delete/i }));

    expect(screen.getByText(/Are you sure you want to delete this connection/i)).toBeInTheDocument();
    expect(mockDeleteMutate).not.toHaveBeenCalled();
  });

  it('closes confirmation dialog and does not mutate when Cancel is clicked', () => {
    render(<ConnectionActions connectionId="conn-1" lifecycleState="active" />);

    fireEvent.click(screen.getByRole('button', { name: /Delete/i }));
    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }));

    expect(screen.queryByText(/Are you sure you want to delete this connection/i)).not.toBeInTheDocument();
    expect(mockDeleteMutate).not.toHaveBeenCalled();
  });

  it('invokes delete mutation when Confirm is clicked', () => {
    render(<ConnectionActions connectionId="conn-1" lifecycleState="active" />);

    fireEvent.click(screen.getByRole('button', { name: /Delete/i }));
    fireEvent.click(screen.getByTestId('confirm-delete-btn'));

    expect(mockDeleteMutate).toHaveBeenCalledTimes(1);
    expect(mockDeleteMutate).toHaveBeenCalledWith('conn-1', expect.any(Object));
  });

  it('shows localized loading state and disables buttons while delete is pending', () => {
    vi.mocked(useConnections).mockReturnValue({
      disableMutation: { ...defaultMutationState, mutate: mockDisableMutate },
      enableMutation: { ...defaultMutationState, mutate: mockEnableMutate },
      deleteMutation: { ...defaultMutationState, mutate: mockDeleteMutate, isPending: true },
    } as any);

    render(<ConnectionActions connectionId="conn-1" lifecycleState="active" />);

    expect(screen.getByRole('button', { name: /Deleting.../i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Disable/i })).toBeDisabled();
  });

  it('renders localized blocked-delete message when backend blocks delete', () => {
    vi.mocked(useConnections).mockReturnValue({
      disableMutation: { ...defaultMutationState, mutate: mockDisableMutate },
      enableMutation: { ...defaultMutationState, mutate: mockEnableMutate },
      deleteMutation: {
        ...defaultMutationState,
        mutate: mockDeleteMutate,
        isError: true,
        error: { message_key: 'error.connection_referenced_delete_blocked' },
      },
    } as any);

    render(<ConnectionActions connectionId="conn-1" lifecycleState="active" />);

    expect(screen.getByText(/Cannot delete: connection is referenced by query attempts or sessions/i)).toBeInTheDocument();
  });

  it('renders localized messages for known action errors', () => {
    vi.mocked(useConnections).mockReturnValue({
      disableMutation: {
        ...defaultMutationState,
        mutate: mockDisableMutate,
        isError: true,
        error: { message_key: 'error.connection_already_active' },
      },
      enableMutation: { ...defaultMutationState, mutate: mockEnableMutate },
      deleteMutation: { ...defaultMutationState, mutate: mockDeleteMutate },
    } as any);

    render(<ConnectionActions connectionId="conn-1" lifecycleState="active" />);

    expect(screen.getByText(/Connection is already active/i)).toBeInTheDocument();
  });

  it('falls back to generic error message and does not leak raw backend error text', () => {
    const rawErrorMsg = "driver_postgres_secret_raw_password_failed";
    vi.mocked(useConnections).mockReturnValue({
      disableMutation: { ...defaultMutationState, mutate: mockDisableMutate },
      enableMutation: { ...defaultMutationState, mutate: mockEnableMutate },
      deleteMutation: {
        ...defaultMutationState,
        mutate: mockDeleteMutate,
        isError: true,
        error: { error: rawErrorMsg, message: rawErrorMsg },
      },
    } as any);

    const { container } = render(<ConnectionActions connectionId="conn-1" lifecycleState="active" />);

    expect(screen.getByText(/An unexpected error occurred. Please try again./i)).toBeInTheDocument();
    expect(container.innerHTML).not.toContain(rawErrorMsg);
  });

  it('disabled prop prevents all actions and disables all buttons', () => {
    render(<ConnectionActions connectionId="conn-1" lifecycleState="active" disabled />);

    const disableBtn = screen.getByRole('button', { name: /Disable/i });
    const deleteBtn = screen.getByRole('button', { name: /Delete/i });

    expect(disableBtn).toBeDisabled();
    expect(deleteBtn).toBeDisabled();

    fireEvent.click(disableBtn);
    expect(mockDisableMutate).not.toHaveBeenCalled();

    fireEvent.click(deleteBtn);
    expect(screen.queryByText(/Are you sure you want to delete this connection/i)).not.toBeInTheDocument();
  });

  it('never leaks or renders sensitive credentials or password in DOM', () => {
    render(<ConnectionActions connectionId="conn-1" lifecycleState="active" />);

    const { container } = render(<ConnectionActions connectionId="conn-1" lifecycleState="active" />);
    expect(container.innerHTML).not.toContain('password');
    expect(container.innerHTML).not.toContain('secret');
  });
});
