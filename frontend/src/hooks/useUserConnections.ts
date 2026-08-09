import { useQuery } from '@tanstack/react-query';
import { listUserConnections } from '../api/generated/sdk.gen';
import { PERMISSIONS } from '../auth/permissions';
import { usePermission } from './usePermission';

export function useUserConnections() {
  const canSubmitQuery = usePermission(PERMISSIONS.QUERY_SUBMIT);
  return useQuery({
    queryKey: ['userConnections'],
    queryFn: () => listUserConnections({ throwOnError: true }).then((res) => res.data),
    enabled: canSubmitQuery,
  });
}
