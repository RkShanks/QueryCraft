const DECIMAL_PATTERN =
  /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;

export type ThresholdIssue = 'invalid' | 'range' | 'order';

export type ThresholdValidation =
  | { ok: true; block: number; flag: number }
  | { ok: false; issue: ThresholdIssue };

export function parseThresholdValue(raw: string): number | null {
  const trimmed = raw.trim();
  if (!DECIMAL_PATTERN.test(trimmed)) return null;
  const value = Number(trimmed);
  return Number.isFinite(value) ? value : null;
}

export function validateThresholds(
  blockRaw: string,
  flagRaw: string
): ThresholdValidation {
  const block = parseThresholdValue(blockRaw);
  const flag = parseThresholdValue(flagRaw);
  if (block === null || flag === null) return { ok: false, issue: 'invalid' };
  if (block < 0 || block > 1 || flag < 0 || flag > 1) {
    return { ok: false, issue: 'range' };
  }
  if (block <= flag) return { ok: false, issue: 'order' };
  return { ok: true, block, flag };
}
