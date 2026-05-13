import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateFeedback } from '../api/generated/sdk.gen';

export const useUpdateFeedback = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { attemptId: string; feedback: number; saved?: boolean }) =>
      updateFeedback({
        path: { attemptId: data.attemptId },
        body: { feedback: data.feedback, saved: data.saved },
        throwOnError: true,
      }).then((res) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
    },
  });
};
