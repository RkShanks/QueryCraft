import {
  type InfiniteData,
  useInfiniteQuery,
  useQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import {
  listQuotas,
  getQuotaStatus,
  upsertQuota,
  deleteQuota,
  type RoleQuotaConfig,
  type RoleQuotaUpsert,
  type RoleQuotaStatus,
  type QuotaStatusPage,
} from '../api/quotas';
import { PERMISSIONS } from '../auth/permissions';
import { requirePermission, usePermission } from './usePermission';

export interface UseAdminQuotasOptions {
  onUpsertSuccess?: (data: RoleQuotaConfig) => void;
  onUpsertError?: (error: unknown) => void;
  onDeleteSuccess?: () => void;
  onDeleteError?: (error: unknown) => void;
}

function flattenedQuotaStatus(
  pages: InfiniteData<QuotaStatusPage, string | undefined> | undefined
): QuotaStatusPage | undefined {
  if (!pages?.pages.length) return undefined;
  const seenRoleIds = new Set<string>();
  const status: RoleQuotaStatus[] = [];
  for (const page of pages.pages) {
    for (const roleStatus of page.status) {
      if (seenRoleIds.has(roleStatus.role_id)) continue;
      seenRoleIds.add(roleStatus.role_id);
      status.push(roleStatus);
    }
  }
  return {
    status,
    total: pages.pages[0].total,
    next_cursor: pages.pages.at(-1)?.next_cursor ?? null,
  };
}

export const useAdminQuotas = (options?: UseAdminQuotasOptions) => {
  const queryClient = useQueryClient();
  const canManageQuotas = usePermission(PERMISSIONS.ADMIN_QUOTAS_MANAGE);

  const listQuery = useQuery<{ quotas: RoleQuotaConfig[] }>({
    queryKey: ['adminQuotas'],
    queryFn: listQuotas,
    enabled: canManageQuotas,
  });

  const statusInfiniteQuery = useInfiniteQuery({
    queryKey: ['adminQuotasStatus'],
    queryFn: ({ pageParam, signal }) => getQuotaStatus(pageParam, signal),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled: canManageQuotas,
  });
  const statusQuery = {
    ...statusInfiniteQuery,
    data: flattenedQuotaStatus(statusInfiniteQuery.data),
  };

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
    onError: async (error) => {
      await queryClient.refetchQueries({ queryKey: ['adminQuotas'], type: 'active' });
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
    onError: async (error) => {
      await queryClient.refetchQueries({ queryKey: ['adminQuotas'], type: 'active' });
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
