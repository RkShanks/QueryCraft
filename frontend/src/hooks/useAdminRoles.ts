import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { client } from '../api/generated/client.gen';

export interface ConnectionPolicyItem {
  id?: string;
  connection_id: string;
  allowed_tables: Array<{ table: string; columns: string[] }>;
  row_filters: Array<{ table: string; filter: string }>;
  column_masks: Array<{ table: string; columns: string[] }>;
}

export interface Role {
  id: string;
  name: string;
  description?: string;
  priority: number;
  permissions: string[];
  is_builtin: boolean;
  group_mappings: Array<{ id: string; sso_group_value: string }>;
  connection_policy_count: number;
  connection_policies?: ConnectionPolicyItem[];
  created_at: string;
  updated_at: string;
}

export interface RoleCreateData {
  name: string;
  description?: string;
  priority: number;
  permissions: string[];
  group_mappings: string[];
  connection_policies?: ConnectionPolicyItem[];
}

export interface RoleUpdateData {
  name?: string;
  description?: string;
  priority?: number;
  permissions?: string[];
  group_mappings?: string[];
  connection_policies?: ConnectionPolicyItem[];
}

export interface GroupMapping {
  id: string;
  sso_group_value: string;
  role_id: string;
  role_name: string;
  created_at: string;
}

export interface UseAdminRolesOptions {
  onCreateSuccess?: (data: unknown) => void;
  onCreateError?: (error: unknown) => void;
  onUpdateSuccess?: (data: unknown) => void;
  onUpdateError?: (error: unknown) => void;
  onDeleteSuccess?: (data: unknown) => void;
  onDeleteError?: (error: unknown) => void;
}

export const useAdminRoles = (options?: UseAdminRolesOptions) => {
  const queryClient = useQueryClient();

  const listQuery = useQuery<{ roles: Role[] }>({
    queryKey: ['adminRoles'],
    queryFn: () =>
      client
        .get({ url: '/admin/roles', throwOnError: true })
        .then((res) => res.data as { roles: Role[] }),
  });

  const createMutation = useMutation({
    mutationFn: async (data: RoleCreateData) => {
      const res = await client.post({
        url: '/admin/roles',
        body: {
          name: data.name,
          description: data.description,
          priority: data.priority,
          permissions: data.permissions,
          connection_policies: data.connection_policies || [],
        },
        throwOnError: true,
      });
      const createdRole = res.data as Role;

      if (data.group_mappings && data.group_mappings.length > 0) {
        await Promise.all(
          data.group_mappings.map((group) =>
            client.post({
              url: '/admin/sso/group-mappings',
              body: { sso_group_value: group, role_id: createdRole.id },
              throwOnError: true,
            })
          )
        );
      }
      return createdRole;
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
      existingMappings = [],
    }: {
      id: string;
      data: RoleUpdateData;
      existingMappings?: Array<{ id: string; sso_group_value: string }>;
    }) => {
      const res = await client.put({
        url: `/admin/roles/${id}`,
        body: {
          name: data.name,
          description: data.description,
          priority: data.priority,
          permissions: data.permissions,
          connection_policies: data.connection_policies || [],
        },
        throwOnError: true,
      });
      const updatedRole = res.data as Role;

      if (data.group_mappings) {
        const newGroups = data.group_mappings;
        const existingGroupNames = existingMappings.map((em) => em.sso_group_value);

        const groupsToAdd = newGroups.filter((g) => !existingGroupNames.includes(g));
        const mappingsToDelete = existingMappings.filter(
          (em) => !newGroups.includes(em.sso_group_value)
        );

        await Promise.all([
          ...groupsToAdd.map((group) =>
            client.post({
              url: '/admin/sso/group-mappings',
              body: { sso_group_value: group, role_id: id },
              throwOnError: true,
            })
          ),
          ...mappingsToDelete.map((mapping) =>
            client.delete({
              url: `/admin/sso/group-mappings/${mapping.id}`,
              throwOnError: true,
            })
          ),
        ]);
      }
      return updatedRole;
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
    mutationFn: (id: string) =>
      client.delete({ url: `/admin/roles/${id}`, throwOnError: true }),
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
    queryFn: () =>
      client
        .get({ url: '/admin/sso/group-mappings', throwOnError: true })
        .then((res) => res.data as { mappings: GroupMapping[] }),
  });

  const createGroupMappingMutation = useMutation({
    mutationFn: (data: { sso_group_value: string; role_id: string }) =>
      client
        .post({ url: '/admin/sso/group-mappings', body: data, throwOnError: true })
        .then((res) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminGroupMappings'] });
      queryClient.invalidateQueries({ queryKey: ['adminRoles'] });
    },
  });

  const deleteGroupMappingMutation = useMutation({
    mutationFn: (id: string) =>
      client.delete({ url: `/admin/sso/group-mappings/${id}`, throwOnError: true }),
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
  return useQuery<Role>({
    queryKey: ['adminRole', roleId],
    queryFn: async () => {
      if (!roleId) {
        throw new Error('Role id is required');
      }
      const res = await client.get({
        url: `/admin/roles/${roleId}`,
        throwOnError: true,
      });
      return res.data as Role;
    },
    enabled: !!roleId,
  });
};
