import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { RefreshSchemaButton } from './RefreshSchemaButton';
import { useConnections } from '../../hooks/useConnections';

vi.mock('../../hooks/useConnections', () => ({
  useConnections: vi.fn(),
}));

describe('RefreshSchemaButton', () => {
  const mockMutate = vi.fn();
  const mockReset = vi.fn();

  const defaultMutationState = {
    mutate: mockMutate,
    reset: mockReset,
    isPending: false,
    isSuccess: false,
    isError: false,
    data: null,
    error: null,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useConnections).mockReturnValue({
      refreshSchemaMutation: { ...defaultMutationState },
    } as unknown as ReturnType<typeof useConnections>);
  });

  it('renders enabled button with localized label', () => {
    render(<RefreshSchemaButton connectionId="conn-123" />);

    const button = screen.getByRole('button', { name: /Refresh Schema/i });
    expect(button).toBeInTheDocument();
    expect(button).not.toBeDisabled();
  });

  it('click invokes refresh schema mutation with the given connectionId', () => {
    render(<RefreshSchemaButton connectionId="conn-123" />);

    const button = screen.getByRole('button', { name: /Refresh Schema/i });
    fireEvent.click(button);

    expect(mockMutate).toHaveBeenCalledTimes(1);
    expect(mockMutate).toHaveBeenCalledWith('conn-123', expect.any(Object));
  });

  it('loading state disables the button and shows localized loading label', () => {
    vi.mocked(useConnections).mockReturnValue({
      refreshSchemaMutation: {
        ...defaultMutationState,
        isPending: true,
      },
    } as unknown as ReturnType<typeof useConnections>);

    render(<RefreshSchemaButton connectionId="conn-123" />);

    const button = screen.getByRole('button', { name: /Refreshing.../i });
    expect(button).toBeInTheDocument();
    expect(button).toBeDisabled();
  });

  it('success state renders localized success message with counts', () => {
    vi.mocked(useConnections).mockReturnValue({
      refreshSchemaMutation: {
        ...defaultMutationState,
        isSuccess: true,
        data: {
          tables_count: 14,
          columns_count: 52,
          approximate_tokens: 350,
          refreshed_at: '2026-05-19T20:30:00Z',
        },
      },
    } as unknown as ReturnType<typeof useConnections>);

    const onSuccess = vi.fn();
    render(<RefreshSchemaButton connectionId="conn-123" onSuccess={onSuccess} />);

    expect(screen.getByText(/Schema refreshed successfully \(14 tables, 52 columns\)/i)).toBeInTheDocument();
  });

  it('renders last refreshed time from schemaLastRefreshedAt when provided', () => {
    render(
      <RefreshSchemaButton
        connectionId="conn-123"
        schemaLastRefreshedAt="2026-05-19T18:15:00Z"
      />
    );

    // Should display the formatted time. We check if the localized text prefix is in document.
    expect(screen.getByText(/Refreshed/i)).toBeInTheDocument();
  });

  it('renders refreshed time from mutation response when mutation succeeds', () => {
    vi.mocked(useConnections).mockReturnValue({
      refreshSchemaMutation: {
        ...defaultMutationState,
        isSuccess: true,
        data: {
          tables_count: 5,
          columns_count: 20,
          refreshed_at: '2026-05-19T20:30:00Z',
        },
      },
    } as unknown as ReturnType<typeof useConnections>);

    render(<RefreshSchemaButton connectionId="conn-123" />);

    expect(screen.getByText(/Refreshed/i)).toBeInTheDocument();
  });

  it('handles response with status unhealthy or failure as an error', () => {
    vi.mocked(useConnections).mockReturnValue({
      refreshSchemaMutation: {
        ...defaultMutationState,
        isError: true,
        error: {
          message_key: 'error.introspection_failed',
        },
      },
    } as unknown as ReturnType<typeof useConnections>);

    const onError = vi.fn();
    render(<RefreshSchemaButton connectionId="conn-123" onError={onError} />);

    expect(screen.getByText(/Schema introspection failed/i)).toBeInTheDocument();
  });

  it('handles network unreachable error category', () => {
    vi.mocked(useConnections).mockReturnValue({
      refreshSchemaMutation: {
        ...defaultMutationState,
        isError: true,
        error: {
          message_key: 'error.connection_network_unreachable',
        },
      },
    } as unknown as ReturnType<typeof useConnections>);

    render(<RefreshSchemaButton connectionId="conn-123" />);

    expect(screen.getByText(/Network unreachable. Check host and port./i)).toBeInTheDocument();
  });

  it('handles introspection timeout error category', () => {
    vi.mocked(useConnections).mockReturnValue({
      refreshSchemaMutation: {
        ...defaultMutationState,
        isError: true,
        error: {
          message_key: 'error.introspection_timeout',
        },
      },
    } as unknown as ReturnType<typeof useConnections>);

    render(<RefreshSchemaButton connectionId="conn-123" />);

    expect(screen.getByText(/Schema introspection timed out/i)).toBeInTheDocument();
  });

  it('handles credential config error category', () => {
    vi.mocked(useConnections).mockReturnValue({
      refreshSchemaMutation: {
        ...defaultMutationState,
        isError: true,
        error: {
          message_key: 'error.credential_config',
        },
      },
    } as unknown as ReturnType<typeof useConnections>);

    render(<RefreshSchemaButton connectionId="conn-123" />);

    expect(screen.getByText(/Credential encryption not configured/i)).toBeInTheDocument();
  });

  it('handles generic unknown error fallback', () => {
    vi.mocked(useConnections).mockReturnValue({
      refreshSchemaMutation: {
        ...defaultMutationState,
        isError: true,
        error: new Error('Database password leak risk!'),
      },
    } as unknown as ReturnType<typeof useConnections>);

    const { container } = render(<RefreshSchemaButton connectionId="conn-123" />);

    expect(screen.getByText(/An unexpected error occurred. Please try again./i)).toBeInTheDocument();
    expect(container.innerHTML).not.toContain('Database password leak risk!');
  });

  it('disabled prop prevents click and disables button', () => {
    render(<RefreshSchemaButton connectionId="conn-123" disabled />);

    const button = screen.getByRole('button', { name: /Refresh Schema/i });
    expect(button).toBeDisabled();

    fireEvent.click(button);
    expect(mockMutate).not.toHaveBeenCalled();
  });

  it('never leaks or renders sensitive credentials or password in DOM', () => {
    vi.mocked(useConnections).mockReturnValue({
      refreshSchemaMutation: {
        ...defaultMutationState,
        isSuccess: true,
        data: {
          tables_count: 5,
          columns_count: 10,
          refreshed_at: '2026-05-19T20:30:00Z',
        },
      },
    } as unknown as ReturnType<typeof useConnections>);

    const { container } = render(<RefreshSchemaButton connectionId="conn-123" />);
    expect(container.innerHTML).not.toContain('password');
    expect(container.innerHTML).not.toContain('secret');
  });

  it('handles unknown error string and falls back to generic localized message without leaking key or message', () => {
    vi.mocked(useConnections).mockReturnValue({
      refreshSchemaMutation: {
        ...defaultMutationState,
        isError: true,
        error: {
          error: 'driver_postgres_secret_raw_password_failed',
        },
      },
    } as unknown as ReturnType<typeof useConnections>);

    const { container } = render(<RefreshSchemaButton connectionId="conn-123" />);

    expect(screen.getByText(/An unexpected error occurred. Please try again./i)).toBeInTheDocument();
    expect(container.innerHTML).not.toContain('driver_postgres_secret_raw_password_failed');
    expect(container.innerHTML).not.toContain('error.driver_postgres_secret_raw_password_failed');
  });
});
