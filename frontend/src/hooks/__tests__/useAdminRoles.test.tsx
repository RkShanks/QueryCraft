/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAdminRoles, useDraftRolePolicyPreview } from '../useAdminRoles';
import { server } from '../../test/server';
import { http, HttpResponse } from 'msw';
import { seedAuthenticatedUser } from '../../test/utils';

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  seedAuthenticatedUser(qc);
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('useAdminRoles hook - Group Mapping Persistence', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('creates a role and its mappings with one composite request', async () => {
    const rolesCreated: any[] = [];
    let standaloneMappingWrites = 0;

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
            group_mappings: body.group_mappings.map((sso_group_value: string, index: number) => ({
              id: `mapping-id-${index}`,
              sso_group_value,
            })),
            connection_policy_count: 0,
            created_at: '2026-06-05T00:00:00Z',
            updated_at: '2026-06-05T00:00:00Z',
          },
          { status: 201 }
        );
      }),
      http.post('*/admin/sso/group-mappings', () => {
        standaloneMappingWrites += 1;
        return HttpResponse.json({}, { status: 500 });
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

    expect(rolesCreated).toHaveLength(1);
    expect(rolesCreated[0]).toEqual({
      name: 'Custom Analyst',
      description: 'Analyst description',
      priority: 15,
      permissions: ['query.submit'],
      group_mappings: ['sso-analyst-group', 'sso-ops-group'],
      connection_policies: [],
    });
    expect(standaloneMappingWrites).toBe(0);
    expect(result.current.createMutation.data?.group_mappings).toHaveLength(2);
  });

  it('updates a role and its mapping diff with one composite request', async () => {
    const rolesUpdated: any[] = [];
    let standaloneMappingWrites = 0;

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
            group_mappings: body.group_mappings.map((sso_group_value: string, index: number) => ({
              id: `mapping-id-${index}`,
              sso_group_value,
            })),
            connection_policy_count: 0,
            created_at: '2026-06-05T00:00:00Z',
            updated_at: '2026-06-05T00:00:00Z',
          },
          { status: 200 }
        );
      }),
      http.post('*/admin/sso/group-mappings', () => {
        standaloneMappingWrites += 1;
        return HttpResponse.json({}, { status: 500 });
      }),
      http.delete('*/admin/sso/group-mappings/:mappingId', () => {
        standaloneMappingWrites += 1;
        return HttpResponse.json({}, { status: 500 });
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

    expect(rolesUpdated).toHaveLength(1);
    expect(rolesUpdated[0]).toEqual({
      id: 'role-uuid-999',
      name: 'Updated Analyst',
      description: 'New Description',
      priority: 20,
      permissions: ['query.submit', 'query.history.view'],
      group_mappings: ['sso-ops', 'sso-manager'],
      connection_policies: [],
    });
    expect(standaloneMappingWrites).toBe(0);
    expect(result.current.updateMutation.data?.group_mappings).toHaveLength(2);
  });

  it('does not fetch roles or group mappings when enabled is false', async () => {
    let rolesFetched = false;
    let mappingsFetched = false;

    server.use(
      http.get('*/admin/roles', () => {
        rolesFetched = true;
        return HttpResponse.json({ roles: [] });
      }),
      http.get('*/admin/sso/group-mappings', () => {
        mappingsFetched = true;
        return HttpResponse.json({ mappings: [] });
      })
    );

    renderHook(() => useAdminRoles({ enabled: false }), { wrapper });

    // Wait a short time to verify no request fires
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(rolesFetched).toBe(false);
    expect(mappingsFetched).toBe(false);
  });

  it('refetches authoritative detail after a definite server rejection', async () => {
    let detailReads = 0;
    const authoritativeRole = roleDetail({ name: 'Original Analyst', groupMappings: ['sso-old'] });
    server.use(
      http.put('*/admin/roles/:id', () =>
        HttpResponse.json({ detail: { code: 'group_mapping_conflict' } }, { status: 409 })
      ),
      http.get('*/admin/roles/:id', () => {
        detailReads += 1;
        return HttpResponse.json(authoritativeRole);
      })
    );

    const { result } = renderHook(() => useAdminRoles({ enabled: false }), { wrapper });
    result.current.updateMutation.mutate({
      id: authoritativeRole.id,
      data: roleDraft({ name: 'Rejected Analyst', groupMappings: ['sso-new'] }),
    });

    await waitFor(() => expect(result.current.updateMutation.isError).toBe(true));
    expect(detailReads).toBe(1);
    expect(result.current.updateMutation.error).toMatchObject({
      recovery: 'rejected',
      authoritativeRole: { name: 'Original Analyst' },
    });
  });

  it('recovers a committed update after its response is lost', async () => {
    const committedRole = roleDetail({ name: 'Committed Analyst', groupMappings: ['sso-new'] });
    server.use(
      http.put('*/admin/roles/:id', () => HttpResponse.error()),
      http.get('*/admin/roles/:id', () => HttpResponse.json(committedRole))
    );

    const { result } = renderHook(() => useAdminRoles({ enabled: false }), { wrapper });
    result.current.updateMutation.mutate({
      id: committedRole.id,
      data: roleDraft({ name: committedRole.name, groupMappings: ['sso-new'] }),
    });

    await waitFor(() => expect(result.current.updateMutation.isSuccess).toBe(true));
    expect(result.current.updateMutation.data).toMatchObject({
      name: 'Committed Analyst',
      group_mappings: [{ sso_group_value: 'sso-new' }],
    });
  });

  it('reports uncertainty when a lost update response did not commit', async () => {
    const authoritativeRole = roleDetail({ name: 'Original Analyst', groupMappings: ['sso-old'] });
    server.use(
      http.put('*/admin/roles/:id', () => HttpResponse.error()),
      http.get('*/admin/roles/:id', () => HttpResponse.json(authoritativeRole))
    );

    const { result } = renderHook(() => useAdminRoles({ enabled: false }), { wrapper });
    result.current.updateMutation.mutate({
      id: authoritativeRole.id,
      data: roleDraft({ name: 'Possibly Saved Analyst', groupMappings: ['sso-new'] }),
    });

    await waitFor(() => expect(result.current.updateMutation.isError).toBe(true));
    expect(result.current.updateMutation.error).toMatchObject({
      recovery: 'uncertain',
      authoritativeStateRefreshed: true,
      authoritativeRole: {
        name: 'Original Analyst',
        group_mappings: [{ sso_group_value: 'sso-old' }],
      },
    });
  });

  it('does not claim refresh when reconciliation also loses its response', async () => {
    server.use(
      http.put('*/admin/roles/:id', () => HttpResponse.error()),
      http.get('*/admin/roles/:id', () => HttpResponse.error())
    );

    const { result } = renderHook(() => useAdminRoles({ enabled: false }), { wrapper });
    result.current.updateMutation.mutate({
      id: 'role-unreachable-id',
      data: roleDraft({ name: 'Unknown Analyst', groupMappings: ['sso-unknown'] }),
    });

    await waitFor(() => expect(result.current.updateMutation.isError).toBe(true));
    expect(result.current.updateMutation.error).toMatchObject({
      recovery: 'uncertain',
      authoritativeStateRefreshed: false,
    });
  });

  it('recovers a committed create after its response is lost', async () => {
    let committed = false;
    const createdRole = roleDetail({ name: 'Created Analyst', groupMappings: ['sso-created'] });
    server.use(
      http.get('*/admin/roles', () =>
        HttpResponse.json({ roles: committed ? [createdRole] : [] })
      ),
      http.get('*/admin/sso/group-mappings', () => HttpResponse.json({ mappings: [] })),
      http.post('*/admin/roles', () => {
        committed = true;
        return HttpResponse.error();
      }),
      http.get('*/admin/roles/:id', () => HttpResponse.json(createdRole))
    );

    const { result } = renderHook(() => useAdminRoles(), { wrapper });
    await waitFor(() => expect(result.current.listQuery.isSuccess).toBe(true));
    result.current.createMutation.mutate(
      roleDraft({ name: createdRole.name, groupMappings: ['sso-created'] })
    );

    await waitFor(() => expect(result.current.createMutation.isSuccess).toBe(true));
    expect(result.current.createMutation.data).toMatchObject({
      id: createdRole.id,
      group_mappings: [{ sso_group_value: 'sso-created' }],
    });
  });

  it('reports uncertainty when a lost create response did not commit', async () => {
    let roleReads = 0;
    server.use(
      http.get('*/admin/roles', () => {
        roleReads += 1;
        return HttpResponse.json({ roles: [] });
      }),
      http.get('*/admin/sso/group-mappings', () => HttpResponse.json({ mappings: [] })),
      http.post('*/admin/roles', () => HttpResponse.error())
    );

    const { result } = renderHook(() => useAdminRoles(), { wrapper });
    await waitFor(() => expect(result.current.listQuery.isSuccess).toBe(true));
    result.current.createMutation.mutate(
      roleDraft({ name: 'Uncommitted Analyst', groupMappings: ['sso-missing'] })
    );

    await waitFor(() => expect(result.current.createMutation.isError).toBe(true));
    expect(roleReads).toBeGreaterThanOrEqual(2);
    expect(result.current.createMutation.error).toMatchObject({ recovery: 'uncertain' });
  });
});

