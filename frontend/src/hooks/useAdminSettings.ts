import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getAdminSettings, updateAdminSettings } from '../api/generated/sdk.gen';
import type { UpdateAdminSettingsData } from '../api/generated/types.gen';

export const useAdminSettings = () => {
  return useQuery({
    queryKey: ['adminSettings'],
    queryFn: () =>
      getAdminSettings({ throwOnError: true }).then((res) => res.data),
  });
};

export const useUpdateAdminSettings = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: UpdateAdminSettingsData['body']) =>
      updateAdminSettings({ body: data, throwOnError: true }).then((res) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminSettings'] });
    },
  });
};
