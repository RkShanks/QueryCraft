import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getAuditStatus, verifyAuditChain } from '../api/generated/sdk.gen';

export const useAdminAudit = () => {
  const queryClient = useQueryClient();

  const statusQuery = useQuery({
    queryKey: ['adminAuditStatus'],
    queryFn: () => getAuditStatus({ throwOnError: true }).then((res) => res.data),
  });

  const verifyMutation = useMutation({
    mutationFn: () => verifyAuditChain({ throwOnError: true }).then((res) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminAuditStatus'] });
    },
  });

  return {
    statusQuery,
    verifyMutation,
  };
};
