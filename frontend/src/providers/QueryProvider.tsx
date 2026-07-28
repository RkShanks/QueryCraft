/* eslint-disable react-refresh/only-export-components */
import { QueryClient, QueryClientProvider, QueryCache, MutationCache } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { handleSessionExpiry } from '../auth/sessionExpiry';

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error) => handleSessionExpiry(error),
  }),
  mutationCache: new MutationCache({
    onError: (error) => handleSessionExpiry(error),
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
