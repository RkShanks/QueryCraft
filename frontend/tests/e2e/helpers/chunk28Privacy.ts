import { expect, type Page } from '@playwright/test';
import { assertReactApplicationStateClean } from './chunk28ReactState';

type ExternalPrivacyScan = {
  canaryObserved: boolean;
  redis: { observed: boolean; matchCount: number; scannedKeyCount: number };
  postgres: { observed: boolean; matchCount: number; scannedColumnCount: number };
  backendLogs: { observed: boolean; matchCount: number };
  taskKeyCount: number;
  taskStateCount: number;
};

type ExternalScannerCalibration = {
  positiveControlsDetected: {
    redisString: boolean;
    redisHash: boolean;
    redisList: boolean;
    redisSet: boolean;
    redisSortedSet: boolean;
    redisStream: boolean;
    redisNestedJson: boolean;
    redisBase64: boolean;
    postgresText: boolean;
    postgresNestedJson: boolean;
    postgresBase64: boolean;
    backendLogs: boolean;
  };
  positiveControlsRemoved: boolean;
  preflightClean: boolean;
};

type RuntimeMemoryScan = {
  instrumented: boolean;
  queryClientCount: number;
  zustandStoreCount: number;
  tanstackQueryCaches: boolean;
  zustandApplicationState: boolean;
  applicationState: boolean;
};

export async function getRuntimeCanary(controlUrl: string): Promise<string> {
  const response = await fetch(`${controlUrl}/canary`);
  expect(response.status, 'canary control status').toBe(200);
  const body = await response.json() as { canary: string };
  expect(typeof body.canary, 'canary control shape').toBe('string');
  expect(body.canary.length, 'canary control length').toBeGreaterThan(20);
  return body.canary;
}

export async function assertExternalScannerCalibrated(controlUrl: string): Promise<void> {
  const response = await fetch(`${controlUrl}/calibration`);
  expect(response.status, 'external scanner calibration status').toBe(200);
  const calibration = await response.json() as ExternalScannerCalibration;
  expect(
    Object.values(calibration.positiveControlsDetected).every(Boolean),
    'every external scanner positive control was detected',
  ).toBe(true);
  expect(calibration.positiveControlsRemoved, 'external scanner positive controls were removed').toBe(true);
  expect(calibration.preflightClean, 'external scanner preflight was clean').toBe(true);
}

export async function assertExternalPrivacyClean(
  controlUrl: string,
  boundary: string,
): Promise<ExternalPrivacyScan> {
  const response = await fetch(`${controlUrl}/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ boundary }),
  });
  expect(response.status, `${boundary}: external scan status`).toBe(200);
  const scan = await response.json() as ExternalPrivacyScan;
  expect(scan.canaryObserved, `${boundary}: external channel contains sensitive value`).toBe(false);
  expect(scan.redis.observed, `${boundary}: Redis contains sensitive value`).toBe(false);
  expect(scan.postgres.observed, `${boundary}: PostgreSQL contains sensitive value`).toBe(false);
  expect(scan.backendLogs.observed, `${boundary}: backend logs contain sensitive value`).toBe(false);
  return scan;
}

export async function inspectRuntimeMemory(page: Page, canary: string): Promise<RuntimeMemoryScan> {
  return page.evaluate(async (needle) => {
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
      for (const field of ['child', 'sibling', 'alternate']) {
        const next = fiber[field];
        if (next && typeof next === 'object') pending.push(next as Record<string, unknown>);
      }
    }

    const queryClients = new Set<{
      getQueryCache: () => { getAll: () => unknown[] };
      getMutationCache: () => { getAll: () => unknown[] };
    }>();
    for (const fiber of fibers) {
      const props = fiber.memoizedProps as Record<string, unknown> | undefined;
      const client = props?.client as {
        getQueryCache?: () => { getAll: () => unknown[] };
        getMutationCache?: () => { getAll: () => unknown[] };
      } | undefined;
      if (client?.getQueryCache && client.getMutationCache) {
        queryClients.add(client as {
          getQueryCache: () => { getAll: () => unknown[] };
          getMutationCache: () => { getAll: () => unknown[] };
        });
      }
    }

    // @ts-expect-error Vite resolves this browser-runtime URL; tsc cannot resolve it from the test project.
    const importedStore = await import(/* @vite-ignore */ '/src/stores/uiStore.ts') as {
      useUIStore?: { getState?: () => unknown };
    };
    const zustandStores = importedStore.useUIStore?.getState ? [importedStore.useUIStore] : [];
    const tanstackQueryCaches = [...queryClients].some((client) =>
      contains(client.getQueryCache().getAll()) || contains(client.getMutationCache().getAll()),
    );
    const zustandApplicationState = zustandStores.some((store) => contains(store.getState?.()));
    const applicationState = fibers.some((fiber) =>
      contains(fiber.memoizedProps) || contains(fiber.memoizedState),
    );
    return {
      instrumented: Boolean(firstFiber),
      queryClientCount: queryClients.size,
      zustandStoreCount: zustandStores.length,
      tanstackQueryCaches,
      zustandApplicationState,
      applicationState,
    };
  }, canary);
}

export async function assertRuntimeMemoryClean(
  page: Page,
  canary: string,
  boundary: string,
): Promise<void> {
  const memory = await inspectRuntimeMemory(page, canary);
  expect(memory.instrumented, `${boundary}: React runtime was not inspectable`).toBe(true);
  expect(memory.queryClientCount, `${boundary}: TanStack clients were not inspectable`).toBeGreaterThan(0);
  expect(memory.zustandStoreCount, `${boundary}: Zustand stores were not inspectable`).toBeGreaterThan(0);
  expect(memory.tanstackQueryCaches, `${boundary}: TanStack cache contains sensitive value`).toBe(false);
  expect(memory.zustandApplicationState, `${boundary}: Zustand state contains sensitive value`).toBe(false);
  expect(memory.applicationState, `${boundary}: application state contains sensitive value`).toBe(false);
  await assertReactApplicationStateClean(page, canary, boundary);
}

export async function recordBrowserSummary(
  controlUrl: string,
  record: {
    category: string;
    apiResponseCount: number;
    apiStatusCounts: Record<string, number>;
    pageErrorCount: number;
    consoleErrorCount: number;
  },
): Promise<void> {
  const response = await fetch(`${controlUrl}/browser-record`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      category: record.category,
      api_response_count: record.apiResponseCount,
      api_status_counts: record.apiStatusCounts,
      page_error_count: record.pageErrorCount,
      console_error_count: record.consoleErrorCount,
    }),
  });
  expect(response.status, `${record.category}: browser summary status`).toBe(200);
}
