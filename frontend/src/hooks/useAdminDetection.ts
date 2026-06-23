import { useQuery, useMutation } from '@tanstack/react-query';
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
  const configQuery = useQuery<DetectionConfig>({
    queryKey: ['adminDetectionConfig'],
    queryFn: getDetectionConfig,
    enabled: false,
  });

  const updateMutation = useMutation({
    mutationFn: (data: DetectionConfigUpdate) => updateDetectionConfig(data),
  });

  return {
    configQuery,
    updateMutation,
  };
};
