import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { SsoProviderCreate, SsoProviderUpdate, SsoProviderResponse } from '../api/generated/types.gen';

export const useAdminSso = () => {
  const queryClient = useQueryClient();

  const listQuery = useQuery({
    queryKey: ['adminSsoProviders'],
    queryFn: async () => ({ providers: [] }),
  });

  const createMutation = useMutation({
    mutationFn: async (data: SsoProviderCreate) => ({} as SsoProviderResponse),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminSsoProviders'] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: string; data: SsoProviderUpdate }) => ({} as SsoProviderResponse),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminSsoProviders'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {},
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminSsoProviders'] });
    },
  });

  return {
    listQuery,
    createMutation,
    updateMutation,
    deleteMutation,
  };
};
