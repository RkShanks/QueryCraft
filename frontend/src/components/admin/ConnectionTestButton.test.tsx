import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ConnectionTestButton } from './ConnectionTestButton';
import { useConnections } from '../../hooks/useConnections';

vi.mock('../../hooks/useConnections', () => ({
  useConnections: vi.fn(),
}));

describe('ConnectionTestButton', () => {
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
      testMutation: { ...defaultMutationState },
    } as any);
  });

  it('renders enabled button with localized label', () => {
    render(<ConnectionTestButton connectionId="test-id-123" />);

    const button = screen.getByRole('button', { name: /Test Connection/i });
    expect(button).toBeInTheDocument();
    expect(button).not.toBeDisabled();
  });

  it('click invokes test connection mutation with the given connectionId', () => {
    render(<ConnectionTestButton connectionId="test-id-123" />);

    const button = screen.getByRole('button', { name: /Test Connection/i });
    fireEvent.click(button);

    expect(mockMutate).toHaveBeenCalledTimes(1);
    expect(mockMutate).toHaveBeenCalledWith('test-id-123', expect.any(Object));
  });

  it('loading state disables the button and shows localized loading label', () => {
    vi.mocked(useConnections).mockReturnValue({
      testMutation: {
        ...defaultMutationState,
        isPending: true,
      },
    } as any);

    render(<ConnectionTestButton connectionId="test-id-123" />);

    const button = screen.getByRole('button', { name: /Testing.../i });
    expect(button).toBeInTheDocument();
    expect(button).toBeDisabled();
  });

  it('success state renders localized success message and latency', () => {
    vi.mocked(useConnections).mockReturnValue({
      testMutation: {
        ...defaultMutationState,
        isSuccess: true,
        data: {
          status: 'healthy',
          latency_ms: 45,
          tested_at: '2026-05-19T20:00:00Z',
        },
      },
    } as any);

    const onSuccess = vi.fn();
    render(<ConnectionTestButton connectionId="test-id-123" onSuccess={onSuccess} />);

    expect(screen.getByText(/Connection successful \(45ms\)/i)).toBeInTheDocument();
  });

  it('handles response with status unhealthy as an error with localized message', () => {
    vi.mocked(useConnections).mockReturnValue({
      testMutation: {
        ...defaultMutationState,
        isSuccess: true,
        data: {
          status: 'unhealthy',
          error_category: 'auth_failed',
          message_key: 'error.connection_auth_failed',
          tested_at: '2026-05-19T20:00:00Z',
        },
      },
    } as any);

    const onError = vi.fn();
    render(<ConnectionTestButton connectionId="test-id-123" onError={onError} />);

    expect(screen.getByText(/Authentication failed. Check username and password./i)).toBeInTheDocument();
  });

  it('handles network unreachable error category', () => {
    vi.mocked(useConnections).mockReturnValue({
      testMutation: {
        ...defaultMutationState,
        isSuccess: true,
        data: {
          status: 'unhealthy',
          error_category: 'network_unreachable',
          message_key: 'error.connection_network_unreachable',
          tested_at: '2026-05-19T20:00:00Z',
        },
      },
    } as any);

    render(<ConnectionTestButton connectionId="test-id-123" />);

    expect(screen.getByText(/Network unreachable. Check host and port./i)).toBeInTheDocument();
  });

  it('handles timeout error category', () => {
    vi.mocked(useConnections).mockReturnValue({
      testMutation: {
        ...defaultMutationState,
        isSuccess: true,
        data: {
          status: 'unhealthy',
          error_category: 'timeout',
          message_key: 'error.connection_timeout',
          tested_at: '2026-05-19T20:00:00Z',
        },
      },
    } as any);

    render(<ConnectionTestButton connectionId="test-id-123" />);

    expect(screen.getByText(/Connection timed out/i)).toBeInTheDocument();
  });

  it('handles credential config error category', () => {
    vi.mocked(useConnections).mockReturnValue({
      testMutation: {
        ...defaultMutationState,
        isSuccess: true,
        data: {
          status: 'unhealthy',
          error_category: 'credential_config',
          message_key: 'error.credential_config',
          tested_at: '2026-05-19T20:00:00Z',
        },
      },
    } as any);

    render(<ConnectionTestButton connectionId="test-id-123" />);

    expect(screen.getByText(/Credential encryption not configured/i)).toBeInTheDocument();
  });

  it('handles thrown error object gracefully', () => {
    vi.mocked(useConnections).mockReturnValue({
      testMutation: {
        ...defaultMutationState,
        isError: true,
        error: {
          message_key: 'error.connection_auth_failed',
        },
      },
    } as any);

    render(<ConnectionTestButton connectionId="test-id-123" />);

    expect(screen.getByText(/Authentication failed. Check username and password./i)).toBeInTheDocument();
  });

  it('handles generic unknown error fallback', () => {
    vi.mocked(useConnections).mockReturnValue({
      testMutation: {
        ...defaultMutationState,
        isError: true,
        error: new Error('Some unexpected crash'),
      },
    } as any);

    render(<ConnectionTestButton connectionId="test-id-123" />);

    expect(screen.getByText(/Some unexpected crash/i)).toBeInTheDocument();
  });

  it('disabled prop prevents click and disables button', () => {
    render(<ConnectionTestButton connectionId="test-id-123" disabled />);

    const button = screen.getByRole('button', { name: /Test Connection/i });
    expect(button).toBeDisabled();

    fireEvent.click(button);
    expect(mockMutate).not.toHaveBeenCalled();
  });

  it('never leaks or renders sensitive credentials or password in DOM', () => {
    vi.mocked(useConnections).mockReturnValue({
      testMutation: {
        ...defaultMutationState,
        isSuccess: true,
        data: {
          status: 'healthy',
          latency_ms: 12,
          tested_at: '2026-05-19T20:00:00Z',
        },
      },
    } as any);

    const { container } = render(<ConnectionTestButton connectionId="test-id-123" />);
    expect(container.innerHTML).not.toContain('password');
    expect(container.innerHTML).not.toContain('secret');
  });
});
