/* eslint-disable react-refresh/only-export-components */
import {
  QueryClient,
  QueryClientProvider,
  QueryCache,
  MutationCache,
  useMutation,
  useQuery,
} from '@tanstack/react-query';
import { useLayoutEffect, useState, type ReactNode } from 'react';
import { handleSessionExpiry } from '../auth/sessionExpiry';
import { getMe, signOut } from '../api/generated/sdk.gen';
import {
  AuthSessionContext,
  type CurrentUserResponse,
} from '../auth/AuthSessionContext';
import { useUIStore } from '../stores/uiStore';
import { resetSessionDeletionLifecycle } from '../sessionDeletionLifecycle';

export const CURRENT_USER_QUERY_KEY = ['currentUser'] as const;

function createFeatureQueryClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error) => handleSessionExpiry(error),
    }),
    mutationCache: new MutationCache({
      onError: (error) => handleSessionExpiry(error),
    }),
    defaultOptions: {
      queries: {
        staleTime: 5 * 60 * 1000,
        retry: 1,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: 0,
      },
    },
  });
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: 0 },
  },
});

function identityFingerprint(response: CurrentUserResponse | undefined): string {
  const user = response?.data;
  if (!user) return 'anonymous';
  const permissions = [...(user.permissions ?? [])].sort().join(',');
  return [user.id, user.role_id ?? '', user.role_name ?? '', permissions].join('|');
}

function resetIdentityState(): void {
  useUIStore.getState().resetIdentityState();
  resetSessionDeletionLifecycle();
}

function IdentityQueryBoundary({
  authClient,
  children,
}: {
  authClient: QueryClient;
  children: ReactNode;
}) {
  const currentUserQuery = useQuery({
    queryKey: CURRENT_USER_QUERY_KEY,
    queryFn: async () => {
      const sourcePath = window.location.pathname;
      try {
        return await getMe({ throwOnError: true });
      } catch (error) {
        handleSessionExpiry(error, sourcePath);
        throw error;
      }
    },
    retry: false,
  }, authClient);
  const observedFingerprint = currentUserQuery.isLoading
    ? null
    : identityFingerprint(currentUserQuery.isError ? undefined : currentUserQuery.data);
  const [featureSession, setFeatureSession] = useState(() => ({
    client: createFeatureQueryClient(),
    fingerprint: 'pending',
    generation: 0,
  }));
  const [isAuthTransitionPending, setAuthTransitionPending] = useState(false);
  const needsIdentityReset =
    observedFingerprint !== null && observedFingerprint !== featureSession.fingerprint;

  const signOutMutation = useMutation({
    mutationFn: () => signOut({ throwOnError: true }),
    onMutate: () => {
      setAuthTransitionPending(true);
      void featureSession.client.cancelQueries();
      featureSession.client.clear();
      resetIdentityState();
      setFeatureSession((current) => ({
        client: createFeatureQueryClient(),
        fingerprint: current.fingerprint,
        generation: current.generation + 1,
      }));
    },
    onError: () => {
      setAuthTransitionPending(false);
    },
  }, authClient);

  useLayoutEffect(() => {
    if (!needsIdentityReset || observedFingerprint === null) return;

    void featureSession.client.cancelQueries();
    featureSession.client.clear();
    resetIdentityState();
    setFeatureSession((current) => ({
      client: createFeatureQueryClient(),
      fingerprint: observedFingerprint,
      generation: current.generation + 1,
    }));
  }, [featureSession.client, needsIdentityReset, observedFingerprint]);

  const contextValue = { authClient, currentUserQuery, signOutMutation };
  if (currentUserQuery.isLoading || needsIdentityReset || isAuthTransitionPending) {
    return (
      <AuthSessionContext.Provider value={contextValue}>
        <div className="min-h-screen flex items-center justify-center" role="status">
          <div className="w-8 h-8 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin" />
        </div>
      </AuthSessionContext.Provider>
    );
  }

  return (
    <AuthSessionContext.Provider value={contextValue}>
      <QueryClientProvider client={featureSession.client} key={featureSession.generation}>
        {children}
      </QueryClientProvider>
    </AuthSessionContext.Provider>
  );
}

interface QueryProviderProps {
  children: ReactNode;
  client?: QueryClient;
}

export function QueryProvider({ children, client }: QueryProviderProps) {
  const authClient = client ?? queryClient;
  return (
    <QueryClientProvider client={authClient}>
      <IdentityQueryBoundary authClient={authClient}>{children}</IdentityQueryBoundary>
    </QueryClientProvider>
  );
}

export { queryClient };
