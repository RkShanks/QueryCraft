import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listAdminSsoProviders,
  createSsoProvider,
  updateSsoProvider,
  deleteSsoProvider,
} from '../api/generated/sdk.gen';
import type {
  SsoProviderCreate,
  SsoProviderUpdate,
} from '../api/generated/types.gen';

export interface UseAdminSsoOptions {
  onCreateSuccess?: (data: unknown) => void;
  onCreateError?: (error: unknown) => void;
  onUpdateSuccess?: (data: unknown) => void;
  onUpdateError?: (error: unknown) => void;
  onDeleteSuccess?: (data: unknown) => void;
  onDeleteError?: (error: unknown) => void;
}

export const useAdminSso = (options?: UseAdminSsoOptions) => {
  const queryClient = useQueryClient();

  const listQuery = useQuery({
    queryKey: ['adminSsoProviders'],
    queryFn: () => listAdminSsoProviders({ throwOnError: true }).then((res) => res.data),
  });

  const createMutation = useMutation({
    mutationFn: (data: SsoProviderCreate) =>
      createSsoProvider({ body: data, throwOnError: true }).then((res) => res.data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['adminSsoProviders'] });
      options?.onCreateSuccess?.(data);
    },
    onError: (err) => {
      options?.onCreateError?.(err);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: SsoProviderUpdate }) =>
      updateSsoProvider({ path: { providerId: id }, body: data, throwOnError: true }).then(
        (res) => res.data
      ),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['adminSsoProviders'] });
      options?.onUpdateSuccess?.(data);
    },
    onError: (err) => {
      options?.onUpdateError?.(err);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      deleteSsoProvider({ path: { providerId: id }, throwOnError: true }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['adminSsoProviders'] });
      options?.onDeleteSuccess?.(data);
    },
    onError: (err) => {
      options?.onDeleteError?.(err);
    },
  });

  return {
    listQuery,
    createMutation,
    updateMutation,
    deleteMutation,
  };
};
