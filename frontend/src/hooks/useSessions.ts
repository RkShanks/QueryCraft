import {
  type InfiniteData,
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import {
  createSession,
  getSession,
  getSessions,
  deleteSession,
} from '../api/generated/sdk.gen';
import type {
  SessionDetail,
  SessionListResponse,
} from '../api/generated/types.gen';
import {
  beginSessionDeletion,
  didSessionDeletionStart,
  getSessionDeletionVersion,
  isSessionUnavailable,
  rollbackSessionDeletion,
  SessionDeletionError,
} from '../sessionDeletionLifecycle';
import { PERMISSIONS } from '../auth/permissions';
import { requirePermission, usePermission } from './usePermission';

type SessionListPages = InfiniteData<SessionListResponse, string | undefined>;

function uniqueById<T extends { id: string }>(groups: T[][]): T[] {
  const seenIds = new Set<string>();
  const uniqueItems: T[] = [];
  for (const group of groups) {
    for (const item of group) {
      if (seenIds.has(item.id)) continue;
      seenIds.add(item.id);
      uniqueItems.push(item);
    }
  }
  return uniqueItems;
}

function flattenedSessionList(
  pages: InfiniteData<SessionListResponse, string | undefined> | undefined
): SessionListResponse | undefined {
  if (!pages?.pages.length) return undefined;
  return {
    items: uniqueById(pages.pages.map((page) => page.items)),
    total: pages.pages[0].total,
    next_cursor: pages.pages.at(-1)?.next_cursor ?? null,
  };
}

export const useSessionsList = ({ enabled = true }: { enabled?: boolean } = {}) => {
  const canSubmitQuery = usePermission(PERMISSIONS.QUERY_SUBMIT);
  const query = useInfiniteQuery({
    queryKey: ['sessions'],
    queryFn: ({ pageParam, signal }) =>
      getSessions({
        query: { cursor: pageParam, limit: 50 },
        signal,
        throwOnError: true,
      }).then((response) => response.data),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    enabled: enabled && canSubmitQuery,
  });
  return { ...query, data: flattenedSessionList(query.data) };
};

function flattenedSessionDetail(
  pages: InfiniteData<SessionDetail, string | undefined> | undefined
): SessionDetail | undefined {
  if (!pages?.pages.length) return undefined;
  const firstPage = pages.pages[0];
  return {
    ...firstPage,
    attempts: uniqueById(pages.pages.map((page) => page.attempts)),
    attempts_total: firstPage.attempts_total,
    attempts_next_cursor: pages.pages.at(-1)?.attempts_next_cursor ?? null,
  };
}

export const useSessionDetail = (sessionId: string) => {
  const canSubmitQuery = usePermission(PERMISSIONS.QUERY_SUBMIT);
  const query = useInfiniteQuery({
    queryKey: ['sessions', sessionId],
    queryFn: async ({ pageParam, signal }) => {
      const deletionVersion = getSessionDeletionVersion(sessionId);
      if (isSessionUnavailable(sessionId)) throw new SessionDeletionError();
      const response = await getSession({
        path: { sessionId },
        query: { attempt_cursor: pageParam, attempt_limit: 50 },
        signal,
        throwOnError: true,
      });
      if (didSessionDeletionStart(sessionId, deletionVersion)) {
        throw new SessionDeletionError();
      }
      return response.data;
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.attempts_next_cursor ?? undefined,
    enabled: !!sessionId && canSubmitQuery && !isSessionUnavailable(sessionId),
  });
  return { ...query, data: flattenedSessionDetail(query.data) };
};

export const useCreateSession = () => {
  const queryClient = useQueryClient();
  const canSubmitQuery = usePermission(PERMISSIONS.QUERY_SUBMIT);
  return useMutation({
    mutationFn: () => {
      requirePermission(canSubmitQuery, PERMISSIONS.QUERY_SUBMIT);
      return createSession({ throwOnError: true }).then((res) => res.data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
    },
  });
};

export const useDeleteSession = () => {
  const queryClient = useQueryClient();
  const canSubmitQuery = usePermission(PERMISSIONS.QUERY_SUBMIT);
  return useMutation({
    mutationFn: (sessionId: string) => {
      requirePermission(canSubmitQuery, PERMISSIONS.QUERY_SUBMIT);
      return deleteSession({ path: { sessionId }, throwOnError: true }).then(
        (res) => res.data
      );
    },
    onMutate: async (sessionId: string) => {
      requirePermission(canSubmitQuery, PERMISSIONS.QUERY_SUBMIT);
      beginSessionDeletion(sessionId);
      await queryClient.cancelQueries({ queryKey: ['sessions', sessionId], exact: true });
      const previousDetail = queryClient.getQueryData(['sessions', sessionId]);
      queryClient.removeQueries({ queryKey: ['sessions', sessionId], exact: true });
      return { previousDetail };
    },
    onSuccess: (_data, sessionId) => {
      queryClient.setQueryData<SessionListPages>(['sessions'], (current) => {
        if (!current) return current;
        const containsSession = current.pages.some((page) =>
          page.items.some((session) => session.id === sessionId)
        );
        if (!containsSession) return current;
        return {
          ...current,
          pages: current.pages.map((page) => ({
            ...page,
            items: page.items.filter((session) => session.id !== sessionId),
            total: Math.max(0, page.total - 1),
          })),
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
