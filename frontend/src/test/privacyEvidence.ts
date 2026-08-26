/** Return only whether a value contains the in-memory canary. */
export function containsSensitiveCanary(value: unknown, canary: string): boolean {
  if (typeof value === 'string') return value.includes(canary);
  if (Array.isArray(value)) return value.some((entry) => containsSensitiveCanary(entry, canary));
  if (value && typeof value === 'object') {
    return Object.values(value as Record<string, unknown>).some((entry) =>
      containsSensitiveCanary(entry, canary)
    );
  }
  return false;
}
