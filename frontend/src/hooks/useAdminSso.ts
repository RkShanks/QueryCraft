import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listAdminSsoProviders,
  createSsoProvider,
  updateSsoProvider,
  deleteSsoProvider,
} from '../api/generated/sdk.gen';
import type {
  SsoProviderCreateWritable as SsoProviderCreate,
  SsoProviderUpdateWritable as SsoProviderUpdate,
} from '../api/generated/types.gen';
import { PERMISSIONS } from '../auth/permissions';
import { requirePermission, usePermission } from './usePermission';

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
  const canManageSso = usePermission(PERMISSIONS.ADMIN_SSO_MANAGE);

  const listQuery = useQuery({
    queryKey: ['adminSsoProviders'],
    queryFn: ({ signal }) =>
      listAdminSsoProviders({ throwOnError: true, signal }).then((res) => res.data),
    enabled: canManageSso,
  });

  const createMutation = useMutation({
    mutationFn: (data: SsoProviderCreate) => {
      requirePermission(canManageSso, PERMISSIONS.ADMIN_SSO_MANAGE);
      return createSsoProvider({ body: data, throwOnError: true }).then((res) => res.data);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['adminSsoProviders'] });
      options?.onCreateSuccess?.(data);
    },
    onError: (err) => {
      options?.onCreateError?.(err);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: SsoProviderUpdate }) => {
      requirePermission(canManageSso, PERMISSIONS.ADMIN_SSO_MANAGE);
      return updateSsoProvider({ path: { provider_id: id }, body: data, throwOnError: true }).then(
        (res) => res.data
      );
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['adminSsoProviders'] });
      options?.onUpdateSuccess?.(data);
    },
    onError: (err) => {
      options?.onUpdateError?.(err);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => {
      requirePermission(canManageSso, PERMISSIONS.ADMIN_SSO_MANAGE);
      return deleteSsoProvider({ path: { provider_id: id }, throwOnError: true });
    },
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
