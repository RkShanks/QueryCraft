/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { AdminRolesPage } from './AdminRolesPage.tsx';
import { useAdminRoles } from '../hooks/useAdminRoles.ts';

vi.mock('../hooks/useAdminRoles', () => ({
  useAdminRoles: vi.fn(),
}));

vi.mock('../hooks/useConnections', () => ({
  useConnections: vi.fn(() => ({
    listQuery: {
      data: [],
      isLoading: false,
      isError: false,
    },
  })),
}));

vi.mock('../hooks/useConnectionSchema', () => ({
  useConnectionSchema: vi.fn(() => ({
    data: null,
    isLoading: false,
    isError: false,
  })),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: 'en', changeLanguage: vi.fn() },
  }),
}));

const mockMutations = {
  createMutation: { mutate: vi.fn(), isPending: false },
  updateMutation: { mutate: vi.fn(), isPending: false },
  deleteMutation: { mutate: vi.fn(), isPending: false },
};

const mockEmptyRoles = {
  listQuery: {
    data: { roles: [] },
    isLoading: false,
    isError: false,
  },
  ...mockMutations,
};

const mockCustomRole = {
  id: '123',
  name: 'Analyst',
  description: 'Read-only analyst role',
  priority: 10,
  permissions: ['query.submit', 'query.history.view'],
  is_builtin: false,
  group_mappings: [
    { id: 'gm-1', sso_group_value: 'analysts' }
  ],
  connection_policy_count: 2,
  created_at: '2026-06-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
};

const mockBuiltinRole = {
  id: 'admin',
  name: 'Super Admin',
  description: 'Built-in administrator role',
  priority: 0,
  permissions: [
    'query.submit',
    'query.history.view',
    'admin.connections.manage',
    'admin.roles.manage',
    'admin.sso.manage',
    'admin.audit.verify'
  ],
  is_builtin: true,
  group_mappings: [
    { id: 'gm-2', sso_group_value: 'admins' }
  ],
  connection_policy_count: 5,
  created_at: '2026-06-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
};

const mockPopulatedRoles = {
  listQuery: {
    data: {
      roles: [mockCustomRole, mockBuiltinRole],
    },
    isLoading: false,
    isError: false,
  },
  ...mockMutations,
};

