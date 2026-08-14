import assert from 'node:assert/strict';
import test from 'node:test';

import { findHarnessViolations } from './check-test-harness.mjs';

function violations(source, classification = {}) {
  return findHarnessViolations({
    files: [{ path: 'tests/e2e/example.spec.ts', source }],
    classification: {
      specs: {
        'tests/e2e/example.spec.ts': {
          category: 'mocked',
          reason: 'Exercises a deterministic browser response state.',
          ...classification,
        },
      },
      skips: [],
    },
  });
}

test('rejects tracked evidence output and stale permission fixtures', () => {
  const result = violations(`
    const permission = 'history.read';
    await page.screenshot({ path: '../audit/wave-18/protected.png' });
  `);

  assert.ok(result.some((entry) => entry.rule === 'tracked-browser-output'));
  assert.ok(result.some((entry) => entry.rule === 'stale-permission'));
});

test('rejects unclassified browser mocks and skips without superseding evidence', () => {
  const mockResult = violations(
    `await page.route('**/api/v1/sessions', route => route.fulfill({ body: '{}' }));`,
    { category: 'live' }
  );
  assert.ok(mockResult.some((entry) => entry.rule === 'unclassified-browser-mock'));

  const skipResult = violations(`test.skip('future check', async () => {});`);
  assert.ok(skipResult.some((entry) => entry.rule === 'unclassified-skip'));
});

test('rejects function-existence checks that do not observe named state', () => {
  const result = violations(`
    expect(typeof result.current.mutate).toBe('function');
    expect(page.reload).toBeDefined();
  `);

  assert.ok(result.some((entry) => entry.rule === 'function-existence-assertion'));
});

test('accepts isolated output and fully classified mocks and skips', () => {
  const result = findHarnessViolations({
    files: [
      {
        path: 'tests/e2e/example.spec.ts',
        source: `
          await page.route('**/api/v1/sessions', route => route.fulfill({ body: '{}' }));
          test.skip('live provider unavailable', async () => {});
          await page.screenshot({ path: testInfo.outputPath('state.png') });
          await expect(page.getByRole('alert')).toContainText('Unable to load');
        `,
      },
    ],
    classification: {
      specs: {
        'tests/e2e/example.spec.ts': {
          category: 'mocked',
          reason: 'Exercises a deterministic browser response state.',
        },
      },
      skips: [
        {
          spec: 'tests/e2e/example.spec.ts',
          title: 'live provider unavailable',
          reason: 'Requires a provider service outside the deterministic suite.',
          supersededBy: 'tests/e2e/example.spec.ts mocked response-state check',
        },
      ],
    },
  });

  assert.deepEqual(result, []);
});
