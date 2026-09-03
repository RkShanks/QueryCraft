import {
  responseComponentSchemas,
  responseOperationManifest,
} from './generated/responseManifest.gen';
import {
  responseValidatorByOperationStatus,
  unionAlternativeValidatorsById,
} from './generated/responseValidators.gen';
import type {
  AcceptedQueryDetail,
  AcceptedQuerySummary,
  AuditRetentionResponse,
  AuditSearchResponse,
  DetectionThresholdRead,
  HistoryListResponse,
  QueryResult,
  QuotaStatusResponse,
  SessionDetail,
  SessionListResponse,
  SessionSummary,
} from './generated/types.gen';

export const CLIENT_CONTRACT_ERROR_CODE = 'client_contract_invalid_response' as const;

export class ClientContractError extends Error {
  readonly code = CLIENT_CONTRACT_ERROR_CODE;

  constructor() {
    super(CLIENT_CONTRACT_ERROR_CODE);
    this.name = 'ClientContractError';
  }
}

export function isClientContractError(error: unknown): error is ClientContractError {
  return (
    error instanceof ClientContractError ||
    (typeof error === 'object' &&
      error !== null &&
      (error as { code?: unknown }).code === CLIENT_CONTRACT_ERROR_CODE)
  );
}

type ManifestOperation = (typeof responseOperationManifest)[number];
type JsonRecord = Record<string, unknown>;
type ResponseValidator = (response: unknown) => boolean;

const manifestById: ReadonlyMap<string, ManifestOperation> = new Map(
  responseOperationManifest.map((operation) => [operation.operationId, operation])
);
const timestampPattern = /(?:Z|[+-]\d{2}:\d{2})$/;
const componentSchemas = new Map<string, JsonRecord>(
  Object.entries(responseComponentSchemas) as [string, JsonRecord][]
);
const responseValidators: Readonly<Record<string, ResponseValidator>> =
  responseValidatorByOperationStatus;
const unionValidators: Readonly<Record<string, readonly ResponseValidator[]>> =
  unionAlternativeValidatorsById;
const UNION_VALIDATOR_ID = 'x-querycraft-union-validator';

function failContract(): never {
  throw new ClientContractError();
}

function isValidTimestamp(timestamp: string): boolean {
  return timestampPattern.test(timestamp) && !Number.isNaN(Date.parse(timestamp));
}

function requireTimestamps(timestamps: string[]): void {
  if (timestamps.some((timestamp) => !isValidTimestamp(timestamp))) failContract();
}

function requireOptionalCursor(cursor: string | null | undefined): void {
  if (cursor === '') failContract();
}

function validateSessionList(response: SessionListResponse): void {
  if (response.total < 0) failContract();
  requireOptionalCursor(response.next_cursor);
  for (const session of response.items) {
    requireTimestamps([session.created_at, session.last_activity_at]);
  }
}

function validateSessionDetail(response: SessionDetail): void {
  if (response.attempts_total < 0) failContract();
  requireOptionalCursor(response.attempts_next_cursor);
  requireTimestamps([response.created_at, response.last_activity_at]);
  requireTimestamps(response.attempts.map((attempt) => attempt.accepted_at));
}

function validateSessionSummary(response: SessionSummary): void {
  requireTimestamps([response.created_at, response.last_activity_at]);
}

function validateHistoryList(response: HistoryListResponse): void {
  if (response.total !== null && response.total !== undefined && response.total < 0) {
    failContract();
  }
  requireOptionalCursor(response.next_cursor);
  requireTimestamps(response.items.map((entry) => entry.accepted_at));
}

function validateAcceptedQuery(
  response: AcceptedQueryDetail | AcceptedQuerySummary
): void {
  requireTimestamps([response.accepted_at]);
}

function validateQueryResult(response: QueryResult): void {
  if (response.attempt_number < 1 || response.row_count !== response.rows.length) {
    failContract();
  }
  if (response.rows.some((row) => row.length !== response.columns.length)) failContract();
}

function validateQuotaStatus(response: QuotaStatusResponse): void {
  if (response.total < 0) failContract();
  requireOptionalCursor(response.next_cursor);
  for (const roleStatus of response.status) {
    for (const dimension of Object.values(roleStatus.dimensions)) {
      if (dimension.used < 0 || (dimension.limit !== null && dimension.limit !== undefined && dimension.limit < 0)) {
        failContract();
      }
      if (dimension.remaining !== null && dimension.remaining !== undefined && dimension.remaining < 0) {
        failContract();
      }
    }
  }
}

