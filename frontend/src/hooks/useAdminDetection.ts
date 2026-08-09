import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getDetectionConfig,
  updateDetectionConfig,
  type DetectionConfig,
  type DetectionConfigUpdate,
} from '../api/detection';
import { PERMISSIONS } from '../auth/permissions';
import { requirePermission, usePermission } from './usePermission';

export interface UseAdminDetectionOptions {
  onUpdateSuccess?: (data: DetectionConfig) => void;
  onUpdateError?: (error: unknown) => void;
}

export const useAdminDetection = (options?: UseAdminDetectionOptions) => {
  const queryClient = useQueryClient();
  const canManageSecurity = usePermission(PERMISSIONS.ADMIN_SECURITY_MANAGE);

  const configQuery = useQuery<DetectionConfig>({
    queryKey: ['adminDetectionConfig'],
    queryFn: getDetectionConfig,
    enabled: canManageSecurity,
  });

  const updateMutation = useMutation({
    mutationFn: (data: DetectionConfigUpdate) => {
      requirePermission(canManageSecurity, PERMISSIONS.ADMIN_SECURITY_MANAGE);
      return updateDetectionConfig(data);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['adminDetectionConfig'] });
      options?.onUpdateSuccess?.(data);
    },
    onError: (error) => {
      options?.onUpdateError?.(error);
    },
  });

  return {
    configQuery,
    updateMutation,
  };
};
