/* eslint-disable react-refresh/only-export-components */
import {
  QueryClient,
  QueryClientProvider,
  QueryCache,
  MutationCache,
  useMutation,
  useQuery,
} from '@tanstack/react-query';
import { useCallback, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { handleSessionExpiry, isSessionExpiryError } from '../auth/sessionExpiry';
import {
  notifySessionExpiry,
  subscribeToSessionExpiry,
} from '../auth/authorizationEvents';
import { getMe, signIn, signOut } from '../api/generated/sdk.gen';
import type { SignInData } from '../api/generated/types.gen';
import {
  AuthSessionContext,
  type CurrentUserResponse,
} from '../auth/AuthSessionContext';
import { useUIStore } from '../stores/uiStore';
import { resetSessionDeletionLifecycle } from '../sessionDeletionLifecycle';

export const CURRENT_USER_QUERY_KEY = ['currentUser'] as const;

function createFeatureQueryClient(): QueryClient {
  const handleFeatureError = (error: unknown) => {
    handleSessionExpiry(error);
    if (isSessionExpiryError(error)) {
      notifySessionExpiry();
    }
  };
  return new QueryClient({
    queryCache: new QueryCache({
      onError: handleFeatureError,
    }),
    mutationCache: new MutationCache({
      onError: handleFeatureError,
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
  const [isExplicitlySignedOut, setExplicitlySignedOut] = useState(false);
  const sessionExpiredRef = useRef(false);
  const createIdentityClient = useCallback(() => createFeatureQueryClient(), []);
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
    enabled: !isExplicitlySignedOut,
  }, authClient);
  const exposedCurrentUserQuery = isExplicitlySignedOut
    ? { ...currentUserQuery, data: undefined, isLoading: false, isError: false }
    : currentUserQuery;
  const observedFingerprint = exposedCurrentUserQuery.isLoading
    ? null
    : identityFingerprint(
        exposedCurrentUserQuery.isError ? undefined : exposedCurrentUserQuery.data
      );
  const [featureSession, setFeatureSession] = useState(() => ({
    client: createIdentityClient(),
    fingerprint: 'pending',
    generation: 0,
  }));
  const [isAuthTransitionPending, setAuthTransitionPending] = useState(false);
  const needsIdentityReset =
    observedFingerprint !== null && observedFingerprint !== featureSession.fingerprint;

  useLayoutEffect(() => {
    return subscribeToSessionExpiry(() => {
      if (sessionExpiredRef.current) return;
      sessionExpiredRef.current = true;
      setExplicitlySignedOut(true);
      authClient.removeQueries({ queryKey: CURRENT_USER_QUERY_KEY });
      void featureSession.client.cancelQueries();
      featureSession.client.clear();
      resetIdentityState();
      setFeatureSession((current) => ({
        client: createIdentityClient(),
        fingerprint: 'anonymous',
        generation: current.generation + 1,
      }));
    });
  }, [authClient, createIdentityClient, featureSession.client]);

  const beginAuthTransition = useCallback(() => {
    setAuthTransitionPending(true);
    void featureSession.client.cancelQueries();
    featureSession.client.clear();
    resetIdentityState();
    setFeatureSession((current) => ({
      client: createIdentityClient(),
      fingerprint: current.fingerprint,
      generation: current.generation + 1,
    }));
  }, [createIdentityClient, featureSession.client]);

  const signInMutation = useMutation({
    mutationFn: (data: SignInData['body']) =>
      signIn({ body: data, throwOnError: true }),
    onMutate: beginAuthTransition,
    onError: () => {
      setAuthTransitionPending(false);
    },
    onSuccess: (response) => {
      sessionExpiredRef.current = false;
      authClient.setQueryData(CURRENT_USER_QUERY_KEY, response);
      setExplicitlySignedOut(false);
      setAuthTransitionPending(false);
    },
  }, authClient);

  const signOutMutation = useMutation({
    mutationFn: () => signOut({ throwOnError: true }),
    onMutate: beginAuthTransition,
    onError: () => {
      setAuthTransitionPending(false);
    },
    onSuccess: () => {
      sessionExpiredRef.current = true;
      setExplicitlySignedOut(true);
      authClient.removeQueries({ queryKey: CURRENT_USER_QUERY_KEY });
      setAuthTransitionPending(false);
    },
  }, authClient);

  useLayoutEffect(() => {
    if (!needsIdentityReset || observedFingerprint === null) return;

    void featureSession.client.cancelQueries();
    featureSession.client.clear();
    resetIdentityState();
    // The permission fingerprint is an async external snapshot. Withhold children
    // above, then rotate the client in this guarded synchronization effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFeatureSession((current) => ({
      client: createIdentityClient(),
      fingerprint: observedFingerprint,
      generation: current.generation + 1,
    }));
  }, [createIdentityClient, featureSession.client, needsIdentityReset, observedFingerprint]);

  const contextValue = {
    authClient,
    currentUserQuery: exposedCurrentUserQuery,
    signInMutation,
    signOutMutation,
  };
  if (exposedCurrentUserQuery.isLoading || needsIdentityReset || isAuthTransitionPending) {
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
