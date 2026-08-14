import { describe, expect, it } from 'vitest';
import type {
  HistoryListResponse,
  QueryResult,
  SessionDetail,
  UserConnectionListResponse,
} from './generated/types.gen';
import { responseOperationManifest } from './generated/responseManifest.gen';
import {
  CLIENT_CONTRACT_ERROR_CODE,
  ClientContractError,
  validateOperationResponse,
} from './responseValidation';

const validUserConnections = {
  connections: [
    {
      id: '550e8400-e29b-41d4-a716-446655440001',
      display_name: 'Analytics',
      database_type: 'postgresql',
    },
  ],
} satisfies UserConnectionListResponse;

const validSessionDetail = {
  id: 'session-1',
  connection_id: null,
  preview_text: 'Quarterly revenue',
  created_at: '2026-08-14T01:00:00Z',
  last_activity_at: '2026-08-14T02:00:00Z',
  attempts: [],
  attempts_total: 0,
  attempts_next_cursor: null,
} satisfies SessionDetail;

const validHistory = {
  items: [
    {
      id: 'history-1',
      question_text: 'Quarterly revenue',
      generated_sql: 'SELECT 1',
      accepted_at: '2026-08-14T02:00:00Z',
      database_connection_id: null,
      database_connection_name: null,
      database_type: null,
    },
  ],
  total: 1,
  next_cursor: null,
} satisfies HistoryListResponse;

const validQueryResult = {
  kind: 'result',
  attempt_id: 'attempt-1',
  question: 'Quarterly revenue',
  generated_sql: 'SELECT 1',
  columns: [{ name: 'revenue', type: 'integer', masked: false }],
  rows: [[1]],
  row_count: 1,
  attempt_number: 1,
  is_last_auto_retry: false,
  accepted_query_id: null,
  session_id: 'session-1',
} satisfies QueryResult;

describe('generated response contract manifest', () => {
  it('classifies every canonical operation exactly once', () => {
    expect(responseOperationManifest).toHaveLength(64);
    expect(
      Object.fromEntries(
        ['consumed_json', 'no_body', 'browser_redirect', 'blob_download', 'unused'].map(
          (classification) => [
            classification,
            responseOperationManifest.filter(
              (operation) => operation.classification === classification
            ).length,
          ]
        )
      )
    ).toEqual({
      consumed_json: 41,
      no_body: 8,
      browser_redirect: 4,
      blob_download: 1,
      unused: 10,
    });
    expect(new Set(responseOperationManifest.map((operation) => operation.operationId)).size).toBe(
      64
    );
  });
});

describe('canonical JSON response validation', () => {
  it.each([
    ['authentication', 'getMe', {}],
    ['user connections enum', 'listUserConnections', {
      connections: [{ ...validUserConnections.connections[0], database_type: 'oracle' }],
    }],
    ['admin connections nested array', 'listAdminConnections', [{ id: 'connection-1' }]],
    ['SSO provider list', 'listAdminSsoProviders', { providers: [{}] }],
    ['roles and mappings', 'listRoles', { roles: [{ id: 'role-1' }] }],
    ['role policy schema', 'getAdminConnectionSchema', { connection_id: 'connection-1', tables: [{}] }],
    ['audit pagination', 'searchAuditEntries', { entries: [], pagination: { page: 1 } }],
    ['quota dimensions', 'getQuotaStatus', {
      status: [{ role_id: 'not-a-uuid', role_name: 'Analyst', dimensions: [], reset_at: 'invalid' }],
      total: 1,
      next_cursor: null,
    }],
    ['detection thresholds', 'getDetectionConfig', {
      block_confidence: '0.8',
      flag_confidence: 0.5,
      updated_at: '2026-08-14T02:00:00Z',
    }],
    ['settings counters', 'getAdminSettings', { llm_context_cap: '20', max_regenerate_attempts: 2 }],
    ['query limits', 'getQueryLimits', { max_question_length: 0 }],
  ])('rejects a malformed %s response without retaining it', (_family, operationId, payload) => {
    let caught: unknown;
    try {
      validateOperationResponse(operationId, 200, payload);
    } catch (error) {
      caught = error;
    }

    expect(caught).toBeInstanceOf(ClientContractError);
    expect(caught).toMatchObject({ code: CLIENT_CONTRACT_ERROR_CODE });
    expect(JSON.stringify(caught)).not.toContain(JSON.stringify(payload));
  });

  it.each([
    ['invalid session timestamp', 'getSession', {
      ...validSessionDetail,
      created_at: 'not-a-timestamp',
    }],
    ['invalid history timestamp', 'listHistory', {
      ...validHistory,
      items: [{ ...validHistory.items[0], accepted_at: 'not-a-timestamp' }],
    }],
    ['empty cursor', 'listHistory', { ...validHistory, next_cursor: '' }],
    ['negative counter', 'getQuotaStatus', { status: [], total: -1, next_cursor: null }],
    ['invalid query union', 'submitQuestion', { ...validQueryResult, kind: 'refine' }],
    ['query column dimensions', 'submitQuestion', {
      ...validQueryResult,
      rows: [[1, 2]],
    }],
  ])('rejects the semantic refinement for %s', (_caseName, operationId, payload) => {
    expect(() => validateOperationResponse(operationId, 200, payload)).toThrowError(
      ClientContractError
    );
  });

  it('strips unknown fields before returning a valid response', () => {
    const validated = validateOperationResponse('listUserConnections', 200, {
      ...validUserConnections,
      response_canary: 'must-not-enter-state',
      connections: [
        {
          ...validUserConnections.connections[0],
          nested_canary: 'must-not-enter-state',
        },
      ],
    });

    expect(validated).toEqual(validUserConnections);
    expect(JSON.stringify(validated)).not.toContain('canary');
  });

  it('preserves the valid refine branch of the generated query response union', () => {
    expect(
      validateOperationResponse('regenerateQuery', 200, {
        kind: 'refine',
        message_key: 'query.refine',
        message_params: null,
        should_refine: true,
        response_canary: 'must-not-enter-state',
      })
    ).toEqual({
      kind: 'refine',
      message_key: 'query.refine',
      message_params: null,
      should_refine: true,
    });
  });
});
