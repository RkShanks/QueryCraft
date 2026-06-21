/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithClient } from '../test/utils';
import { AdminQuotasPage } from './AdminQuotasPage';
import { useCurrentUser } from '../hooks/useAuth';
import { useAdminRoles } from '../hooks/useAdminRoles';
import { useAdminQuotas } from '../hooks/useAdminQuotas';

vi.mock('../hooks/useAuth', () => ({
  useCurrentUser: vi.fn(),
}));

vi.mock('../hooks/useAdminRoles', () => ({
  useAdminRoles: vi.fn(),
}));

vi.mock('../hooks/useAdminQuotas', () => ({
  useAdminQuotas: vi.fn(),
}));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, params?: any) => {
      if (params && params.time) return `${key} | time:${params.time}`;
      return key;
    },
    i18n: { language: 'en', changeLanguage: vi.fn() },
  }),
}));

describe('AdminQuotasPage', () => {
  const mockMutations = {
    upsertMutation: { mutate: vi.fn(), isPending: false },
    deleteMutation: { mutate: vi.fn(), isPending: false },
  };

  const mockQuotasList = [
    {
      role_id: 'analyst-role-id',
      role_name: 'analyst',
      daily_query_limit: 100,
      daily_execution_limit: 50,
      daily_export_limit: 5,
    },
  ];

  const mockQuotasStatus = [
    {
      role_id: 'analyst-role-id',
      role_name: 'analyst',
      dimensions: {
        queries: { limit: 100, used: 42, remaining: 58 },
        executions: { limit: 50, used: 10, remaining: 40 },
        exports: { limit: 5, used: 1, remaining: 4 },
      },
      reset_at: '2026-06-22T00:00:00Z',
    },
  ];

  const mockRolesList = {
    roles: [
      { id: 'admin-role-id', name: 'admin', is_builtin: true },
      { id: 'analyst-role-id', name: 'analyst', is_builtin: false },
      { id: 'viewer-role-id', name: 'viewer', is_builtin: false },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders title and loading state', () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: { data: { role: 'admin', permissions: ['admin.quotas.manage', 'admin.roles.manage'] } },
      isLoading: false,
    } as any);
    vi.mocked(useAdminRoles).mockReturnValue({
      listQuery: { data: undefined, isLoading: true },
    } as any);
    vi.mocked(useAdminQuotas).mockReturnValue({
      listQuery: { data: undefined, isLoading: true },
      statusQuery: { data: undefined, isLoading: true },
      ...mockMutations,
    } as any);

    renderWithClient(<AdminQuotasPage />);
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
  });

  it('with both permissions: fetches roles, merges list client-side, renders all roles showing uncapped if no quota config exists', async () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: { data: { role: 'custom', permissions: ['admin.quotas.manage', 'admin.roles.manage'] } },
      isLoading: false,
    } as any);
    vi.mocked(useAdminRoles).mockReturnValue({
      listQuery: { data: mockRolesList, isLoading: false, isError: false },
    } as any);
    vi.mocked(useAdminQuotas).mockReturnValue({
      listQuery: { data: { quotas: mockQuotasList }, isLoading: false, isError: false },
      statusQuery: { data: { status: mockQuotasStatus }, isLoading: false },
      ...mockMutations,
    } as any);

    renderWithClient(<AdminQuotasPage />);

    // Assert that we fetch roles (so useAdminRoles is called with enabled: true)
    expect(useAdminRoles).toHaveBeenCalledWith({ enabled: true });

    // Renders all roles (admin, analyst, viewer)
    expect(screen.getByText('admin')).toBeInTheDocument();
    expect(screen.getAllByText('analyst')[0]).toBeInTheDocument();
    expect(screen.getByText('viewer')).toBeInTheDocument();

    // Renders custom limits for analyst
    expect(screen.getByText('100')).toBeInTheDocument();
    expect(screen.getByText('50')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();

    // Renders Uncapped for other roles
    const uncappedElements = screen.getAllByText('quota.uncapped');
    expect(uncappedElements.length).toBeGreaterThan(0);
  });

  it('missing roles permission: does NOT call useAdminRoles, lists only configured quota rows, renders discovery warning', () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: { data: { role: 'custom', permissions: ['admin.quotas.manage'] } }, // No admin.roles.manage
      isLoading: false,
    } as any);
    
    // We expect listQuery for roles to NOT be queried, so we can mock useAdminRoles as not loaded or throwing error
    const rolesSpy = vi.mocked(useAdminRoles).mockReturnValue({
      listQuery: { data: undefined, isLoading: false, isError: true },
    } as any);

    vi.mocked(useAdminQuotas).mockReturnValue({
      listQuery: { data: { quotas: mockQuotasList }, isLoading: false, isError: false },
      statusQuery: { data: { status: mockQuotasStatus }, isLoading: false },
      ...mockMutations,
    } as any);

    renderWithClient(<AdminQuotasPage />);

    // Assert useAdminRoles was called with enabled: false to prevent calling /admin/roles
    expect(rolesSpy).toHaveBeenCalledWith({ enabled: false });
    expect(screen.queryByText('viewer')).not.toBeInTheDocument(); // viewer is uncapped and missing roles perm hides it
    expect(screen.getAllByText('analyst')[0]).toBeInTheDocument(); // analyst has a configured quota, so it is shown

    // Renders discovery warning
    expect(screen.getByText('quota.discovery_warning')).toBeInTheDocument();
  });

  it('allows saving quota configuration and calls upsert mutation', async () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: { data: { role: 'admin', permissions: ['admin.quotas.manage', 'admin.roles.manage'] } },
      isLoading: false,
    } as any);
    vi.mocked(useAdminRoles).mockReturnValue({
      listQuery: { data: mockRolesList, isLoading: false, isError: false },
    } as any);
    vi.mocked(useAdminQuotas).mockReturnValue({
      listQuery: { data: { quotas: mockQuotasList }, isLoading: false, isError: false },
      statusQuery: { data: { status: mockQuotasStatus }, isLoading: false },
      ...mockMutations,
    } as any);

    renderWithClient(<AdminQuotasPage />);

    // Click edit on analyst role row
    const editBtn = screen.getByTestId('edit-quota-analyst-role-id');
    fireEvent.click(editBtn);

    // Modify inputs
    const queryLimitInput = screen.getByLabelText('quota.query_limit');
    fireEvent.change(queryLimitInput, { target: { value: '200' } });

    // Click save
    fireEvent.click(screen.getByRole('button', { name: 'common.save' }));

    await waitFor(() => {
      expect(mockMutations.upsertMutation.mutate).toHaveBeenCalledWith({
        roleId: 'analyst-role-id',
        data: {
          daily_query_limit: 200,
          daily_execution_limit: 50,
          daily_export_limit: 5,
        },
      });
    });
  });

  it('allows deleting quota configuration and calls delete mutation', async () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: { data: { role: 'admin', permissions: ['admin.quotas.manage', 'admin.roles.manage'] } },
      isLoading: false,
    } as any);
    vi.mocked(useAdminRoles).mockReturnValue({
      listQuery: { data: mockRolesList, isLoading: false, isError: false },
    } as any);
    vi.mocked(useAdminQuotas).mockReturnValue({
      listQuery: { data: { quotas: mockQuotasList }, isLoading: false, isError: false },
      statusQuery: { data: { status: mockQuotasStatus }, isLoading: false },
      ...mockMutations,
    } as any);

    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);

    renderWithClient(<AdminQuotasPage />);

    // Click delete on analyst role row
    const deleteBtn = screen.getByTestId('delete-quota-analyst-role-id');
    fireEvent.click(deleteBtn);

    expect(confirmSpy).toHaveBeenCalled();
    await waitFor(() => {
      expect(mockMutations.deleteMutation.mutate).toHaveBeenCalledWith('analyst-role-id');
    });
  });

  it('renders with RTL direction and verified logical classes without physical inline styles', () => {
    vi.mocked(useCurrentUser).mockReturnValue({
      data: { data: { role: 'admin', permissions: ['admin.quotas.manage', 'admin.roles.manage'] } },
      isLoading: false,
    } as any);
    vi.mocked(useAdminRoles).mockReturnValue({
      listQuery: { data: mockRolesList, isLoading: false, isError: false },
    } as any);
    vi.mocked(useAdminQuotas).mockReturnValue({
      listQuery: { data: { quotas: mockQuotasList }, isLoading: false, isError: false },
      statusQuery: { data: { status: mockQuotasStatus }, isLoading: false },
      ...mockMutations,
    } as any);

    const { container } = renderWithClient(
      <div dir="rtl">
        <AdminQuotasPage />
      </div>
    );

    // Verify root is marked as RTL
    expect(container.firstChild).toHaveAttribute('dir', 'rtl');

    // Assert that there are no physical alignment inline styles
    const allElements = container.querySelectorAll('*');
    allElements.forEach((el) => {
      const style = el.getAttribute('style') || '';
      expect(style).not.toContain('text-align' + ': left');
      expect(style).not.toContain('text-align' + ': right');
      expect(style).not.toContain('margin-left');
      expect(style).not.toContain('margin-right');
      expect(style).not.toContain('padding-left');
      expect(style).not.toContain('padding-right');
    });

    // Assert that table alignment uses logical properties/classes
    const tableHeader = container.querySelector('th');
    expect(tableHeader).toHaveClass('text-start');
  });
});
