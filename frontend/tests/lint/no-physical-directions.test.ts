import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

function findFiles(dir: string, extensions: string[]): string[] {
  const results: string[] = [];
  if (!fs.existsSync(dir)) return results;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory() && entry.name !== 'node_modules' && entry.name !== 'dist') {
      results.push(...findFiles(fullPath, extensions));
    } else if (entry.isFile() && extensions.some((ext) => fullPath.endsWith(ext))) {
      results.push(fullPath);
    }
  }
  return results;
}

const PHYSICAL_PATTERNS = [
  /margin-left\s*:/,
  /margin-right\s*:/,
  /padding-left\s*:/,
  /padding-right\s*:/,
  /text-align\s*:\s*left/,
  /text-align\s*:\s*right/,
];

describe('T-180: no physical-direction CSS declarations', () => {
  const srcDir = path.resolve(__dirname, '../../src');
  const files = findFiles(srcDir, ['.css', '.tsx', '.ts']);

  it('has source files to scan', () => {
    expect(files.length).toBeGreaterThan(0);
  });

  it('zero physical-direction declarations in source', () => {
    const violations: Array<{ file: string; line: number; text: string }> = [];
    for (const file of files) {
      const content = fs.readFileSync(file, 'utf-8');
      const lines = content.split('\n');
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        for (const pattern of PHYSICAL_PATTERNS) {
          if (pattern.test(line)) {
            violations.push({ file: path.relative(srcDir, file), line: i + 1, text: line.trim() });
          }
        }
      }
    }
    expect(violations).toEqual([]);
  });
});
