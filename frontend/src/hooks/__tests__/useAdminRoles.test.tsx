/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAdminRoles } from '../useAdminRoles';
import { server } from '../../test/server';
import { http, HttpResponse } from 'msw';

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('useAdminRoles hook - Group Mapping Persistence', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('performs role creation and then POSTs each group mapping individually', async () => {
    const rolesCreated: any[] = [];
    const mappingsCreated: any[] = [];

    server.use(
      http.post('*/admin/roles', async ({ request }) => {
        const body = (await request.json()) as any;
        rolesCreated.push(body);
        return HttpResponse.json(
          {
            id: 'generated-role-id-123',
            name: body.name,
            description: body.description,
            priority: body.priority,
            permissions: body.permissions,
            is_builtin: false,
            group_mappings: [],
            connection_policy_count: 0,
            created_at: '2026-06-05T00:00:00Z',
            updated_at: '2026-06-05T00:00:00Z',
          },
          { status: 201 }
        );
      }),
      http.post('*/admin/sso/group-mappings', async ({ request }) => {
        const body = (await request.json()) as any;
        mappingsCreated.push(body);
        return HttpResponse.json(
          {
            id: `mapping-id-${body.sso_group_value}`,
            sso_group_value: body.sso_group_value,
            role_id: body.role_id,
            role_name: 'Custom Role',
            created_at: '2026-06-05T00:00:00Z',
          },
          { status: 201 }
        );
      })
    );

    const { result } = renderHook(() => useAdminRoles(), { wrapper });

    result.current.createMutation.mutate({
      name: 'Custom Analyst',
      description: 'Analyst description',
      priority: 15,
      permissions: ['query.submit'],
      group_mappings: ['sso-analyst-group', 'sso-ops-group'],
    });

    await waitFor(() => expect(result.current.createMutation.isSuccess).toBe(true));

    // Verify role creation payload (should not have group_mappings directly in body to roles endpoint)
    expect(rolesCreated).toHaveLength(1);
    expect(rolesCreated[0]).toEqual({
      name: 'Custom Analyst',
      description: 'Analyst description',
      priority: 15,
      permissions: ['query.submit'],
    });

    // Verify separate group mapping requests
    expect(mappingsCreated).toHaveLength(2);
    expect(mappingsCreated[0]).toEqual({
      sso_group_value: 'sso-analyst-group',
      role_id: 'generated-role-id-123',
    });
    expect(mappingsCreated[1]).toEqual({
      sso_group_value: 'sso-ops-group',
      role_id: 'generated-role-id-123',
    });
  });

  it('performs role update and computes correct mapping delta (adds/deletes)', async () => {
    const rolesUpdated: any[] = [];
    const mappingsCreated: any[] = [];
    const mappingsDeleted: string[] = [];

    server.use(
      http.put('*/admin/roles/:id', async ({ request, params }) => {
        const body = (await request.json()) as any;
        rolesUpdated.push({ id: params.id, ...body });
        return HttpResponse.json(
          {
            id: params.id,
            name: body.name,
            description: body.description,
            priority: body.priority,
            permissions: body.permissions,
            is_builtin: false,
            group_mappings: [],
            connection_policy_count: 0,
            created_at: '2026-06-05T00:00:00Z',
            updated_at: '2026-06-05T00:00:00Z',
          },
          { status: 200 }
        );
      }),
      http.post('*/admin/sso/group-mappings', async ({ request }) => {
        const body = (await request.json()) as any;
        mappingsCreated.push(body);
        return HttpResponse.json({}, { status: 201 });
      }),
      http.delete('*/admin/sso/group-mappings/:mappingId', async ({ params }) => {
        mappingsDeleted.push(params.mappingId as string);
        return new HttpResponse(null, { status: 204 });
      })
    );

    const { result } = renderHook(() => useAdminRoles(), { wrapper });

    // Existing mappings are: map-1 (sso-analyst), map-2 (sso-ops)
    // New requested mappings are: sso-ops (stays), sso-manager (added), sso-analyst (deleted)
    result.current.updateMutation.mutate({
      id: 'role-uuid-999',
      data: {
        name: 'Updated Analyst',
        description: 'New Description',
        priority: 20,
        permissions: ['query.submit', 'query.history.view'],
        group_mappings: ['sso-ops', 'sso-manager'],
      },
      existingMappings: [
        { id: 'map-1', sso_group_value: 'sso-analyst' },
        { id: 'map-2', sso_group_value: 'sso-ops' },
      ],
    });

    await waitFor(() => expect(result.current.updateMutation.isSuccess).toBe(true));

    // Verify base PUT request
    expect(rolesUpdated).toHaveLength(1);
    expect(rolesUpdated[0]).toEqual({
      id: 'role-uuid-999',
      name: 'Updated Analyst',
      description: 'New Description',
      priority: 20,
      permissions: ['query.submit', 'query.history.view'],
    });

    // Verify additions (sso-manager)
    expect(mappingsCreated).toHaveLength(1);
    expect(mappingsCreated[0]).toEqual({
      sso_group_value: 'sso-manager',
      role_id: 'role-uuid-999',
    });

    // Verify deletions (map-1 / sso-analyst)
    expect(mappingsDeleted).toHaveLength(1);
    expect(mappingsDeleted[0]).toBe('map-1');
  });
});
