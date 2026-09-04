import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { WorkspacePage } from './WorkspacePage';
import { seedAuthenticatedUser } from '../test/utils';
import { server } from '../test/server';
import { useUIStore } from '../stores/uiStore';

const AUTHORIZED_CONNECTION_ID = '550e8400-e29b-41d4-a716-446655440004';

function SettledLocation() {
  const { pathname, search, hash } = useLocation();
  return <output data-testid="settled-location">{pathname}{search}{hash}</output>;
}

function renderWorkspaceAt(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  seedAuthenticatedUser(queryClient);

  return render(
    <MemoryRouter initialEntries={[path]}>
      <QueryClientProvider client={queryClient}>
        <WorkspacePage />
        <SettledLocation />
      </QueryClientProvider>
    </MemoryRouter>
  );
}

describe('Workspace legacy bookmark prefill', () => {
  beforeEach(() => {
    useUIStore.setState({
      activeSessionId: null,
      sidebarCollapsed: false,
      hoveredSessionId: null,
      promptDraft: '',
    });
  });

  it('consumes authorized question and connection inputs without auto-submitting', async () => {
    let submitRequestCount = 0;
    server.use(
      http.post('/api/v1/query/submit', () => {
        submitRequestCount += 1;
        return HttpResponse.json({});
      })
    );

    renderWorkspaceAt(
      `/?question=monthly%20revenue&connectionId=${AUTHORIZED_CONNECTION_ID}&lng=ar`
    );

    await waitFor(() => {
      expect(screen.getByLabelText('Ask a question')).toHaveValue('monthly revenue');
      expect(screen.getByText('PostgreSQL DB')).toBeInTheDocument();
      expect(screen.getByTestId('settled-location')).toHaveTextContent('/?lng=ar');
    });
    expect(submitRequestCount).toBe(0);
  });

  it('discards an unavailable connection without retaining URL residue', async () => {
    let submitRequestCount = 0;
    server.use(
      http.post('/api/v1/query/submit', () => {
        submitRequestCount += 1;
        return HttpResponse.json({});
      })
    );

    renderWorkspaceAt(
      '/?question=authorized%20prefill&connectionId=unavailable-connection&lng=en'
    );

    await waitFor(() => {
      expect(screen.getByLabelText('Ask a question')).toHaveValue('authorized prefill');
      expect(screen.getByText('PostgreSQL DB')).toBeInTheDocument();
      expect(screen.getByTestId('settled-location')).toHaveTextContent('/?lng=en');
    });
    expect(screen.queryByText('unavailable-connection')).not.toBeInTheDocument();
    expect(submitRequestCount).toBe(0);
  });

  it('preserves the question and discards the connection when authorization lookup fails', async () => {
    let submitRequestCount = 0;
    server.use(
      http.get('/api/v1/connections', () =>
        HttpResponse.json({ error: 'unavailable' }, { status: 503 })
      ),
      http.post('/api/v1/query/submit', () => {
        submitRequestCount += 1;
        return HttpResponse.json({});
      })
    );

    renderWorkspaceAt(
      '/?question=retained%20prefill&connectionId=unverified-connection&lng=en'
    );

    await waitFor(() => {
      expect(screen.getByLabelText('Ask a question')).toHaveValue('retained prefill');
      expect(screen.getByTestId('settled-location')).toHaveTextContent('/?lng=en');
    });
    expect(screen.queryByText('unverified-connection')).not.toBeInTheDocument();
    expect(submitRequestCount).toBe(0);
  });
});
