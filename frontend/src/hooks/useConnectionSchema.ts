import { useQuery } from '@tanstack/react-query';
import { getAdminConnectionSchema } from '../api/generated/sdk.gen';
import type {
  ConnectionSchemaColumn,
  ConnectionSchemaResponse,
  ConnectionSchemaTable,
} from '../api/generated/types.gen';
import { withRequestDeadline } from '../api/requestScope';
import { PERMISSIONS } from '../auth/permissions';
import { useAnyPermission } from './usePermission';

export type ColumnSchema = ConnectionSchemaColumn;
export type TableSchema = ConnectionSchemaTable;
export type ConnectionSchema = ConnectionSchemaResponse;

export const useConnectionSchema = (connectionId: string | null) => {
  const canViewSchema = useAnyPermission([
    PERMISSIONS.ADMIN_CONNECTIONS_MANAGE,
    PERMISSIONS.ADMIN_ROLES_MANAGE,
  ]);
  return useQuery<ConnectionSchema>({
    queryKey: ['connectionSchema', connectionId],
    queryFn: ({ signal }) => {
      if (!connectionId) throw new Error('Connection ID is required');
      return withRequestDeadline(
        (requestSignal) =>
          getAdminConnectionSchema({
            path: { connection_id: connectionId },
            throwOnError: true,
            signal: requestSignal,
          }).then((response) => response.data),
        { signal },
      );
    },
    enabled: !!connectionId && canViewSchema,
  });
};
