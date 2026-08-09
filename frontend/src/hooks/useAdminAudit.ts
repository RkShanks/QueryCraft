import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getAuditStatus, verifyAuditChain } from '../api/generated/sdk.gen';
import { PERMISSIONS } from '../auth/permissions';
import { requirePermission, usePermission } from './usePermission';

export const useAdminAudit = () => {
  const queryClient = useQueryClient();
  const canVerifyAudit = usePermission(PERMISSIONS.ADMIN_AUDIT_VERIFY);

  const statusQuery = useQuery({
    queryKey: ['adminAuditStatus'],
    queryFn: () => getAuditStatus({ throwOnError: true }).then((res) => res.data),
    enabled: canVerifyAudit,
  });

  const verifyMutation = useMutation({
    mutationFn: () => {
      requirePermission(canVerifyAudit, PERMISSIONS.ADMIN_AUDIT_VERIFY);
      return verifyAuditChain({ throwOnError: true }).then((res) => res.data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminAuditStatus'] });
    },
  });

  return {
    statusQuery,
    verifyMutation,
  };
};
