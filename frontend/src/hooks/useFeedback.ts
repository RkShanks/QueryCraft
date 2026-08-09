import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateFeedback } from '../api/generated/sdk.gen';
import { PERMISSIONS } from '../auth/permissions';
import { requirePermission, usePermission } from './usePermission';

export const useUpdateFeedback = () => {
  const queryClient = useQueryClient();
  const canSubmitQuery = usePermission(PERMISSIONS.QUERY_SUBMIT);
  return useMutation({
    mutationFn: (data: { attemptId: string; feedback: number; saved?: boolean }) => {
      requirePermission(canSubmitQuery, PERMISSIONS.QUERY_SUBMIT);
      return updateFeedback({
        path: { attemptId: data.attemptId },
        body: { feedback: data.feedback, saved: data.saved },
        throwOnError: true,
      }).then((res) => res.data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
    },
  });
};
