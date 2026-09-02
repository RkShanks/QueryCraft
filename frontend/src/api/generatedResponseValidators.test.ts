import { describe, expect, it } from 'vitest';
import {
  responseComponentSchemas,
  responseOperationManifest,
} from './generated/responseManifest.gen';
import {
  responseValidatorByOperationStatus,
  unionAlternativeValidatorsById,
} from './generated/responseValidators.gen';

const UNION_VALIDATOR_ID = 'x-querycraft-union-validator';
type JsonRecord = Record<string, unknown>;

function collectUnionValidatorIds(schema: unknown, unionIds: Set<string>): void {
  if (Array.isArray(schema)) {
    for (const entry of schema) collectUnionValidatorIds(entry, unionIds);
    return;
  }
  if (!schema || typeof schema !== 'object') return;

  const schemaObject = schema as JsonRecord;
  const alternatives = schemaObject.anyOf ?? schemaObject.oneOf;
  if (Array.isArray(alternatives)) {
    const unionId = schemaObject[UNION_VALIDATOR_ID];
    expect(unionId).toEqual(expect.any(String));
    const validators = unionAlternativeValidatorsById[unionId as string];
    expect(validators).toHaveLength(alternatives.length);
    expect(validators.every((validator) => typeof validator === 'function')).toBe(true);
    unionIds.add(unionId as string);
  }

  for (const nestedSchema of Object.values(schemaObject)) {
    collectUnionValidatorIds(nestedSchema, unionIds);
  }
}

describe('generated standalone response validators', () => {
  it('maps every canonical JSON response contract by operation and status', () => {
    const expectedKeys = responseOperationManifest.flatMap((operation) =>
      operation.responses
        .filter((response) => response.schema !== null)
        .map((response) => `${operation.operationId}:${response.status}`)
    );

    expect(Object.keys(responseValidatorByOperationStatus).sort()).toEqual(expectedKeys.sort());
    expect(
      Object.values(responseValidatorByOperationStatus).every(
        (validator) => typeof validator === 'function'
      )
    ).toBe(true);
  });

  it('maps every generated sanitization union to its alternative validators', () => {
    const unionIds = new Set<string>();
    for (const operation of responseOperationManifest) {
      for (const response of operation.responses) {
        collectUnionValidatorIds(response.schema, unionIds);
      }
    }
    collectUnionValidatorIds(responseComponentSchemas, unionIds);

    expect(Object.keys(unionAlternativeValidatorsById).sort()).toEqual([...unionIds].sort());
    expect(unionIds.size).toBeGreaterThan(0);
  });
});
