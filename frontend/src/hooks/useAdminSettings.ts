import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getAdminSettings, updateAdminSettings } from '../api/generated/sdk.gen';
import type { UpdateAdminSettingsData } from '../api/generated/types.gen';
import { PERMISSIONS } from '../auth/permissions';
import { requirePermission, usePermission } from './usePermission';

export const useAdminSettings = () => {
  const canManageConnections = usePermission(PERMISSIONS.ADMIN_CONNECTIONS_MANAGE);
  return useQuery({
    queryKey: ['adminSettings'],
    queryFn: () =>
      getAdminSettings({ throwOnError: true }).then((res) => res.data),
    enabled: canManageConnections,
  });
};

export const useUpdateAdminSettings = () => {
  const queryClient = useQueryClient();
  const canManageConnections = usePermission(PERMISSIONS.ADMIN_CONNECTIONS_MANAGE);
  return useMutation({
    mutationFn: (data: UpdateAdminSettingsData['body']) => {
      requirePermission(canManageConnections, PERMISSIONS.ADMIN_CONNECTIONS_MANAGE);
      return updateAdminSettings({ body: data, throwOnError: true }).then(
        (res) => res.data
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminSettings'] });
    },
  });
};