function validateAuditPagination(response: AuditSearchResponse): void {
  const pagination = response.pagination;
  if (
    pagination.page < 1 ||
    pagination.page_size < 1 ||
    pagination.total_entries < 0 ||
    pagination.total_pages < 0
  ) {
    failContract();
  }
}

function validateAuditRetention(response: AuditRetentionResponse): void {
  if (response.retention_months < 0) failContract();
  if (response.last_purge_at && !isValidTimestamp(response.last_purge_at)) failContract();
  if (response.purged_count !== null && response.purged_count !== undefined && response.purged_count < 0) {
    failContract();
  }
}

function validateDetectionThresholds(response: DetectionThresholdRead): void {
  const { block_confidence: block, flag_confidence: flag } = response;
  if (!Number.isFinite(block) || !Number.isFinite(flag)) failContract();
  if (block < 0 || block > 1 || flag < 0 || flag > 1 || block <= flag) failContract();
}

function validateSessionOperation(operationId: string, response: unknown): void {
  if (operationId === 'getSessions') validateSessionList(response as SessionListResponse);
  if (operationId === 'getSession') validateSessionDetail(response as SessionDetail);
  if (['createSession', 'updateSessionConnection'].includes(operationId)) {
    validateSessionSummary(response as SessionSummary);
  }
}

function validateQueryOperation(operationId: string, response: unknown): void {
  if (operationId === 'listHistory') validateHistoryList(response as HistoryListResponse);
  if (['acceptQuery', 'getHistoryEntry'].includes(operationId)) {
    validateAcceptedQuery(response as AcceptedQueryDetail);
  }
  if (
    ['submitQuestion', 'rejectQuery', 'regenerateQuery'].includes(operationId) &&
    (response as JsonRecord).kind !== 'refine'
  ) {
    validateQueryResult(response as QueryResult);
  }
}

function validateSemanticContract(operationId: string, status: number, response: unknown): void {
  if (status >= 400) return;
  validateSessionOperation(operationId, response);
  validateQueryOperation(operationId, response);
  if (operationId === 'getQuotaStatus') validateQuotaStatus(response as QuotaStatusResponse);
  if (operationId === 'searchAuditEntries') validateAuditPagination(response as AuditSearchResponse);
  if (operationId === 'getAuditRetention') {
    validateAuditRetention(response as AuditRetentionResponse);
  }
  if (['getDetectionConfig', 'updateDetectionConfig'].includes(operationId)) {
    validateDetectionThresholds(response as DetectionThresholdRead);
  }
}

function responseContract(operation: ManifestOperation, status: number) {
  return operation.responses.find((response) => response.status === String(status));
}

function operationValidator(operation: ManifestOperation, status: number): ResponseValidator {
  const validator = responseValidators[`${operation.operationId}:${status}`];
  if (!validator) failContract();
  return validator;
}

function resolvedSchema(schema: JsonRecord): JsonRecord {
  const reference = schema.$ref;
  if (typeof reference !== 'string') return schema;
  const componentName = reference.split('/').at(-1);
  const componentSchema = componentName ? componentSchemas.get(componentName) : undefined;
  return componentSchema ? resolvedSchema(componentSchema) : schema;
}

function matchingUnionSchema(schema: JsonRecord, responseBody: unknown): JsonRecord | undefined {
  const alternatives = schema.anyOf ?? schema.oneOf;
  if (!Array.isArray(alternatives)) return undefined;
  const unionId = schema[UNION_VALIDATOR_ID];
  if (typeof unionId !== 'string') failContract();
  const alternativeValidators = unionValidators[unionId];
  if (!alternativeValidators || alternativeValidators.length !== alternatives.length) {
    failContract();
  }
  const responseKeys = new Set(
    responseBody && typeof responseBody === 'object' && !Array.isArray(responseBody)
      ? Object.keys(responseBody)
      : []
  );
  return (alternatives as JsonRecord[])
    .filter((_alternative, index) => alternativeValidators[index](responseBody))
    .sort((left, right) => {
      const matchingProperties = (alternative: JsonRecord) =>
        Object.keys(resolvedSchema(alternative).properties ?? {}).filter((key) =>
          responseKeys.has(key)
        ).length;
      return matchingProperties(right) - matchingProperties(left);
    })[0];
}

