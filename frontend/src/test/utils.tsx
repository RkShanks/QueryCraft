import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactElement } from 'react';
import React from 'react';

import { MemoryRouter } from 'react-router-dom';
import { CURRENT_USER_QUERY_KEY } from '../providers/QueryProvider';
import { PERMISSIONS, type Permission } from '../auth/permissions';

const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

export function seedAuthenticatedUser(
  queryClient: QueryClient,
  permissions: readonly Permission[] = Object.values(PERMISSIONS)
): void {
  queryClient.setQueryData(CURRENT_USER_QUERY_KEY, {
    data: {
      id: 'test-user',
      username: 'admin',
      display_name: 'Admin User',
      role: 'admin',
      permissions: [...permissions],
    },
  });
}

export function renderWithClient(
  ui: ReactElement,
  permissions: readonly Permission[] = Object.values(PERMISSIONS)
) {
  const testQueryClient = createTestQueryClient();
  seedAuthenticatedUser(testQueryClient, permissions);
  const { rerender, ...result } = render(
    <MemoryRouter>
      <QueryClientProvider client={testQueryClient}>{ui}</QueryClientProvider>
    </MemoryRouter>
  );
  return {
    ...result,
    queryClient: testQueryClient,
    rerender: (rerenderUi: ReactElement) =>
      rerender(
        <MemoryRouter>
          <QueryClientProvider client={testQueryClient}>{rerenderUi}</QueryClientProvider>
        </MemoryRouter>
      ),
  };
}

export function createWrapper({ authenticated = true }: { authenticated?: boolean } = {}) {
  const testQueryClient = createTestQueryClient();
  if (authenticated) {
    seedAuthenticatedUser(testQueryClient);
  }
  return ({ children }: { children: React.ReactNode }) => (
    <MemoryRouter>
      <QueryClientProvider client={testQueryClient}>{children}</QueryClientProvider>
    </MemoryRouter>
  );
}
