/* eslint-disable react-refresh/only-export-components */
import { QueryClient, QueryClientProvider, QueryCache, MutationCache } from '@tanstack/react-query';
import type { ReactNode } from 'react';

function handle401(error: unknown) {
  const apiError = error as { status?: number; response?: { status?: number } } | undefined;
  if (apiError?.status === 401 || apiError?.response?.status === 401) {
    window.history.replaceState({}, '', '/sign-in?error=session_expired');
    window.dispatchEvent(new PopStateEvent('popstate'));
  }
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: handle401,
  }),
  mutationCache: new MutationCache({
    onError: handle401,
  }),
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,       // 5 minutes
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});

interface QueryProviderProps {
  children: ReactNode;
  client?: QueryClient;
}

export function QueryProvider({ children, client }: QueryProviderProps) {
  return (
    <QueryClientProvider client={client ?? queryClient}>
      {children}
    </QueryClientProvider>
  );
}

export { queryClient };
