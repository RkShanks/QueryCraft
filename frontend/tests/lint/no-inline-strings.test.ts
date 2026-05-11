import { describe, it, expect } from 'vitest';
import { ESLint } from 'eslint';
import path from 'path';
import fs from 'fs';

async function lintSource(source: string, filename = 'Fixture.tsx') {
  const fixtureDir = path.resolve(__dirname, '../../tmp');
  if (!fs.existsSync(fixtureDir)) {
    fs.mkdirSync(fixtureDir, { recursive: true });
  }
  const filePath = path.join(fixtureDir, filename);
  fs.writeFileSync(filePath, source, 'utf-8');

  const eslint = new ESLint({
    overrideConfigFile: path.resolve(__dirname, '../../eslint.config.js'),
    overrideConfig: {
      ignores: ['dist', 'coverage', 'src/api/generated/**'],
    },
  });

  const results = await eslint.lintFiles([filePath]);
  fs.unlinkSync(filePath);
  return results[0]?.messages ?? [];
}

describe('T-179: no-inline-strings ESLint regression', () => {
  it('catches inline JSX text as a violation', async () => {
    const source = `export const Fixture = () => <div>Hello world</div>;`;
    const messages = await lintSource(source);
    const violation = messages.find((m) => m.ruleId === 'local/no-inline-user-strings');
    expect(violation).toBeDefined();
    expect(violation?.messageId).toBe('jsxText');
  });

  it('allows t() wrapped strings with zero violations', async () => {
    const source = `
      import { useTranslation } from 'react-i18next';
      export const Fixture = () => {
        const { t } = useTranslation();
        return <div>{t('hello')}</div>;
      };
    `;
    const messages = await lintSource(source);
    const violation = messages.find((m) => m.ruleId === 'local/no-inline-user-strings');
    expect(violation).toBeUndefined();
  });

  it('catches inline attribute strings', async () => {
    const source = `export const Fixture = () => <input placeholder="Search" />;`;
    const messages = await lintSource(source);
    const violation = messages.find((m) => m.ruleId === 'local/no-inline-user-strings');
    expect(violation).toBeDefined();
    expect(violation?.messageId).toBe('jsxAttr');
  });

  it('allows attribute strings wrapped in t()', async () => {
    const source = `
      import { useTranslation } from 'react-i18next';
      export const Fixture = () => {
        const { t } = useTranslation();
        return <input placeholder={t('search.placeholder')} />;
      };
    `;
    const messages = await lintSource(source);
    const violation = messages.find((m) => m.ruleId === 'local/no-inline-user-strings');
    expect(violation).toBeUndefined();
  });
});
