import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createSession,
  getSession,
  listSessions,
  deleteSession,
} from '../api/generated/sdk.gen';



export const useSessionsList = () => {
  return useQuery({
    queryKey: ['sessions'],
    queryFn: () => listSessions({ throwOnError: true }).then((res) => res.data),
  });
};


export const useSessionDetail = (sessionId: string) => {
  return useQuery({
    queryKey: ['sessions', sessionId],
    queryFn: () =>
      getSession({ path: { sessionId }, throwOnError: true }).then((res) => res.data),
    enabled: !!sessionId,
  });
};

export const useCreateSession = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      createSession({ throwOnError: true }).then((res) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
    },
  });
};

export const useDeleteSession = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: string) =>
      deleteSession({ path: { sessionId }, throwOnError: true }).then((res) => res.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
    },
    onError: () => {
      // If DELETE fails (e.g. 500), refetch sessions to restore optimistic UI state.
      // The session was hidden from the sidebar by the undo soft-delete mechanism;
      // invalidating ensures the session reappears.
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
    },
  });
};
