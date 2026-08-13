import { describe, expect, expectTypeOf, it } from 'vitest';
import { client } from './generated/client.gen';
import * as sdk from './generated/sdk.gen';
import type {
  AuditExportRequest,
  DraftPolicyTestRequest,
  QueryLimitsResponse,
  QuotaStatusResponse,
} from './generated/types.gen';

describe('representative generated client compatibility', () => {
  it.each([
    'signIn',
    'getMe',
    'getQueryLimits',
    'submitQuestion',
    'listAdminConnections',
    'getQuotaStatus',
    'searchAuditEntries',
    'exportAuditEntries',
    'oidcLogin',
    'samlCallback',
    'testDraftRolePolicy',
  ] as const)('exports %s', (operationName) => {
    expect(sdk[operationName]).toBeTypeOf('function');
  });

  it('exposes the canonical quota, query-limit, and download types', () => {
    expectTypeOf<QueryLimitsResponse>().toMatchTypeOf<{ max_question_length: number }>();
    expectTypeOf<QuotaStatusResponse>().toHaveProperty('next_cursor');
    expectTypeOf<AuditExportRequest>().toHaveProperty('format');
    expectTypeOf<DraftPolicyTestRequest>().toHaveProperty('connection_policy');
  });

  it('keeps cookie credentials enabled for generated API calls', () => {
    expect(client.getConfig().credentials).toBe('include');
  });
});
