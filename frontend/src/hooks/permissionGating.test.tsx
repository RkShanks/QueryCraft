/* eslint-disable local/no-inline-user-strings */
import { QueryClient } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { useState } from 'react';
import { QueryProvider } from '../providers/QueryProvider';
import { server } from '../test/server';
import { useAdminAudit } from './useAdminAudit';
import { useAdminDetection } from './useAdminDetection';
import { useAdminQuotas } from './useAdminQuotas';
import { useAdminRole, useAdminRoles } from './useAdminRoles';
import { useAdminSettings } from './useAdminSettings';
import { useAdminSso } from './useAdminSso';
import { useConnections } from './useConnections';
import { useConnectionSchema } from './useConnectionSchema';
import { useHistory, useHistoryDetail } from './useHistory';
import { useSessionDetail, useSessionsList } from './useSessions';
import { useCreateSession, useDeleteSession } from './useSessions';
import { useAcceptQuery, useSubmitQuestion } from './useQuerySubmit';
import { useUpdateFeedback } from './useFeedback';

function PermissionGatingProbe() {
  const sessions = useSessionsList();
  const session = useSessionDetail('session-id');
  const history = useHistory();
  useHistoryDetail('history-id');
  const settings = useAdminSettings();
  const connections = useConnections();
  const roles = useAdminRoles();
  const role = useAdminRole('role-id');
  const sso = useAdminSso();
  const audit = useAdminAudit();
  const quotas = useAdminQuotas();
  const detection = useAdminDetection();
  const schema = useConnectionSchema('connection-id');

  const isFetching = [
    sessions,
    session,
    settings,
    connections.listQuery,
    roles.listQuery,
    roles.groupMappingsQuery,
    role,
    sso.listQuery,
    audit.statusQuery,
    quotas.listQuery,
    quotas.statusQuery,
    detection.configQuery,
    schema,
  ].some((query) => query.isFetching) || history.isFetching;

  return <span>{isFetching ? 'fetching' : 'settled'}</span>;
}

function MutationGatingProbe() {
  const [isSettled, setSettled] = useState(false);
  const submit = useSubmitQuestion();
  const accept = useAcceptQuery();
  const createSession = useCreateSession();
  const deleteSession = useDeleteSession();
  const feedback = useUpdateFeedback();

  const triggerRequests = async () => {
    await Promise.allSettled([
      submit.mutateAsync({ question: 'probe', connection_id: 'connection-id' }),
      accept.mutateAsync({ attempt_id: 'attempt-id' }),
      createSession.mutateAsync(),
      deleteSession.mutateAsync('session-id'),
      feedback.mutateAsync({ attemptId: 'attempt-id', feedback: 1 }),
    ]);
    setSettled(true);
  };

  return (
    <button onClick={() => void triggerRequests()}>
      {isSettled ? 'Mutations settled' : 'Trigger mutations'}
    </button>
  );
}

describe('permission-gated feature hooks', () => {
  it('makes zero feature requests when the authenticated user has no permissions', async () => {
    let featureRequestCount = 0;
    server.use(
      http.all('/api/v1/*', ({ request }) => {
        const path = new URL(request.url).pathname;
        if (path === '/api/v1/auth/me') {
          return HttpResponse.json({
            id: 'restricted-user',
            username: 'restricted',
            display_name: 'Restricted',
            role: 'admin',
            role_name: 'admin',
            permissions: [],
          });
        }
        featureRequestCount += 1;
        if (path === '/api/v1/admin/connections') {
          return HttpResponse.json({ connections: [] });
        }
        if (path === '/api/v1/admin/roles') {
          return HttpResponse.json({ roles: [] });
        }
        if (path === '/api/v1/admin/sso/group-mappings') {
          return HttpResponse.json({ mappings: [] });
        }
        return HttpResponse.json({});
      })
    );

    render(
      <QueryProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <PermissionGatingProbe />
      </QueryProvider>
    );

    expect(await screen.findByText('settled')).toBeInTheDocument();
    expect(featureRequestCount).toBe(0);
  });

  it('rejects imperative feature mutations before they reach the network', async () => {
    let featureRequestCount = 0;
    server.use(
      http.all('/api/v1/*', ({ request }) => {
        const path = new URL(request.url).pathname;
        if (path === '/api/v1/auth/me') {
          return HttpResponse.json({
            id: 'restricted-user',
            username: 'restricted',
            display_name: 'Restricted',
            role: 'admin',
            role_name: 'admin',
            permissions: [],
          });
        }
        featureRequestCount += 1;
        return HttpResponse.json({});
      })
    );

    render(
      <QueryProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <MutationGatingProbe />
      </QueryProvider>
    );

    fireEvent.click(await screen.findByRole('button', { name: 'Trigger mutations' }));
    await screen.findByRole('button', { name: 'Mutations settled' });
    expect(featureRequestCount).toBe(0);
  });
});
