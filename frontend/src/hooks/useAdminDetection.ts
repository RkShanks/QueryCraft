import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getDetectionConfig,
  updateDetectionConfig,
  type DetectionConfig,
  type DetectionConfigUpdate,
} from '../api/detection';

export interface UseAdminDetectionOptions {
  onUpdateSuccess?: (data: DetectionConfig) => void;
  onUpdateError?: (error: unknown) => void;
}

export const useAdminDetection = (options?: UseAdminDetectionOptions) => {
  const queryClient = useQueryClient();

  const configQuery = useQuery<DetectionConfig>({
    queryKey: ['adminDetectionConfig'],
    queryFn: getDetectionConfig,
  });

  const updateMutation = useMutation({
    mutationFn: (data: DetectionConfigUpdate) => updateDetectionConfig(data),
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