function roleDraft({ name, groupMappings }: { name: string; groupMappings: string[] }) {
  return {
    name,
    description: 'Analyst description',
    priority: 15,
    permissions: ['query.submit'],
    group_mappings: groupMappings,
    connection_policies: [],
  };
}

function roleDetail({ name, groupMappings }: { name: string; groupMappings: string[] }) {
  return {
    id: 'role-recovery-id',
    name,
    description: 'Analyst description',
    priority: 15,
    permissions: ['query.submit'],
    is_builtin: false,
    group_mappings: groupMappings.map((sso_group_value, index) => ({
      id: `mapping-recovery-${index}`,
      sso_group_value,
    })),
    connection_policy_count: 0,
    connection_policies: [],
    created_at: '2026-06-05T00:00:00Z',
    updated_at: '2026-06-05T00:00:00Z',
  };
}

describe('useDraftRolePolicyPreview', () => {
  it('posts the complete unsaved policy to the canonical draft endpoint', async () => {
    const requests: unknown[] = [];
    server.use(
      http.post('*/admin/roles/test-policy', async ({ request }) => {
        requests.push(await request.json());
        return HttpResponse.json({
          accessible_tables: ['users'],
          accessible_columns: { users: ['id'] },
          blocked_tables: [],
          applicable_row_filters: [],
          masked_columns: {},
          would_be_allowed: true,
          message_key: null,
        });
      })
    );
    const draft = {
      question: 'Show unsaved users',
      sample_sql: 'SELECT id FROM users',
      connection_policy: {
        connection_id: 'connection-draft',
        allowed_tables: [{ table: 'users', columns: ['id'] }],
        row_filters: [],
        column_masks: [],
      },
    };

    const { result } = renderHook(() => useDraftRolePolicyPreview(), { wrapper });
    result.current.mutate(draft);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(requests).toEqual([draft]);
    expect(result.current.data?.would_be_allowed).toBe(true);
  });
});
