import { afterAll, describe, expect, it } from 'vitest';
import { mkdtempSync, readFileSync, readdirSync, rmSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const FRONTEND_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const REPOSITORY_ROOT = resolve(FRONTEND_ROOT, '..');
const CANONICAL_OPENAPI = join(REPOSITORY_ROOT, 'backend/openapi.json');
const GENERATED_SDK = join(FRONTEND_ROOT, 'src/api/generated/sdk.gen.ts');
const GENERATED_ROOT = join(FRONTEND_ROOT, 'src/api/generated');
const GENERATOR = join(FRONTEND_ROOT, 'scripts/generate-api-client.mjs');
const HTTP_METHODS = new Set(['delete', 'get', 'patch', 'post', 'put']);
const temporaryRoot = mkdtempSync(join(tmpdir(), 'querycraft-openapi-client-'));

afterAll(() => {
  rmSync(temporaryRoot, { recursive: true, force: true });
});

function operationIds(): Set<string> {
  const contract = JSON.parse(readFileSync(CANONICAL_OPENAPI, 'utf8')) as {
    paths: Record<string, Record<string, { operationId?: string }>>;
  };
  return new Set(
    Object.values(contract.paths).flatMap((pathItem) =>
      Object.entries(pathItem)
        .filter(([method]) => HTTP_METHODS.has(method))
        .map(([, operation]) => operation.operationId)
        .filter((operationId): operationId is string => Boolean(operationId))
    )
  );
}

function generatedFunctions(directory = GENERATED_ROOT): Set<string> {
  const source = readFileSync(join(directory, 'sdk.gen.ts'), 'utf8');
  return new Set([...source.matchAll(/^export const (\w+) =/gm)].map((match) => match[1]));
}

function generatedFiles(directory: string): Map<string, Buffer> {
  const files = new Map<string, Buffer>();
  const visit = (currentDirectory: string): void => {
    for (const entry of readdirSync(currentDirectory)) {
      const absolutePath = join(currentDirectory, entry);
      if (statSync(absolutePath).isDirectory()) {
        visit(absolutePath);
      } else {
        files.set(relative(directory, absolutePath), readFileSync(absolutePath));
      }
    }
  };
  visit(directory);
  return files;
}

function generateInto(outputDirectory: string): void {
  const generation = spawnSync(process.execPath, [GENERATOR, '--output', outputDirectory], {
    cwd: FRONTEND_ROOT,
    encoding: 'utf8',
  });
  expect(generation.status, generation.stderr || generation.stdout).toBe(0);
}

describe('canonical generated API contract', () => {
  it('generates exactly one client function for every canonical operation', () => {
    expect(generatedFunctions()).toEqual(operationIds());
  });

  it('preserves representative caller-facing operation names', () => {
    const functions = generatedFunctions();
    for (const operationName of [
      'signIn',
      'submitQuestion',
      'getQueryLimits',
      'listAdminConnections',
      'searchAuditEntries',
      'exportAuditEntries',
      'oidcLogin',
      'samlCallback',
    ]) {
      expect(functions).toContain(operationName);
    }
  });

  it(
    'produces byte-identical output twice and matches the checked-in client',
    () => {
      const firstOutput = join(temporaryRoot, 'first');
      const secondOutput = join(temporaryRoot, 'second');
      generateInto(firstOutput);
      generateInto(secondOutput);

      expect(generatedFiles(firstOutput)).toEqual(generatedFiles(secondOutput));
      expect(generatedFiles(firstOutput)).toEqual(generatedFiles(GENERATED_ROOT));
    },
    60_000
  );
});
