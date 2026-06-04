import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { client } from '../api/generated/client.gen';

export interface Role {
  id: string;
  name: string;
  description?: string;
  priority: number;
  permissions: string[];
  is_builtin: boolean;
  group_mappings: Array<{ id: string; sso_group_value: string }>;
  connection_policy_count: number;
  created_at: string;
  updated_at: string;
}

export interface RoleCreateData {
  name: string;
  description?: string;
  priority: number;
  permissions: string[];
  group_mappings: string[];
}

export interface RoleUpdateData {
  name?: string;
  description?: string;
  priority?: number;
  permissions?: string[];
  group_mappings?: string[];
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
    mutationFn: (data: RoleCreateData) =>
      client.post({ url: '/admin/roles', body: data, throwOnError: true }).then((res) => res.data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['adminRoles'] });
      options?.onCreateSuccess?.(data);
    },
    onError: (err) => {
      options?.onCreateError?.(err);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: RoleUpdateData }) =>
      client.put({ url: `/admin/roles/${id}`, body: data, throwOnError: true }).then((res) => res.data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['adminRoles'] });
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