describe('AdminRolesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders title and empty state when no roles exist', () => {
    vi.mocked(useAdminRoles).mockReturnValue(mockEmptyRoles as any);
    render(<AdminRolesPage />);

    expect(screen.getByText('admin.roles.title')).toBeInTheDocument();
    expect(screen.getByText('admin.roles.emptyState')).toBeInTheDocument();
  });

  it('renders loading state', () => {
    vi.mocked(useAdminRoles).mockReturnValue({
      listQuery: { isLoading: true, data: undefined, isError: false },
      ...mockMutations,
    } as any);

    render(<AdminRolesPage />);
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
  });

  it('renders error state', () => {
    vi.mocked(useAdminRoles).mockReturnValue({
      listQuery: { isLoading: false, data: undefined, isError: true },
      ...mockMutations,
    } as any);

    render(<AdminRolesPage />);
    expect(screen.getByText('admin.roles.loadError')).toBeInTheDocument();
  });

  it('renders configured roles with priority and built-in protection indicator', () => {
    vi.mocked(useAdminRoles).mockReturnValue(mockPopulatedRoles as any);
    render(<AdminRolesPage />);

    // Custom Role
    expect(screen.getByText('Analyst')).toBeInTheDocument();
    expect(screen.getByText('Read-only analyst role')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument(); // priority
    expect(screen.getByText('analysts')).toBeInTheDocument(); // group mappings

    // Built-in Role
    expect(screen.getByText('Super Admin')).toBeInTheDocument();
    expect(screen.getByText('admin.roles.builtinProtected')).toBeInTheDocument();
    expect(screen.getByText('admins')).toBeInTheDocument();
  });

  it('shows creation form when clicking Add Role', () => {
    vi.mocked(useAdminRoles).mockReturnValue(mockEmptyRoles as any);
    render(<AdminRolesPage />);

    const addRoleButton = screen.getByRole('button', { name: 'admin.roles.addRole' });
    fireEvent.click(addRoleButton);

    expect(screen.getByText('admin.roles.form.addRoleTitle')).toBeInTheDocument();
    expect(screen.getByLabelText('admin.roles.form.name')).toBeInTheDocument();
    expect(screen.getByLabelText('admin.roles.form.description')).toBeInTheDocument();
    expect(screen.getByLabelText('admin.roles.form.priority')).toBeInTheDocument();
  });

  it('performs role creation and calls mutate with form data including permissions and inline group mappings', async () => {
    vi.mocked(useAdminRoles).mockReturnValue(mockEmptyRoles as any);
    render(<AdminRolesPage />);

    fireEvent.click(screen.getByRole('button', { name: 'admin.roles.addRole' }));

    fireEvent.change(screen.getByLabelText('admin.roles.form.name'), { target: { value: 'New Role' } });
    fireEvent.change(screen.getByLabelText('admin.roles.form.description'), { target: { value: 'New Description' } });
    fireEvent.change(screen.getByLabelText('admin.roles.form.priority'), { target: { value: '25' } });

    // Select a permission
    const querySubmitCheckbox = screen.getByLabelText('admin.roles.permissions.query.submit', { exact: false });
    fireEvent.click(querySubmitCheckbox);

    // Add inline group mapping
    const groupInput = screen.getByPlaceholderText('admin.roles.form.groupMappingPlaceholder');
    fireEvent.change(groupInput, { target: { value: 'new-group-sso' } });
    fireEvent.click(screen.getByRole('button', { name: 'common.add' }));

    // Click save
    fireEvent.click(screen.getByRole('button', { name: 'common.save' }));

    await waitFor(() => {
      expect(mockMutations.createMutation.mutate).toHaveBeenCalledWith(expect.objectContaining({
        name: 'New Role',
        description: 'New Description',
        priority: 25,
        permissions: ['query.submit'],
        group_mappings: ['new-group-sso'],
        connection_policies: [],
      }));
    });
  });

  it('shows validation errors for missing required fields', async () => {
    vi.mocked(useAdminRoles).mockReturnValue(mockEmptyRoles as any);
    render(<AdminRolesPage />);

    fireEvent.click(screen.getByRole('button', { name: 'admin.roles.addRole' }));
    fireEvent.click(screen.getByRole('button', { name: 'common.save' }));

    await waitFor(() => {
      expect(screen.getByText('error.validation.roleRequiredFields')).toBeInTheDocument();
    });
    expect(mockMutations.createMutation.mutate).not.toHaveBeenCalled();
  });

  it('allows updating a custom role and calls update mutation', async () => {
    vi.mocked(useAdminRoles).mockReturnValue(mockPopulatedRoles as any);
    render(<AdminRolesPage />);

    const editButtons = screen.getAllByRole('button', { name: 'common.edit' });
    fireEvent.click(editButtons[0]); // Edit Analyst (first in list)

    expect(screen.getByText('admin.roles.form.editRoleTitle')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Analyst')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('admin.roles.form.description'), { target: { value: 'Updated description' } });
    fireEvent.click(screen.getByRole('button', { name: 'common.save' }));

    await waitFor(() => {
      expect(mockMutations.updateMutation.mutate).toHaveBeenCalledWith(expect.objectContaining({
        id: '123',
        data: expect.objectContaining({
          description: 'Updated description',
          connection_policies: [],
        }),
      }));
    });
  });

  it('built-in roles hide delete button and block unsafe delete/mutation in UI', () => {
    vi.mocked(useAdminRoles).mockReturnValue(mockPopulatedRoles as any);
    render(<AdminRolesPage />);

    // Custom role should have both Edit and Delete
    const customRoleRow = screen.getByText('Analyst').closest('tr');
    expect(customRoleRow).toBeInTheDocument();
    expect(screen.getByTestId('edit-role-123')).toBeInTheDocument();
    expect(screen.getByTestId('delete-role-123')).toBeInTheDocument();

    // Built-in role should NOT have Delete, and should have a Protected badge
    const builtinRoleRow = screen.getByText('Super Admin').closest('tr');
    expect(builtinRoleRow).toBeInTheDocument();
    expect(screen.queryByTestId('delete-role-admin')).not.toBeInTheDocument();
    expect(screen.getByText('admin.roles.builtinProtected')).toBeInTheDocument();
  });

  it('allows deleting a custom role after confirmation', async () => {
    vi.mocked(useAdminRoles).mockReturnValue(mockPopulatedRoles as any);
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);

    render(<AdminRolesPage />);

    const deleteButton = screen.getByTestId('delete-role-123');
    fireEvent.click(deleteButton);

    expect(confirmSpy).toHaveBeenCalledWith('admin.roles.deleteConfirm');

    await waitFor(() => {
      expect(mockMutations.deleteMutation.mutate).toHaveBeenCalledWith('123');
    });
  });

  it('does not delete custom role if confirmation is cancelled', async () => {
    vi.mocked(useAdminRoles).mockReturnValue(mockPopulatedRoles as any);
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);

    render(<AdminRolesPage />);

    const deleteButton = screen.getByTestId('delete-role-123');
    fireEvent.click(deleteButton);

    expect(confirmSpy).toHaveBeenCalled();
    expect(mockMutations.deleteMutation.mutate).not.toHaveBeenCalled();
  });

  it('sanitizes hostile error containing raw database info and renders localized fallback instead', async () => {
    let capturedOnCreateError: ((err: unknown) => void) | undefined;

    vi.mocked(useAdminRoles).mockImplementation((opts: any) => {
      capturedOnCreateError = opts?.onCreateError;
      return mockEmptyRoles as any;
    });

    render(<AdminRolesPage />);
    expect(capturedOnCreateError).toBeDefined();

    // Trigger error callback with hostile raw message containing sensitive leaked info
    const hostileError = {
      message: 'Database query failed: Role table not found on internal-db-host-99.internal.corp (traceback uuid-1234-abcd-5678-secret-xyz)',
      body: {
        detail: 'Stack trace: at line 45 cert = secret-key-data'
      }
    };

    act(() => {
      capturedOnCreateError!(hostileError);
    });

    // Verify toast shows localized fallback key and DOES NOT leak internal host/uuid/trace/secret info
    expect(screen.getByText('admin.roles.addError')).toBeInTheDocument();
    expect(screen.queryByText(/internal-db-host-99/)).toBeNull();
    expect(screen.queryByText(/uuid-1234/i)).toBeNull();
    expect(screen.queryByText(/secret-key-data/i)).toBeNull();
  });
});
