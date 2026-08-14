import { createClient } from '@hey-api/openapi-ts';
import {
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const CANONICAL_OPENAPI = resolve(FRONTEND_ROOT, '../backend/openapi.json');
const DEFAULT_OUTPUT = resolve(FRONTEND_ROOT, 'src/api/generated');
const RESPONSE_CLASSIFICATIONS = resolve(
  FRONTEND_ROOT,
  'scripts/response-operation-classifications.json',
);

const CLASSIFICATION_NAMES = [
  'consumed_json',
  'no_body',
  'browser_redirect',
  'blob_download',
  'unused',
];

function parseArguments(argumentsList) {
  let output = DEFAULT_OUTPUT;
  let check = false;
  for (let index = 0; index < argumentsList.length; index += 1) {
    const argument = argumentsList[index];
    if (argument === '--check') {
      check = true;
    } else if (argument === '--output' && argumentsList[index + 1]) {
      output = resolve(argumentsList[index + 1]);
      index += 1;
    } else {
      throw new Error(`Unknown or incomplete argument: ${argument}`);
    }
  }
  return { check, output };
}

async function generate(output) {
  await createClient({
    input: CANONICAL_OPENAPI,
    output: { clean: true, path: output },
    plugins: [
      '@hey-api/typescript',
      '@hey-api/schemas',
      {
        name: '@hey-api/client-fetch',
        runtimeConfigPath: '../generatedClientConfig',
      },
      '@hey-api/sdk',
    ],
    logs: { file: false, level: 'silent' },
  });
  writeResponseManifest(output);
}

function canonicalOperations(openapi) {
  const operations = [];
  for (const [path, pathOperations] of Object.entries(openapi.paths)) {
    for (const [method, operation] of Object.entries(pathOperations)) {
      if (!operation.operationId) continue;
      operations.push({ method: method.toUpperCase(), operation, path });
    }
  }
  return operations.sort((left, right) =>
    left.operation.operationId.localeCompare(right.operation.operationId),
  );
}

function classificationsByOperation(classificationSource) {
  const classifications = new Map();
  for (const classification of CLASSIFICATION_NAMES) {
    for (const operationId of classificationSource.classifications[classification] ?? []) {
      if (classifications.has(operationId)) {
        throw new Error(`Duplicate response classification for ${operationId}`);
      }
      classifications.set(operationId, classification);
    }
  }
  return classifications;
}

function responseContracts(operation) {
  return Object.entries(operation.responses)
    .flatMap(([status, response]) =>
      Object.entries(response.content ?? {})
        .filter(([contentType]) => contentType === 'application/json')
        .map(([contentType, media]) => ({
          contentType,
          schema: media.schema ?? null,
          status,
        })),
    )
    .sort((left, right) => left.status.localeCompare(right.status));
}

function writeResponseManifest(output) {
  const openapi = JSON.parse(readFileSync(CANONICAL_OPENAPI, 'utf8'));
  const classificationSource = JSON.parse(readFileSync(RESPONSE_CLASSIFICATIONS, 'utf8'));
  const classifications = classificationsByOperation(classificationSource);
  const operations = canonicalOperations(openapi);
  const operationIds = new Set(operations.map(({ operation }) => operation.operationId));

  for (const operationId of classifications.keys()) {
    if (!operationIds.has(operationId)) {
      throw new Error(`Classified response operation is absent from OpenAPI: ${operationId}`);
    }
  }
  for (const operationId of operationIds) {
    if (!classifications.has(operationId)) {
      throw new Error(`OpenAPI response operation is unclassified: ${operationId}`);
    }
  }

  const manifest = operations.map(({ method, operation, path }) => ({
    classification: classifications.get(operation.operationId),
    method,
    operationId: operation.operationId,
    path,
    responses: responseContracts(operation),
    unusedReason: classificationSource.unused_reasons[operation.operationId] ?? null,
  }));
  const source = [
    '// This file is auto-generated from backend/openapi.json.',
    '',
    `export const responseOperationManifest = ${JSON.stringify(manifest, null, 2)} as const;`,
    '',
  ].join('\n');
  writeFileSync(join(output, 'responseManifest.gen.ts'), source);
}

function filesByRelativePath(directory) {
  const files = new Map();
  const visit = (currentDirectory) => {
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

function findDifference(expected, actual) {
  const expectedFiles = filesByRelativePath(expected);
  const actualFiles = filesByRelativePath(actual);
  const allPaths = new Set([...expectedFiles.keys(), ...actualFiles.keys()]);
  for (const filePath of [...allPaths].sort()) {
    const expectedContent = expectedFiles.get(filePath);
    const actualContent = actualFiles.get(filePath);
    if (!expectedContent || !actualContent || !expectedContent.equals(actualContent)) {
      return filePath;
    }
  }
  return undefined;
}

async function main() {
  const { check, output } = parseArguments(process.argv.slice(2));
  if (!check) {
    await generate(output);
    return;
  }

  const comparisonRoot = mkdtempSync(join(tmpdir(), 'querycraft-generated-api-check-'));
  try {
    const generatedOutput = join(comparisonRoot, 'generated');
    await generate(generatedOutput);
    const difference = findDifference(output, generatedOutput);
    if (difference) {
      throw new Error(`Generated API client drift detected at ${difference}`);
    }
  } finally {
    rmSync(comparisonRoot, { recursive: true, force: true });
  }
}

await main();
