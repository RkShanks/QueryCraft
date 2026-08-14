import { useQuery } from '@tanstack/react-query';
import { getQueryLimits } from '../api/queryLimits';
import { PERMISSIONS } from '../auth/permissions';
import { usePermission } from './usePermission';

export const QUERY_LIMITS_QUERY_KEY = ['queryLimits'] as const;

export function useQueryLimits() {
  const canSubmitQuery = usePermission(PERMISSIONS.QUERY_SUBMIT);
  return useQuery({
    queryKey: QUERY_LIMITS_QUERY_KEY,
    queryFn: ({ signal }) => getQueryLimits(signal),
    enabled: canSubmitQuery,
  });
}