function sanitizeArray(schema: JsonRecord, responseBody: unknown[]): unknown[] {
  if (!schema.items || typeof schema.items !== 'object') return responseBody;
  return responseBody.map((entry) => sanitizeResponse(schema.items as JsonRecord, entry));
}

function sanitizeObject(schema: JsonRecord, responseBody: JsonRecord): JsonRecord {
  const properties = schema.properties;
  if (!properties || typeof properties !== 'object') return responseBody;

  const sanitized: JsonRecord = {};
  for (const [key, propertySchema] of Object.entries(properties)) {
    if (Object.hasOwn(responseBody, key)) {
      sanitized[key] = sanitizeResponse(propertySchema as JsonRecord, responseBody[key]);
    }
  }
  const additional = schema.additionalProperties;
  if (additional === true) return { ...responseBody, ...sanitized };
  if (additional && typeof additional === 'object') {
    for (const [key, entry] of Object.entries(responseBody)) {
      if (!Object.hasOwn(properties, key)) {
        sanitized[key] = sanitizeResponse(additional as JsonRecord, entry);
      }
    }
  }
  return sanitized;
}

function sanitizeResponse(schema: JsonRecord, responseBody: unknown): unknown {
  const resolved = resolvedSchema(schema);
  const unionSchema = matchingUnionSchema(resolved, responseBody);
  if (unionSchema) return sanitizeResponse(unionSchema, responseBody);
  if (Array.isArray(responseBody)) return sanitizeArray(resolved, responseBody);
  if (responseBody && typeof responseBody === 'object') {
    return sanitizeObject(resolved, responseBody as JsonRecord);
  }
  return responseBody;
}

export function validateOperationResponse(
  operationId: string,
  status: number,
  responseBody: unknown
): unknown {
  const operation = manifestById.get(operationId);
  if (!operation) failContract();
  let responseCopy: unknown;
  try {
    responseCopy = structuredClone(responseBody);
  } catch {
    failContract();
  }
  if (!operationValidator(operation, status)(responseCopy)) failContract();
  const contract = responseContract(operation, status);
  if (!contract?.schema) failContract();
  const validatedBody = sanitizeResponse(contract.schema as JsonRecord, responseCopy);
  validateSemanticContract(operationId, status, validatedBody);
  return validatedBody;
}

function pathMatches(template: string, pathname: string): boolean {
  const expectedSegments = template.split('/');
  const actualSegments = pathname.split('/');
  if (expectedSegments.length !== actualSegments.length) return false;
  return expectedSegments.every(
    (segment, index) =>
      (segment.startsWith('{') && segment.endsWith('}')) || segment === actualSegments[index]
  );
}

function requestOperation(request: Request): ManifestOperation | undefined {
  const pathname = new URL(request.url).pathname;
  return responseOperationManifest
    .filter(
      (operation) => operation.method === request.method && pathMatches(operation.path, pathname)
    )
    .sort((left, right) => {
      const leftParameters = left.path.split('/').filter((segment) => segment.startsWith('{')).length;
      const rightParameters = right.path.split('/').filter((segment) => segment.startsWith('{')).length;
      return leftParameters - rightParameters;
    })[0];
}

function shouldValidateResponse(operation: ManifestOperation, response: Response): boolean {
  if (operation.classification === 'consumed_json') return true;
  return !response.ok && operation.classification !== 'browser_redirect';
}

function sanitizedJsonResponse(response: Response, validatedBody: unknown): Response {
  const headers = new Headers(response.headers);
  headers.delete('content-encoding');
  headers.delete('content-length');
  headers.delete('transfer-encoding');
  return new Response(JSON.stringify(validatedBody), {
    headers,
    status: response.status,
    statusText: response.statusText,
  });
}

async function validateFetchResponse(request: Request, response: Response): Promise<Response> {
  const operation = requestOperation(request);
  if (!operation || !shouldValidateResponse(operation, response)) return response;
  const contract = responseContract(operation, response.status);
  if (!contract || !response.headers.get('content-type')?.includes('application/json')) {
    failContract();
  }

  let responseBody: unknown;
  try {
    responseBody = await response.clone().json();
  } catch {
    failContract();
  }
  const validatedBody = validateOperationResponse(
    operation.operationId,
    response.status,
    responseBody
  );
  return sanitizedJsonResponse(response, validatedBody);
}

export const validatedApiFetch: typeof fetch = async (input, init) => {
  const request = input instanceof Request ? input : new Request(input, init);
  const response = await globalThis.fetch(input, init);
  return validateFetchResponse(request, response);
};
