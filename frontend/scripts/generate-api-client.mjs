import { createClient } from '@hey-api/openapi-ts';
import {
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const CANONICAL_OPENAPI = resolve(FRONTEND_ROOT, '../backend/openapi.json');
const DEFAULT_OUTPUT = resolve(FRONTEND_ROOT, 'src/api/generated');

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
      {
        name: '@hey-api/client-fetch',
        runtimeConfigPath: '../generatedClientConfig',
      },
      '@hey-api/sdk',
    ],
    logs: { file: false, level: 'silent' },
  });
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
