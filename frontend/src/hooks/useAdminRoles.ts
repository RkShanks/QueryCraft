import { useQuery, useMutation } from '@tanstack/react-query';

export const useAdminRoles = (options?: any) => {
  return {
    listQuery: { data: { roles: [] }, isLoading: false, isError: false },
    createMutation: { mutate: () => {}, isPending: false },
    updateMutation: { mutate: () => {}, isPending: false },
    deleteMutation: { mutate: () => {}, isPending: false },
    groupMappingsQuery: { data: { mappings: [] }, isLoading: false },
    createGroupMappingMutation: { mutate: () => {}, isPending: false },
    deleteGroupMappingMutation: { mutate: () => {}, isPending: false },
  } as any;
};
