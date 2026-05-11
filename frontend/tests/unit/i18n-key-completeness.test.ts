import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';
import en from '../../src/locales/en.json';

function flattenKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) => {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      return flattenKeys(v as Record<string, unknown>, key);
    }
    return [key];
  });
}

function findSourceFiles(dir: string): string[] {
  const results: string[] = [];
  if (!fs.existsSync(dir)) return results;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory() && entry.name !== 'node_modules' && entry.name !== 'dist') {
      results.push(...findSourceFiles(fullPath));
    } else if (
      entry.isFile() &&
      (fullPath.endsWith('.tsx') || fullPath.endsWith('.ts')) &&
      !fullPath.endsWith('.test.tsx') &&
      !fullPath.endsWith('.test.ts')
    ) {
      results.push(fullPath);
    }
  }
  return results;
}

describe('T-182: en.json key completeness', () => {
  const srcDir = path.resolve(__dirname, '../../src');
  const enKeys = new Set(flattenKeys(en));
  const referencedKeys = new Set<string>();

  it('extracts t() references from all source files', () => {
    const files = findSourceFiles(srcDir);
    expect(files.length).toBeGreaterThan(0);

    const tCallPattern = /t\(['"]([a-zA-Z0-9_.]+)['"]/g;
    for (const file of files) {
      const content = fs.readFileSync(file, 'utf-8');
      let match;
      while ((match = tCallPattern.exec(content)) !== null) {
        const key = match[1];
        // All i18n keys are namespaced with at least one dot
        if (key.includes('.')) {
          referencedKeys.add(key);
        }
      }
    }
  });

  it('every referenced key exists in en.json (hard fail)', () => {
    const missing: string[] = [];
    for (const key of referencedKeys) {
      if (!enKeys.has(key)) {
        missing.push(key);
      }
    }
    expect(missing).toEqual([]);
  });

  it('warns on unused en.json keys (soft check)', () => {
    const unused: string[] = [];
    for (const key of enKeys) {
      if (!referencedKeys.has(key)) {
        unused.push(key);
      }
    }
    if (unused.length > 0) {
      console.warn('T-182: Unused en.json keys (informational only):', unused);
    }
    // Soft warning — not a hard failure
    expect(true).toBe(true);
  });
});
