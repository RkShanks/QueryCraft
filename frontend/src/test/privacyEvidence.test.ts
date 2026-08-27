import { describe, expect, it } from 'vitest';
import { containsSensitiveCanary } from './privacyEvidence';

describe('privacy evidence scanner', () => {
  it('detects a canary in nested values without exposing the value', () => {
    const canary = `token=${crypto.randomUUID()}`;
    const payload = { outer: [{ inner: canary }] };

    expect(containsSensitiveCanary(payload, canary)).toBe(true);
  });

  it('does not match an unrelated value', () => {
    const canary = `token=${crypto.randomUUID()}`;

    expect(containsSensitiveCanary({ status: 'safe' }, canary)).toBe(false);
  });
});
