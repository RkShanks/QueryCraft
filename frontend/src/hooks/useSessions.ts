import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createSession,
  getSession,
  getSessions,
  deleteSession,
} from '../api/generated/sdk.gen';
import {
  beginSessionDeletion,
  rollbackSessionDeletion,
} from '../sessionDeletionLifecycle';

interface SessionListCache {
  items: Array<{ id: string }>;
  total: number;
}


export const useSessionsList = () => {
  return useQuery({
    queryKey: ['sessions'],
    queryFn: () => getSessions({ throwOnError: true }).then((res) => res.data),
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
    onMutate: async (sessionId: string) => {
      beginSessionDeletion(sessionId);
      await queryClient.cancelQueries({ queryKey: ['sessions', sessionId], exact: true });
      const previousDetail = queryClient.getQueryData(['sessions', sessionId]);
      queryClient.removeQueries({ queryKey: ['sessions', sessionId], exact: true });
      return { previousDetail };
    },
    onSuccess: (_data, sessionId) => {
      queryClient.setQueryData<SessionListCache>(['sessions'], (current) => {
        if (!current) return current;
        const items = current.items.filter((session) => session.id !== sessionId);
        return {
          ...current,
          items,
          total: Math.max(0, current.total - (current.items.length - items.length)),
        };
      });
      queryClient.removeQueries({ queryKey: ['sessions', sessionId], exact: true });
      queryClient.invalidateQueries({ queryKey: ['sessions'], exact: true });
      queryClient.invalidateQueries({ queryKey: ['history'] });
    },
    onError: (_error, sessionId, context) => {
      rollbackSessionDeletion(sessionId);
      if (context?.previousDetail !== undefined) {
        queryClient.setQueryData(['sessions', sessionId], context.previousDetail);
      }
      queryClient.invalidateQueries({ queryKey: ['sessions'], exact: true });
      queryClient.invalidateQueries({ queryKey: ['sessions', sessionId], exact: true });
      queryClient.invalidateQueries({ queryKey: ['history'] });
    },
  });
};
