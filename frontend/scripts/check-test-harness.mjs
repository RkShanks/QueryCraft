import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ALLOWED_CATEGORIES = new Set([
  'mocked',
  'live',
  'deterministic-provider',
  'setup-dependent',
  'deferred-placeholder',
]);

function violation(file, rule, detail) {
  return { file, rule, detail };
}

function quotedSkipLabels(source) {
  const labels = [];
  const skipPattern = /test\.skip\s*\(([^;]*?)\)/gs;
  for (const match of source.matchAll(skipPattern)) {
    const strings = [...match[1].matchAll(/(['"`])([^'"`]+)\1/g)].map((entry) => entry[2]);
    labels.push(strings.at(-1) ?? '<dynamic skip>');
  }
  return labels;
}

function hasBrowserMock(source) {
  return /\b(?:page|context)\.route\s*\(|\broute\.fulfill\s*\(/.test(source);
}

function hasTrackedBrowserOutput(source) {
  return (
    /\bEVIDENCE_DIR\b/.test(source) ||
    /(?:screenshot|tracing|video)[\s\S]{0,240}(?:\.\.\/)?(?:audit|specs)\//.test(source)
  );
}

function hasFunctionExistenceAssertion(source) {
  return (
    /expect\s*\(\s*typeof\s+[^)]*\)\s*\.toBe\(\s*['"]function['"]\s*\)/.test(source) ||
    /expect\s*\([^)]*\)\s*\.toBeTypeOf\(\s*['"]function['"]\s*\)/.test(source) ||
    /expect\s*\(\s*[^)]*\.(?:mutate|mutateAsync|refetch|reload|fetchNextPage|submitQuestion|rejectQuery|regenerateQuery|acceptQuery)\s*\)\s*\.toBeDefined\(\s*\)/.test(source)
  );
}

export function findHarnessViolations({ files, classification }) {
  const violations = [];
  const specs = classification?.specs ?? {};
  const skips = classification?.skips ?? [];
  const mockHelpers = classification?.mockHelpers ?? [];
  const filePaths = new Set(files.map((file) => file.path));

  for (const file of files) {
    const isSpec = file.path.endsWith('.spec.ts') || file.path.endsWith('.spec.tsx');
    const specClassification = specs[file.path];

    if (isSpec) {
      if (!specClassification) {
        violations.push(violation(file.path, 'unclassified-spec', 'Every browser spec needs a classification.'));
      } else if (
        !ALLOWED_CATEGORIES.has(specClassification.category) ||
        typeof specClassification.reason !== 'string' ||
        specClassification.reason.trim().length === 0
      ) {
        violations.push(violation(file.path, 'invalid-spec-classification', 'Category and reason are required.'));
      }
    }

    if (hasBrowserMock(file.source)) {
      const helperClassification = mockHelpers.find((entry) => entry.path === file.path);
      const classifiedMock =
        specClassification &&
        ['mocked', 'deterministic-provider', 'setup-dependent'].includes(specClassification.category);
      if (!classifiedMock && !helperClassification) {
        violations.push(violation(file.path, 'unclassified-browser-mock', 'Browser routes must be classified as mocked.'));
      }
    }

    if (hasTrackedBrowserOutput(file.source)) {
      violations.push(violation(file.path, 'tracked-browser-output', 'Browser artifacts must use testInfo.outputPath, ignored output, or /tmp.'));
    }
    if (/['"]history\.read['"]/.test(file.source)) {
      violations.push(violation(file.path, 'stale-permission', 'Use the current query.history.view permission.'));
    }
    if (hasFunctionExistenceAssertion(file.source)) {
      violations.push(violation(file.path, 'function-existence-assertion', 'Assert observable behavior or named state.'));
    }

    for (const title of quotedSkipLabels(file.source)) {
      const metadata = skips.find((entry) => entry.spec === file.path && entry.title === title);
      if (
        !metadata ||
        typeof metadata.reason !== 'string' ||
        !metadata.reason.trim() ||
        typeof metadata.supersededBy !== 'string' ||
        !metadata.supersededBy.trim()
      ) {
        violations.push(violation(file.path, 'unclassified-skip', `Missing skip metadata for: ${title}`));
      }
    }
  }

  for (const specPath of Object.keys(specs)) {
    if (!filePaths.has(specPath)) {
      violations.push(violation(specPath, 'orphan-spec-classification', 'Classification does not map to a browser spec.'));
    }
  }
  for (const helper of mockHelpers) {
    if (!filePaths.has(helper.path) || typeof helper.reason !== 'string' || !helper.reason.trim()) {
      violations.push(violation(helper.path, 'invalid-mock-helper-classification', 'Mock helper path and reason must be valid.'));
    }
  }

  return violations;
}

function collectSourceFiles(root, relativeDirectory) {
  const absoluteDirectory = path.join(root, relativeDirectory);
  if (!fs.existsSync(absoluteDirectory)) return [];
  return fs.readdirSync(absoluteDirectory, { withFileTypes: true }).flatMap((entry) => {
    const relativePath = path.posix.join(relativeDirectory, entry.name);
    if (entry.isDirectory()) return collectSourceFiles(root, relativePath);
    if (!/\.(?:ts|tsx|mjs)$/.test(entry.name)) return [];
    return [{ path: relativePath, source: fs.readFileSync(path.join(root, relativePath), 'utf8') }];
  });
}

function run() {
  const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  const classification = JSON.parse(
    fs.readFileSync(path.join(frontendRoot, 'tests/e2e/classification.json'), 'utf8')
  );
  const files = [
    ...collectSourceFiles(frontendRoot, 'tests/e2e'),
    ...collectSourceFiles(frontendRoot, 'src'),
  ];
  const violations = findHarnessViolations({ files, classification });
  if (violations.length) {
    for (const entry of violations) {
      process.stderr.write(`${entry.file}: ${entry.rule}: ${entry.detail}\n`);
    }
    process.exitCode = 1;
    return;
  }
  process.stdout.write(`Harness guard passed (${Object.keys(classification.specs).length} specs classified).\n`);
}

const invokedPath = process.argv[1] ? path.resolve(process.argv[1]) : '';
if (invokedPath === fileURLToPath(import.meta.url)) run();
