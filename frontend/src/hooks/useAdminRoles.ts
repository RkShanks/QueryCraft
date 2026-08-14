import { useQuery, useMutation, useQueryClient, type QueryClient } from '@tanstack/react-query';
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

export type RoleSaveRecovery = 'rejected' | 'uncertain';

export class RoleSaveError extends Error {
  readonly authoritativeRole?: Role;
  readonly authoritativeStateRefreshed: boolean;
  readonly recovery: RoleSaveRecovery;
  readonly serverError: unknown;

  constructor(
    recovery: RoleSaveRecovery,
    serverError: unknown,
    authoritativeRole?: Role,
    authoritativeStateRefreshed = false
  ) {
    super(`role_save_${recovery}`);
    this.name = 'RoleSaveError';
    this.recovery = recovery;
    this.serverError = serverError;
    this.authoritativeRole = authoritativeRole;
    this.authoritativeStateRefreshed = authoritativeStateRefreshed;
  }
}

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

function isAmbiguousNetworkFailure(error: unknown): boolean {
  return error instanceof TypeError || error instanceof DOMException;
}

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value
      .map(canonicalize)
      .sort((left, right) => JSON.stringify(left).localeCompare(JSON.stringify(right)));
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, entry]) => [key, canonicalize(entry)])
    );
  }
  return value;
}

function sameValue(left: unknown, right: unknown): boolean {
  return JSON.stringify(canonicalize(left)) === JSON.stringify(canonicalize(right));
}

function roleMatchesUpdate(role: Role, data: RoleUpdateData): boolean {
  const scalarFields: Array<keyof Pick<RoleUpdateData, 'description' | 'name' | 'priority'>> = [
    'name',
    'description',
    'priority',
  ];
  if (scalarFields.some((field) => data[field] !== undefined && role[field] !== data[field])) {
    return false;
  }
  if (data.permissions !== undefined && !sameValue(role.permissions, data.permissions)) {
    return false;
  }
  if (
    data.group_mappings !== undefined &&
    !sameValue(
      role.group_mappings.map((mapping) => mapping.sso_group_value),
      data.group_mappings
    )
  ) {
    return false;
  }
  if (data.connection_policies !== undefined) {
    const authoritativePolicies = (role.connection_policies ?? []).map(
      ({ connection_id, allowed_tables, column_masks, row_filters }) => ({
        connection_id,
        allowed_tables,
        column_masks,
        row_filters,
      })
    );
    const requestedPolicies = data.connection_policies.map(
      ({ connection_id, allowed_tables, column_masks, row_filters }) => ({
        connection_id,
        allowed_tables,
        column_masks,
        row_filters,
      })
    );
    if (!sameValue(authoritativePolicies, requestedPolicies)) {
      return false;
    }
  }
  return true;
}

function roleCouldBeCreatedCandidate(role: Role, data: RoleCreateData): boolean {
  return (
    role.name === data.name &&
    role.description === (data.description ?? null) &&
    role.priority === data.priority &&
    sameValue(role.permissions, data.permissions) &&
    sameValue(
      role.group_mappings.map((mapping) => mapping.sso_group_value),
      data.group_mappings
    )
  );
}

function roleMatchesCreate(role: Role, data: RoleCreateData): boolean {
  return roleMatchesUpdate(role, {
    ...data,
    connection_policies: data.connection_policies ?? [],
  });
}

async function fetchAuthoritativeRole(roleId: string): Promise<Role | undefined> {
  try {
    const response = await getRole({ path: { role_id: roleId }, throwOnError: true });
    return normalizeRole(response.data);
  } catch {
    return undefined;
  }
}

async function fetchAuthoritativeRoles(): Promise<Role[] | undefined> {
  try {
    const response = await listRoles({ throwOnError: true });
    return response.data.roles.map(normalizeRole);
  } catch {
    return undefined;
  }
}

function publishAuthoritativeRole(queryClient: QueryClient, role: Role): void {
  queryClient.setQueryData(['adminRole', role.id], role);
  queryClient.setQueryData<{ roles: Role[] }>(['adminRoles'], (current) => {
    if (!current) {
      return current;
    }
    return {
      roles: current.roles.map((listedRole) =>
        listedRole.id === role.id ? role : listedRole
      ),
    };
  });
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
      const rolesBeforeSave = await fetchAuthoritativeRoles();
      if (rolesBeforeSave) {
        queryClient.setQueryData(['adminRoles'], { roles: rolesBeforeSave });
      }
      const priorRoleIds = rolesBeforeSave
        ? new Set(rolesBeforeSave.map((role) => role.id))
        : undefined;
      try {
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
      } catch (error) {
        const authoritativeRoles = await fetchAuthoritativeRoles();
        if (authoritativeRoles) {
          queryClient.setQueryData(['adminRoles'], { roles: authoritativeRoles });
        }
        if (isAmbiguousNetworkFailure(error) && authoritativeRoles && priorRoleIds) {
          const candidates = authoritativeRoles.filter(
            (role) =>
              !priorRoleIds.has(role.id) && roleCouldBeCreatedCandidate(role, data)
          );
          const candidateDetails = await Promise.all(
            candidates.map((role) => fetchAuthoritativeRole(role.id))
          );
          const committedRoles = candidateDetails.filter(
            (role): role is Role => !!role && roleMatchesCreate(role, data)
          );
          if (committedRoles.length === 1) {
            return committedRoles[0];
          }
        }
        throw new RoleSaveError(
          isAmbiguousNetworkFailure(error) ? 'uncertain' : 'rejected',
          error,
          undefined,
          authoritativeRoles !== undefined
        );
      }
    },
    onSuccess: (data) => {
      queryClient.setQueryData(['adminRole', data.id], data);
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
    }) => {
      requirePermission(canManageRoles, PERMISSIONS.ADMIN_ROLES_MANAGE);
      try {
        const response = await updateRole({
          path: { role_id: id },
          body: {
            name: data.name,
            description: data.description,
            priority: data.priority,
            permissions: data.permissions,
            group_mappings: data.group_mappings,
            connection_policies: data.connection_policies,
          },
          throwOnError: true,
        });
        return normalizeRole(response.data);
      } catch (error) {
        const authoritativeRole = await fetchAuthoritativeRole(id);
        if (authoritativeRole) {
          publishAuthoritativeRole(queryClient, authoritativeRole);
        }
        if (
          isAmbiguousNetworkFailure(error) &&
          authoritativeRole &&
          roleMatchesUpdate(authoritativeRole, data)
        ) {
          return authoritativeRole;
        }
        throw new RoleSaveError(
          isAmbiguousNetworkFailure(error) ? 'uncertain' : 'rejected',
          error,
          authoritativeRole,
          authoritativeRole !== undefined
        );
      }
    },
    onSuccess: (data) => {
      queryClient.setQueryData(['adminRole', data.id], data);
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
