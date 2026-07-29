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
  ConnectionResponse,
  ConnectionUpdate,
} from '../api/generated/types.gen';

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

export const useConnections = () => {
  const queryClient = useQueryClient();

  const listQuery = useQuery({
    queryKey: ['adminConnections'],
    queryFn: () =>
      listAdminConnections({ throwOnError: true, cache: 'no-store' }).then((response) => ({
        connections: response.data.connections.map(normalizeConnection),
      })),
  });

  const createMutation = useMutation({
    mutationFn: (data: ConnectionCreate) =>
      createAdminConnection({ body: data, throwOnError: true }).then((res) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminConnections'] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: ConnectionUpdate }) =>
      updateAdminConnection({ path: { connectionId: id }, body: data, throwOnError: true }).then(
        (res) => res.data
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminConnections'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      deleteAdminConnection({ path: { connectionId: id }, throwOnError: true }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminConnections'] });
    },
  });

  const testMutation = useMutation({
    mutationFn: (id: string) =>
      testAdminConnection({ path: { connectionId: id }, throwOnError: true }).then(
        (res) => res.data
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminConnections'] });
    },
  });

  const disableMutation = useMutation({
    mutationFn: (id: string) =>
      disableAdminConnection({ path: { connectionId: id }, throwOnError: true }).then(
        (res) => res.data
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminConnections'] });
    },
  });

  const enableMutation = useMutation({
    mutationFn: (id: string) =>
      enableAdminConnection({ path: { connectionId: id }, throwOnError: true }).then(
        (res) => res.data
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['adminConnections'] });
    },
  });

  const refreshSchemaMutation = useMutation({
    mutationFn: (id: string) =>
      refreshSchema({ path: { connectionId: id }, throwOnError: true }).then(
        (res) => res.data
      ),
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
