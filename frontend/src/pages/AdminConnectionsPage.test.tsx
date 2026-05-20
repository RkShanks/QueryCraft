import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
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

const mockMutations = {
  createMutation: { mutate: vi.fn(), isPending: false },
  updateMutation: { mutate: vi.fn(), isPending: false },
  deleteMutation: { mutate: vi.fn(), isPending: false },
  testMutation: { mutate: vi.fn(), isPending: false, isSuccess: false, isError: false },
  disableMutation: { mutate: vi.fn(), isPending: false },
  enableMutation: { mutate: vi.fn(), isPending: false },
  refreshSchemaMutation: { mutate: vi.fn(), isPending: false },
};

const mockEmptyUseConnections = {
  listQuery: {
    data: { connections: [] },
    isLoading: false,
    isError: false,
  },
  ...mockMutations,
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
  ...mockMutations,
};

describe('AdminConnectionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders empty state when no connections', () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    vi.mocked(useConnections).mockReturnValue(mockEmptyUseConnections as any);
    render(<AdminConnectionsPage />);
    
    expect(screen.getByText('admin.connections.title')).toBeInTheDocument();
    expect(screen.getByText('admin.connections.empty')).toBeInTheDocument();
  });

  it('renders populated list with status indicators and formatted time', () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
      ...mockMutations,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    render(<AdminConnectionsPage />);
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
  });

  it('renders error state', () => {
    vi.mocked(useConnections).mockReturnValue({
      listQuery: { isLoading: false, data: undefined, isError: true },
      ...mockMutations,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    } as any);

    render(<AdminConnectionsPage />);
    expect(screen.getByText('admin.connections.loadError')).toBeInTheDocument();
  });

  it('opens connection form on Add Connection click', () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    vi.mocked(useConnections).mockReturnValue(mockEmptyUseConnections as any);
    render(<AdminConnectionsPage />);

    const addButton = screen.getByRole('button', { name: 'admin.connections.add' });
    addButton.click();

    expect(screen.getByText('admin.connections.form.createTitle')).toBeInTheDocument();
  });

  it('opens connection form with initial values on Edit click', () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    vi.mocked(useConnections).mockReturnValue(mockPopulatedUseConnections as any);
    render(<AdminConnectionsPage />);

    const editButtons = screen.getAllByRole('button', { name: 'common.edit' });
    editButtons[0].click();

    expect(screen.getByText('admin.connections.form.editTitle')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Prod DB')).toBeInTheDocument();
  });
});
