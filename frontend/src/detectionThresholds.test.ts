import { describe, it, expect } from 'vitest';
import { parseThresholdValue, validateThresholds } from './detectionThresholds';

describe('parseThresholdValue', () => {
  it('parses finite decimal values including exponent notation', () => {
    expect(parseThresholdValue('0.5')).toBe(0.5);
    expect(parseThresholdValue(' 0.8 ')).toBe(0.8);
    expect(parseThresholdValue('1')).toBe(1);
    expect(parseThresholdValue('0')).toBe(0);
    expect(parseThresholdValue('-0.25')).toBe(-0.25);
    expect(parseThresholdValue('1e-1')).toBeCloseTo(0.1);
  });

  it('rejects non-numeric and empty input without coercion', () => {
    expect(parseThresholdValue('')).toBeNull();
    expect(parseThresholdValue('   ')).toBeNull();
    expect(parseThresholdValue('abc')).toBeNull();
    expect(parseThresholdValue('NaN')).toBeNull();
    expect(parseThresholdValue('Infinity')).toBeNull();
    expect(parseThresholdValue('0.8abc')).toBeNull();
  });

  it('rejects non-finite magnitudes instead of coercing them', () => {
    expect(parseThresholdValue('1e999')).toBeNull();
    expect(parseThresholdValue('-1e999')).toBeNull();
  });
});

describe('validateThresholds', () => {
  it('accepts ordered in-range pairs including exact boundaries', () => {
    expect(validateThresholds('0.8', '0.5')).toEqual({
      ok: true,
      block: 0.8,
      flag: 0.5,
    });
    expect(validateThresholds('1', '0')).toEqual({ ok: true, block: 1, flag: 0 });
  });

  it('rejects unparseable values as invalid', () => {
    for (const [block, flag] of [
      ['', '0.5'],
      ['0.8', ''],
      ['abc', '0.5'],
      ['1e999', '0.5'],
      ['-1e999', '0.5'],
    ]) {
      expect(validateThresholds(block, flag)).toEqual({ ok: false, issue: 'invalid' });
    }
  });

  it('rejects values below 0 or above 1 as out of range before ordering', () => {
    expect(validateThresholds('-0.5', '0.5')).toEqual({ ok: false, issue: 'range' });
    expect(validateThresholds('1.5', '0.5')).toEqual({ ok: false, issue: 'range' });
    expect(validateThresholds('0.8', '-0.1')).toEqual({ ok: false, issue: 'range' });
    expect(validateThresholds('0.8', '1.1')).toEqual({ ok: false, issue: 'range' });
    expect(validateThresholds('-2', '-1')).toEqual({ ok: false, issue: 'range' });
  });

  it('rejects equal or inverted thresholds as ordering failures', () => {
    expect(validateThresholds('0.5', '0.5')).toEqual({ ok: false, issue: 'order' });
    expect(validateThresholds('0.5', '0.6')).toEqual({ ok: false, issue: 'order' });
    expect(validateThresholds('0', '0')).toEqual({ ok: false, issue: 'order' });
    expect(validateThresholds('1', '1')).toEqual({ ok: false, issue: 'order' });
  });
});
