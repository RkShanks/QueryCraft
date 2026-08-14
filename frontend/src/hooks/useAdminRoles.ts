import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  createGroupMapping,
  createRole,
  deleteGroupMapping,
  deleteRole,
  getRole,
  listGroupMappings,
  listRoles,
  testDraftRolePolicy,
  updateRole,
} from '../api/generated/sdk.gen';
import type {
  ConnectionPolicyResponse,
  DraftPolicyTestRequest,
  GroupMappingResponse,
  PolicyTestResponse,
  RoleCreate,
  RoleDetailResponse,
  RoleGroupMappingSummary,
  RoleResponse,
  RoleUpdate,
} from '../api/generated/types.gen';
import { PERMISSIONS } from '../auth/permissions';
import { requirePermission, usePermission } from './usePermission';

export type ConnectionPolicyItem = Omit<
  ConnectionPolicyResponse,
  'allowed_tables' | 'column_masks' | 'id' | 'row_filters'
> & {
  id?: string;
  allowed_tables: NonNullable<ConnectionPolicyResponse['allowed_tables']>;
  column_masks: NonNullable<ConnectionPolicyResponse['column_masks']>;
  row_filters: NonNullable<ConnectionPolicyResponse['row_filters']>;
};

export type Role = Omit<
  RoleResponse,
  'group_mappings' | 'permissions' | 'is_builtin' | 'connection_policy_count'
> & {
  permissions: NonNullable<RoleResponse['permissions']>;
  is_builtin: NonNullable<RoleResponse['is_builtin']>;
  group_mappings: RoleGroupMappingSummary[];
  connection_policy_count: NonNullable<RoleResponse['connection_policy_count']>;
  connection_policies?: ConnectionPolicyItem[];
};

export type RoleCreateData = Omit<
  RoleCreate,
  'connection_policies' | 'group_mappings' | 'permissions'
> & {
  permissions: string[];
  group_mappings: string[];
  connection_policies?: ConnectionPolicyItem[];
};

export type RoleUpdateData = Omit<RoleUpdate, 'connection_policies' | 'group_mappings'> & {
  group_mappings?: string[];
  connection_policies?: ConnectionPolicyItem[];
};

export type GroupMapping = GroupMappingResponse;

function normalizeRole(role: RoleResponse | RoleDetailResponse): Role {
  const connectionPolicies =
    'connection_policies' in role
      ? role.connection_policies?.map((policy) => ({
          ...policy,
          allowed_tables: policy.allowed_tables ?? [],
          column_masks: policy.column_masks ?? [],
          row_filters: policy.row_filters ?? [],
        }))
      : undefined;
  return {
    ...role,
    permissions: role.permissions ?? [],
    is_builtin: role.is_builtin ?? false,
    group_mappings: role.group_mappings ?? [],
    connection_policy_count:
      'connection_policy_count' in role
        ? (role.connection_policy_count ?? 0)
        : (connectionPolicies?.length ?? 0),
    connection_policies: connectionPolicies,
  };
}

export interface UseAdminRolesOptions {
  onCreateSuccess?: (data: unknown) => void;
  onCreateError?: (error: unknown) => void;
  onUpdateSuccess?: (data: unknown) => void;
  onUpdateError?: (error: unknown) => void;
  onDeleteSuccess?: (data: unknown) => void;
  onDeleteError?: (error: unknown) => void;
  enabled?: boolean;
}

