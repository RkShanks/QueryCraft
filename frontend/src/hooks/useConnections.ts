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
  ConnectionUpdate,
} from '../api/generated/types.gen';

export const useConnections = () => {
  const queryClient = useQueryClient();

  const listQuery = useQuery({
    queryKey: ['adminConnections'],
    queryFn: () => listAdminConnections({ throwOnError: true }).then((res) => res.data),
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
    mutationFn: () => refreshSchema({ throwOnError: true }).then((res) => res.data),
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
