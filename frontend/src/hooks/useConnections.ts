import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listAdminConnections,
  createAdminConnection,
  updateAdminConnection,
  deleteAdminConnection,
  testAdminConnection,
  disableAdminConnection,
  enableAdminConnection,
  refreshSchema,
} from '../api/generated/sdk.gen';
import type {
  ConnectionCreate,
  ConnectionListResponse,
  ConnectionResponse,
  ConnectionUpdate,
} from '../api/generated/types.gen';
import { PERMISSIONS } from '../auth/permissions';
import { requirePermission, usePermission } from './usePermission';

export type ConnectionView = Pick<
  ConnectionResponse,
  | 'id'
  | 'display_name'
  | 'database_type'
  | 'port'
  | 'database_name'
  | 'ssl_mode'
  | 'lifecycle_state'
  | 'health_status'
  | 'last_health_check_at'
  | 'health_error_category'
  | 'schema_introspection_status'
  | 'schema_last_refreshed_at'
  | 'created_at'
  | 'updated_at'
>;

const normalizeConnection = (connection: ConnectionResponse): ConnectionView => ({
  id: connection.id,
  display_name: connection.display_name,
  database_type: connection.database_type,
  port: connection.port,
  database_name: connection.database_name,
  ssl_mode: connection.ssl_mode,
  lifecycle_state: connection.lifecycle_state,
  health_status: connection.health_status,
  last_health_check_at: connection.last_health_check_at,
  health_error_category: connection.health_error_category,
  schema_introspection_status: connection.schema_introspection_status,
  schema_last_refreshed_at: connection.schema_last_refreshed_at,
  created_at: connection.created_at,
  updated_at: connection.updated_at,
});

const normalizeConnectionList = (
  connectionList: ConnectionListResponse | ConnectionResponse[]
) => ({
  connections: (Array.isArray(connectionList) ? connectionList : connectionList.connections).map(
    normalizeConnection
  ),
});

export const useConnections = () => {
  const queryClient = useQueryClient();
  const canManageConnections = usePermission(PERMISSIONS.ADMIN_CONNECTIONS_MANAGE);

  const listQuery = useQuery({
    queryKey: ['adminConnections'],
    queryFn: () =>
      listAdminConnections({ throwOnError: true, cache: 'no-store' }).then((response) =>
        normalizeConnectionList(response.data)
      ),
    enabled: canManageConnections,
  });

  const createMutation = useMutation({
    mutationFn: (data: ConnectionCreate) => {
      requirePermission(canManageConnections, PERMISSIONS.ADMIN_CONNECTIONS_MANAGE);
      return createAdminConnection({ body: data, throwOnError: true, cache: 'no-store' }).then(
        (response) => normalizeConnection(response.data)
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminConnections'] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: ConnectionUpdate }) => {
      requirePermission(canManageConnections, PERMISSIONS.ADMIN_CONNECTIONS_MANAGE);
      return updateAdminConnection({
        path: { connectionId: id },
        body: data,
        throwOnError: true,
        cache: 'no-store',
      }).then(
        (response) => normalizeConnection(response.data)
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminConnections'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => {
      requirePermission(canManageConnections, PERMISSIONS.ADMIN_CONNECTIONS_MANAGE);
      return deleteAdminConnection({ path: { connectionId: id }, throwOnError: true });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminConnections'] });
    },
  });

  const testMutation = useMutation({
    mutationFn: (id: string) => {
      requirePermission(canManageConnections, PERMISSIONS.ADMIN_CONNECTIONS_MANAGE);
      return testAdminConnection({ path: { connectionId: id }, throwOnError: true }).then(
        (res) => res.data
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminConnections'] });
    },
  });

  const disableMutation = useMutation({
    mutationFn: (id: string) => {
      requirePermission(canManageConnections, PERMISSIONS.ADMIN_CONNECTIONS_MANAGE);
      return disableAdminConnection({
        path: { connectionId: id },
        throwOnError: true,
        cache: 'no-store',
      }).then(
        (response) => normalizeConnection(response.data)
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminConnections'] });
    },
  });

  const enableMutation = useMutation({
    mutationFn: (id: string) => {
      requirePermission(canManageConnections, PERMISSIONS.ADMIN_CONNECTIONS_MANAGE);
      return enableAdminConnection({
        path: { connectionId: id },
        throwOnError: true,
        cache: 'no-store',
      }).then(
        (response) => normalizeConnection(response.data)
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminConnections'] });
    },
  });

  const refreshSchemaMutation = useMutation({
    mutationFn: (id: string) => {
      requirePermission(canManageConnections, PERMISSIONS.ADMIN_CONNECTIONS_MANAGE);
      return refreshSchema({ path: { connectionId: id }, throwOnError: true }).then(
        (res) => res.data
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminConnections'] });
    },
  });

  return {
    listQuery,
    createMutation,
    updateMutation,
    deleteMutation,
    testMutation,
    disableMutation,
    enableMutation,
    refreshSchemaMutation,
  };
};
