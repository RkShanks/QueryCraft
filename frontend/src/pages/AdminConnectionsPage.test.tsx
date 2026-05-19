import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { AdminConnectionsPage } from './AdminConnectionsPage';
import { useConnections } from '../hooks/useConnections';

vi.mock('../hooks/useConnections', () => ({
  useConnections: vi.fn(),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

const mockEmptyUseConnections = {
  listQuery: {
    data: { connections: [] },
    isLoading: false,
    isError: false,
  },
};

const mockPopulatedUseConnections = {
  listQuery: {
    data: {
      connections: [
        {
          id: '1',
          display_name: 'Prod DB',
          database_type: 'postgresql',
          lifecycle_state: 'active',
          health_status: 'healthy',
          schema_introspection_status: 'success',
          schema_last_refreshed_at: '2026-05-18T12:00:00Z',
        },
        {
          id: '2',
          display_name: 'Old MySQL',
          database_type: 'mysql',
          lifecycle_state: 'disabled',
          health_status: 'unhealthy',
          schema_introspection_status: 'failed',
          schema_last_refreshed_at: null,
        },
      ],
    },
    isLoading: false,
    isError: false,
  },
};

describe('AdminConnectionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders empty state when no connections', () => {
    vi.mocked(useConnections).mockReturnValue(mockEmptyUseConnections as any);
    render(<AdminConnectionsPage />);
    
    expect(screen.getByText('admin.connections.title')).toBeInTheDocument();
    expect(screen.getByText('admin.connections.empty')).toBeInTheDocument();
  });

  it('renders populated list with status indicators and formatted time', () => {
    vi.mocked(useConnections).mockReturnValue(mockPopulatedUseConnections as any);
    render(<AdminConnectionsPage />);

    expect(screen.getByText('Prod DB')).toBeInTheDocument();
    expect(screen.getByText('Old MySQL')).toBeInTheDocument();

    // Database Types
    expect(screen.getByText('admin.connections.type.postgresql')).toBeInTheDocument();
    expect(screen.getByText('admin.connections.type.mysql')).toBeInTheDocument();

    // Statuses
    expect(screen.getByText('admin.connections.lifecycle.active')).toBeInTheDocument();
    expect(screen.getByText('admin.connections.status.healthy')).toBeInTheDocument();
    expect(screen.getByText('admin.connections.schema.success')).toBeInTheDocument();

    expect(screen.getByText('admin.connections.lifecycle.disabled')).toBeInTheDocument();
    expect(screen.getByText('admin.connections.status.unhealthy')).toBeInTheDocument();
    expect(screen.getByText('admin.connections.schema.failed')).toBeInTheDocument();
  });

  it('renders loading state', () => {
    vi.mocked(useConnections).mockReturnValue({
      listQuery: { isLoading: true, data: undefined, isError: false },
    } as any);

    render(<AdminConnectionsPage />);
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
  });

  it('renders error state', () => {
    vi.mocked(useConnections).mockReturnValue({
      listQuery: { isLoading: false, data: undefined, isError: true },
    } as any);

    render(<AdminConnectionsPage />);
    expect(screen.getByText('history.error')).toBeInTheDocument();
  });
});
