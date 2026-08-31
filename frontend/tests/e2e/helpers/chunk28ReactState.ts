import { expect, type Page } from '@playwright/test';

type ReactStateScan = {
  instrumented: boolean;
  applicationState: boolean;
};

async function scanReactApplicationState(page: Page, canary: string): Promise<ReactStateScan> {
  return page.evaluate((needle) => {
    const root = document.getElementById('root');
    const reactKey = root
      ? Object.keys(root).find((key) => key.startsWith('__reactContainer$') || key.startsWith('__reactFiber$'))
      : undefined;
    const firstFiber = reactKey
      ? (root as unknown as Record<string, unknown>)[reactKey]
      : undefined;
    const seen = new WeakSet<object>();
    let visitedObjectCount = 0;

    const contains = (candidate: unknown): boolean => {
      if (typeof candidate === 'string') return candidate.includes(needle);
      if (!candidate || typeof candidate !== 'object' || seen.has(candidate)) return false;
      if (typeof Node !== 'undefined' && candidate instanceof Node) return false;
      seen.add(candidate);
      visitedObjectCount += 1;
      if (visitedObjectCount > 100_000) return false;
      if (Array.isArray(candidate)) return candidate.some(contains);
      return Object.entries(candidate as Record<string, unknown>).some(([key, value]) => {
        if (key === 'stateNode') return false;
        return contains(value);
      });
    };

    const fibers: Array<Record<string, unknown>> = [];
    const pending = firstFiber && typeof firstFiber === 'object'
      ? [firstFiber as Record<string, unknown>]
      : [];
    const visitedFibers = new WeakSet<object>();
    while (pending.length > 0) {
      const fiber = pending.pop()!;
      if (visitedFibers.has(fiber)) continue;
      visitedFibers.add(fiber);
      fibers.push(fiber);
      for (const field of ['child', 'sibling']) {
        const next = fiber[field];
        if (next && typeof next === 'object') pending.push(next as Record<string, unknown>);
      }
    }

    return {
      instrumented: Boolean(firstFiber),
      applicationState: fibers.some((fiber) => contains(fiber.memoizedProps) || contains(fiber.memoizedState)),
    };
  }, canary);
}

export async function assertReactApplicationStateClean(
  page: Page,
  canary: string,
  boundary: string,
): Promise<void> {
  const scan = await scanReactApplicationState(page, canary);
  expect(scan.instrumented, `${boundary}: React runtime was not inspectable`).toBe(true);
  expect(scan.applicationState, `${boundary}: React application state contains sensitive value`).toBe(false);
}
