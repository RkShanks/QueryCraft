import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

describe('T-181: built CSS bundle has no physical-direction utilities', () => {
  const distDir = path.resolve(__dirname, '../../dist');

  it('skips if dist/ does not exist', () => {
    if (!fs.existsSync(distDir)) {
      console.warn('Skipping T-181: dist/ not found. Run npm run build first.');
    }
  });

  it('zero physical-direction utilities in built CSS', () => {
    if (!fs.existsSync(distDir)) {
      return;
    }

    function findCssFiles(dir: string): string[] {
      const results: string[] = [];
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          results.push(...findCssFiles(fullPath));
        } else if (entry.isFile() && fullPath.endsWith('.css')) {
          results.push(fullPath);
        }
      }
      return results;
    }

    const cssFiles = findCssFiles(distDir);
    expect(cssFiles.length).toBeGreaterThan(0);

    const PHYSICAL_UTILITIES = [
      /\.ml-/,   // margin-left
      /\.mr-/,   // margin-right
      /\.pl-/,   // padding-left
      /\.pr-/,   // padding-right
      /\.text-left/,   // text-align left
      /\.text-right/,  // text-align right
      /\.left-/,       // left positioning
      /\.right-/,      // right positioning
    ];

    const violations: Array<{ file: string; line: number; text: string }> = [];
    for (const file of cssFiles) {
      const content = fs.readFileSync(file, 'utf-8');
      const lines = content.split('\n');
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        for (const pattern of PHYSICAL_UTILITIES) {
          if (pattern.test(line)) {
            violations.push({ file: path.relative(distDir, file), line: i + 1, text: line.trim() });
          }
        }
      }
    }
    expect(violations).toEqual([]);
  });
});