export const useAdminRoles = (options?: UseAdminRolesOptions) => {
  const queryClient = useQueryClient();
  const canManageRoles = usePermission(PERMISSIONS.ADMIN_ROLES_MANAGE);

  const listQuery = useQuery<{ roles: Role[] }>({
    queryKey: ['adminRoles'],
    queryFn: () =>
      listRoles({ throwOnError: true }).then((response) => ({
        roles: response.data.roles.map(normalizeRole),
      })),
    enabled: canManageRoles && options?.enabled !== false,
  });

  const createMutation = useMutation({
    mutationFn: async (data: RoleCreateData) => {
      requirePermission(canManageRoles, PERMISSIONS.ADMIN_ROLES_MANAGE);
      const response = await createRole({
        body: {
          name: data.name,
          description: data.description,
          priority: data.priority,
          permissions: data.permissions,
          group_mappings: data.group_mappings,
          connection_policies: data.connection_policies || [],
        },
        throwOnError: true,
      });
      return normalizeRole(response.data);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['adminRoles'] });
      queryClient.invalidateQueries({ queryKey: ['adminGroupMappings'] });
      options?.onCreateSuccess?.(data);
    },
    onError: (err) => {
      options?.onCreateError?.(err);
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data: RoleUpdateData;
      existingMappings?: Array<{ id: string; sso_group_value: string }>;
    }) => {
      requirePermission(canManageRoles, PERMISSIONS.ADMIN_ROLES_MANAGE);
      const response = await updateRole({
        path: { role_id: id },
        body: {
          name: data.name,
          description: data.description,
          priority: data.priority,
          permissions: data.permissions,
          group_mappings: data.group_mappings,
          connection_policies: data.connection_policies || [],
        },
        throwOnError: true,
      });
      return normalizeRole(response.data);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['adminRoles'] });
      queryClient.invalidateQueries({ queryKey: ['adminGroupMappings'] });
      options?.onUpdateSuccess?.(data);
    },
    onError: (err) => {
      options?.onUpdateError?.(err);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => {
      requirePermission(canManageRoles, PERMISSIONS.ADMIN_ROLES_MANAGE);
      return deleteRole({ path: { role_id: id }, throwOnError: true });
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['adminRoles'] });
      options?.onDeleteSuccess?.(data);
    },
    onError: (err) => {
      options?.onDeleteError?.(err);
    },
  });

  // Standalone group mapping queries and mutations
  const groupMappingsQuery = useQuery<{ mappings: GroupMapping[] }>({
    queryKey: ['adminGroupMappings'],
    queryFn: () => listGroupMappings({ throwOnError: true }).then((response) => response.data),
    enabled: canManageRoles && options?.enabled !== false,
  });

  const createGroupMappingMutation = useMutation({
    mutationFn: (data: { sso_group_value: string; role_id: string }) => {
      requirePermission(canManageRoles, PERMISSIONS.ADMIN_ROLES_MANAGE);
      return createGroupMapping({ body: data, throwOnError: true }).then(
        (response) => response.data
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminGroupMappings'] });
      queryClient.invalidateQueries({ queryKey: ['adminRoles'] });
    },
  });

  const deleteGroupMappingMutation = useMutation({
    mutationFn: (id: string) => {
      requirePermission(canManageRoles, PERMISSIONS.ADMIN_ROLES_MANAGE);
      return deleteGroupMapping({ path: { mapping_id: id }, throwOnError: true });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminGroupMappings'] });
      queryClient.invalidateQueries({ queryKey: ['adminRoles'] });
    },
  });

  return {
    listQuery,
    createMutation,
    updateMutation,
    deleteMutation,
    groupMappingsQuery,
    createGroupMappingMutation,
    deleteGroupMappingMutation,
  };
};

/**
 * Fetch a single role by id with its full detail (including
 * `connection_policies`). The list endpoint `GET /admin/roles` only
 * returns `connection_policy_count`, so the editor must hit this
 * detail endpoint when opening an existing role. Pass `null` to
 * disable the query.
 */
export const useAdminRole = (roleId: string | null | undefined) => {
  const canManageRoles = usePermission(PERMISSIONS.ADMIN_ROLES_MANAGE);
  return useQuery<Role>({
    queryKey: ['adminRole', roleId],
    queryFn: async () => {
      if (!roleId) {
        throw new Error('Role id is required');
      }
      const response = await getRole({
        path: { role_id: roleId },
        throwOnError: true,
      });
      return normalizeRole(response.data);
    },
    enabled: !!roleId && canManageRoles,
  });
};

export const useDraftRolePolicyPreview = () => {
  const canManageRoles = usePermission(PERMISSIONS.ADMIN_ROLES_MANAGE);

  return useMutation<PolicyTestResponse, unknown, DraftPolicyTestRequest>({
    mutationFn: async (draft) => {
      requirePermission(canManageRoles, PERMISSIONS.ADMIN_ROLES_MANAGE);
      const response = await testDraftRolePolicy({
        body: draft,
        throwOnError: true,
      });
      return response.data;
    },
  });
};
