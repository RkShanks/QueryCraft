import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactElement } from 'react';
import React from 'react';

const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

export function renderWithClient(ui: ReactElement) {
  const testQueryClient = createTestQueryClient();
  const { rerender, ...result } = render(
    <QueryClientProvider client={testQueryClient}>{ui}</QueryClientProvider>
  );
  return {
    ...result,
    rerender: (rerenderUi: ReactElement) =>
      rerender(
        <QueryClientProvider client={testQueryClient}>{rerenderUi}</QueryClientProvider>
      ),
  };
}

export function createWrapper() {
  const testQueryClient = createTestQueryClient();
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={testQueryClient}>{children}</QueryClientProvider>
  );
}
