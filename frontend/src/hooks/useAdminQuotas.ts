import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listQuotas,
  getQuotaStatus,
  upsertQuota,
  deleteQuota,
  type RoleQuotaConfig,
  type RoleQuotaUpsert,
  type RoleQuotaStatus,
} from '../api/quotas';
import { PERMISSIONS } from '../auth/permissions';
import { requirePermission, usePermission } from './usePermission';

export interface UseAdminQuotasOptions {
  onUpsertSuccess?: (data: RoleQuotaConfig) => void;
  onUpsertError?: (error: unknown) => void;
  onDeleteSuccess?: () => void;
  onDeleteError?: (error: unknown) => void;
}

export const useAdminQuotas = (options?: UseAdminQuotasOptions) => {
  const queryClient = useQueryClient();
  const canManageQuotas = usePermission(PERMISSIONS.ADMIN_QUOTAS_MANAGE);

  const listQuery = useQuery<{ quotas: RoleQuotaConfig[] }>({
    queryKey: ['adminQuotas'],
    queryFn: listQuotas,
    enabled: canManageQuotas,
  });

  const statusQuery = useQuery<{ status: RoleQuotaStatus[] }>({
    queryKey: ['adminQuotasStatus'],
    queryFn: getQuotaStatus,
    enabled: canManageQuotas,
  });

  const upsertMutation = useMutation({
    mutationFn: ({ roleId, data }: { roleId: string; data: RoleQuotaUpsert }) => {
      requirePermission(canManageQuotas, PERMISSIONS.ADMIN_QUOTAS_MANAGE);
      return upsertQuota(roleId, data);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['adminQuotas'] });
      queryClient.invalidateQueries({ queryKey: ['adminQuotasStatus'] });
      options?.onUpsertSuccess?.(data);
    },
    onError: (error) => {
      options?.onUpsertError?.(error);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (roleId: string) => {
      requirePermission(canManageQuotas, PERMISSIONS.ADMIN_QUOTAS_MANAGE);
      return deleteQuota(roleId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminQuotas'] });
      queryClient.invalidateQueries({ queryKey: ['adminQuotasStatus'] });
      options?.onDeleteSuccess?.();
    },
    onError: (error) => {
      options?.onDeleteError?.(error);
    },
  });

  return {
    listQuery,
    statusQuery,
    upsertMutation,
    deleteMutation,
  };
};
