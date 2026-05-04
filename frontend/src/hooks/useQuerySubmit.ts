import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { submitQuestion, acceptQuery, listHistory } from '../api/generated/sdk.gen';
import type { SubmitQuestionData, AcceptQueryData } from '../api/generated/types.gen';

export const useSubmitQuestion = () => {
  return useMutation({
    mutationFn: (data: SubmitQuestionData['body']) => submitQuestion({ body: data, throwOnError: true }).then(res => res.data),
  });
};

export const useAcceptQuery = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: AcceptQueryData['body']) => acceptQuery({ body: data, throwOnError: true }).then(res => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['history'] });
    },
  });
};

export const useHistory = () => {
  return useQuery({
    queryKey: ['history'],
    queryFn: () => listHistory({ throwOnError: true }).then(res => res.data),
  });
};
