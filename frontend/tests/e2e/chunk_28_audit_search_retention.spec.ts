import { expect, test, type Download, type Page, type Request, type Response } from '@playwright/test';
import { readFile, rm } from 'node:fs/promises';
import {
  assertExternalPrivacyClean,
  assertExternalScannerCalibrated,
  assertRuntimeMemoryClean,
  getRuntimeCanary,
  recordBrowserSummary,
} from './helpers/chunk28Privacy';

/** CHUNK-28 audit-search retention privacy proof. */

test.use({ screenshot: 'off', trace: 'off', video: 'off' });

interface PrivacyObserver {
  canaryObserved: boolean;
  apiResponseCount: number;
  apiStatusCounts: Record<string, number>;
  responseInspectionFailureCount: number;
  responseInspectionFailureStatuses: Record<string, number>;
  unexpectedConsoleErrors: number;
  pageErrors: number;
  pendingBodyChecks: Array<Promise<void>>;
}

function observePrivacyBoundary(page: Page, canary: string): PrivacyObserver {
  const observer: PrivacyObserver = {
    canaryObserved: false,
    apiResponseCount: 0,
    apiStatusCounts: {},
    responseInspectionFailureCount: 0,
    responseInspectionFailureStatuses: {},
    unexpectedConsoleErrors: 0,
    pageErrors: 0,
    pendingBodyChecks: [],
  };
  page.on('response', (response) => {
    if (!response.url().includes('/api/v1/')) return;
    observer.apiResponseCount += 1;
    const status = String(response.status());
    observer.apiStatusCounts[status] = (observer.apiStatusCounts[status] ?? 0) + 1;
    if (response.request().method() === 'HEAD' || [204, 205, 304].includes(response.status())) return;
    observer.pendingBodyChecks.push(
      response.body().then((body) => {
        if (new TextDecoder().decode(body).includes(canary)) observer.canaryObserved = true;
      }).catch(() => {
        const pathname = new URL(response.url()).pathname;
        if (pathname.startsWith('/api/v1/auth/')) {
          const key = 'classified-auth-body-unavailable';
          observer.apiStatusCounts[key] = (observer.apiStatusCounts[key] ?? 0) + 1;
          return;
        }
        observer.responseInspectionFailureCount += 1;
        observer.responseInspectionFailureStatuses[status] =
          (observer.responseInspectionFailureStatuses[status] ?? 0) + 1;
      }),
    );
  });
  page.on('request', (request) => {
    if (request.url().includes(canary)) observer.canaryObserved = true;
  });
  page.on('console', (message) => {
    const messageText = message.text();
    if (messageText.includes(canary)) observer.canaryObserved = true;
    if (message.type() === 'error' && !messageText.startsWith('Failed to load resource:')) {
      observer.unexpectedConsoleErrors += 1;
    }
  });
  page.on('pageerror', (error) => {
    observer.pageErrors += 1;
    if (error.message.includes(canary)) observer.canaryObserved = true;
  });
  return observer;
}

async function assertValueSafe(
  page: Page,
  observer: PrivacyObserver,
  canary: string,
  boundary: string,
): Promise<void> {
  await Promise.all(observer.pendingBodyChecks.splice(0));
  const browserSnapshot = await page.evaluate(async (needle) => {
    const attributes = [...document.querySelectorAll('*')].some((element) =>
      [...element.attributes].some((attribute) => attribute.value.includes(needle)),
    );
    const formValues = [...document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement>('input, textarea')]
      .some((element) => element.value.includes(needle));
    const storageContains = (storage: Storage) => {
      for (let index = 0; index < storage.length; index += 1) {
        const key = storage.key(index) ?? '';
        if (key.includes(needle) || (storage.getItem(key) ?? '').includes(needle)) return true;
      }
      return false;
    };
    const cacheContains = async () => {
      if (typeof caches === 'undefined') return false;
      for (const cacheName of await caches.keys()) {
        if (cacheName.includes(needle)) return true;
        const cache = await caches.open(cacheName);
        for (const request of await cache.keys()) {
          if (request.url.includes(needle)) return true;
          const response = await cache.match(request);
          if (response && (await response.clone().text()).includes(needle)) return true;
        }
      }
      return false;
    };
    const indexedDbContains = async () => {
      if (!indexedDB.databases) return false;
      for (const databaseInfo of await indexedDB.databases()) {
        if (!databaseInfo.name) continue;
        const database = await new Promise<IDBDatabase | null>((resolve) => {
          const request = indexedDB.open(databaseInfo.name!);
          request.onsuccess = () => resolve(request.result);
          request.onerror = () => resolve(null);
        });
        if (!database) continue;
        for (const storeName of database.objectStoreNames) {
          const found = await new Promise<boolean>((resolve) => {
            const request = database.transaction(storeName, 'readonly').objectStore(storeName).openCursor();
            request.onsuccess = () => {
              const cursor = request.result;
              if (!cursor) {
                resolve(false);
              } else if ((JSON.stringify(cursor.value) ?? '').includes(needle) || String(cursor.key).includes(needle)) {
                resolve(true);
              } else {
                cursor.continue();
              }
            };
            request.onerror = () => resolve(false);
          });
          if (found) {
            database.close();
            return true;
          }
        }
        database.close();
      }
      return false;
    };
    return {
      text: (document.body.textContent ?? '').includes(needle),
      attributes,
      formValues,
      localStorage: storageContains(localStorage),
      sessionStorage: storageContains(sessionStorage),
      indexedDb: await indexedDbContains(),
      cacheStorage: await cacheContains(),
      cookie: document.cookie.includes(needle),
      history: (JSON.stringify(history.state) ?? '').includes(needle),
      location: location.href.includes(needle),
      resources: performance.getEntriesByType('resource').some((entry) => entry.name.includes(needle)),
      windowName: window.name.includes(needle),
    };
  }, canary);
  const accessibilitySnapshot = await page.locator('body').ariaSnapshot();
  expect(Object.values(browserSnapshot).some(Boolean), `${boundary}: browser surface contains sensitive value`).toBe(false);
  expect(accessibilitySnapshot.includes(canary), `${boundary}: accessibility output contains sensitive value`).toBe(false);
  await assertRuntimeMemoryClean(page, canary, boundary);
  expect(observer.canaryObserved, `${boundary}: API or console contains sensitive value`).toBe(false);
  expect(
    observer.responseInspectionFailureCount,
    `${boundary}: unclassified API bodies were unavailable ${JSON.stringify(observer.responseInspectionFailureStatuses)}`,
  ).toBe(0);
  expect(observer.pageErrors, `${boundary}: page error count`).toBe(0);
  expect(observer.unexpectedConsoleErrors, `${boundary}: console error count`).toBe(0);
}

async function signIn(page: Page, username: string, password: string): Promise<void> {
  await page.goto('/sign-in?lng=en');
  await page.getByLabel(/username/i).fill(username);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole('button', { name: /^sign in$/i }).click();
  await expect(page).not.toHaveURL(/\/sign-in/, { timeout: 15_000 });
}

async function signOut(page: Page): Promise<void> {
  await page.getByRole('button', { name: /^sign out$/i }).click();
  await expect(page).toHaveURL(/\/sign-in/, { timeout: 15_000 });
}

async function submitFilter(page: Page, label: RegExp, filterValue: string) {
  await page.getByLabel(label).fill(filterValue);
  const contextResponse = page.waitForResponse(
    (response) => response.url().includes('/api/v1/admin/audit/filter-context'),
  );
  const searchResponse = page.waitForResponse(
    (response) => response.url().includes('/api/v1/admin/audit/entries'),
  );
  await page.getByRole('button', { name: /^search$/i }).click();
  return { contextResponse: await contextResponse, searchResponse: await searchResponse };
}

async function opaqueContext(response: Response): Promise<string> {
  const body = await response.json() as { filter_context: string };
  return body.filter_context;
}

async function downloadWithRequest(page: Page, format: 'csv' | 'json') {
  const button = page.getByRole('button', { name: new RegExp(`export ${format}`, 'i') });
  const requestPromise = page.waitForRequest(
    (request) => request.url().includes('/api/v1/admin/audit/export'),
  );
  const downloadPromise = page.waitForEvent('download');
  await button.click();
  return { request: await requestPromise, download: await downloadPromise };
}

async function inspectedDownload(
  request: Request,
  download: Download,
  canary: string,
  expectedContext: string,
): Promise<{ recordCount: number | null }> {
  const requestBody = request.postDataJSON() as { filter_context?: string };
  expect(requestBody.filter_context === expectedContext, 'export context matches settled search').toBe(true);
  expect(download.suggestedFilename().includes(canary), 'download filename contains sensitive value').toBe(false);
  const downloadPath = await download.path();
  expect(downloadPath !== null, 'download path exists').toBe(true);
  const payload = await readFile(downloadPath!, 'utf8');
  expect(payload.includes(canary), 'download payload contains sensitive value').toBe(false);
  const recordCount = download.suggestedFilename().endsWith('.json')
    ? Number((JSON.parse(payload) as { metadata: { record_count: number } }).metadata.record_count)
    : Number(payload.match(/^# record_count = (\d+)$/m)?.[1] ?? Number.NaN);
  await rm(downloadPath!, { force: true });
  return { recordCount: Number.isFinite(recordCount) ? recordCount : null };
}

test('keeps audit filters value-safe across search, export, failure, reset, reload, and identity change', async ({ page }) => {
  test.setTimeout(120_000);
  const usernameA = process.env.CHUNK28_USER_A;
  const passwordA = process.env.CHUNK28_PASSWORD_A;
  const usernameB = process.env.CHUNK28_AUDIT_USER_B ?? process.env.CHUNK28_USER_B;
  const passwordB = process.env.CHUNK28_AUDIT_PASSWORD_B ?? process.env.CHUNK28_PASSWORD_B;
  const controlUrl = process.env.CHUNK28_PROVIDER_CONTROL_URL;
  test.skip(
    !usernameA || !passwordA || !usernameB || !passwordB || !controlUrl,
    'Disposable CHUNK-28 credentials are required.',
  );

  await assertExternalScannerCalibrated(controlUrl!);
  const canary = await getRuntimeCanary(controlUrl!);
  await signIn(page, usernameA!, passwordA!);
  await page.goto('/admin/audit?lng=en');
  await expect(page.getByRole('heading', { name: /audit/i }).first()).toBeVisible({ timeout: 15_000 });
  const observer = observePrivacyBoundary(page, canary);

  const canarySearch = await submitFilter(page, /actor/i, canary);
  expect(canarySearch.contextResponse.status(), 'context creation status').toBe(200);
  expect(canarySearch.searchResponse.status(), 'canary search status').toBe(200);
  const canaryContext = await opaqueContext(canarySearch.contextResponse);
  expect(canarySearch.searchResponse.url().includes(canary), 'search URL contains sensitive value').toBe(false);
  expect(canarySearch.searchResponse.url().includes('actor_identity='), 'search URL contains raw actor field').toBe(false);
  await assertValueSafe(page, observer, canary, 'successful canary search');
  await assertExternalPrivacyClean(controlUrl!, 'successful audit search');

  const safeSearch = await submitFilter(page, /action type/i, 'audit.verify');
  expect(safeSearch.searchResponse.status(), 'safe search status').toBe(200);
  const safeContext = await opaqueContext(safeSearch.contextResponse);
  const firstPageBody = await safeSearch.searchResponse.json() as {
    pagination: { total_entries: number; total_pages: number };
  };
  if (firstPageBody.pagination.total_pages > 1) {
    const nextPageResponse = page.waitForResponse(
      (response) => response.url().includes('/api/v1/admin/audit/entries') && response.url().includes('page=2'),
    );
    await page.getByRole('button', { name: /^next$/i }).click();
    const pageTwo = await nextPageResponse;
    expect(new URL(pageTwo.url()).searchParams.get('filter_context') === safeContext, 'pagination context matches').toBe(true);
    const firstPageResponse = page.waitForResponse(
      (response) => response.url().includes('/api/v1/admin/audit/entries') && response.url().includes('page=1'),
    );
    await page.getByRole('button', { name: /^previous$/i }).click();
    expect((await firstPageResponse).status(), 'first page restore status').toBe(200);
  }

  const jsonDownload = await downloadWithRequest(page, 'json');
  const jsonInspection = await inspectedDownload(jsonDownload.request, jsonDownload.download, canary, safeContext);
  expect(jsonInspection.recordCount, 'JSON export count').toBe(firstPageBody.pagination.total_entries);
  const csvDownload = await downloadWithRequest(page, 'csv');
  const csvInspection = await inspectedDownload(csvDownload.request, csvDownload.download, canary, safeContext);
  expect(csvInspection.recordCount, 'CSV export count').toBe(firstPageBody.pagination.total_entries);
  await assertValueSafe(page, observer, canary, 'pagination and exports');
  await assertExternalPrivacyClean(controlUrl!, 'audit pagination and exports');

  let failNextSearch = true;
  await page.route('**/api/v1/admin/audit/entries?**', async (route) => {
    const requestContext = new URL(route.request().url()).searchParams.get('filter_context');
    if (requestContext === safeContext) {
      await route.continue();
      return;
    }
    if (!failNextSearch) {
      await route.continue();
      return;
    }
    failNextSearch = false;
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'internal', message_key: 'error.internal' }),
    });
  });
  const failedSearch = await submitFilter(page, /actor/i, canary);
  expect(failedSearch.searchResponse.status(), 'failed search status').toBe(500);
  const priorExport = await downloadWithRequest(page, 'json');
  await inspectedDownload(priorExport.request, priorExport.download, canary, safeContext);
  await page.unroute('**/api/v1/admin/audit/entries?**');
  const retriedSearch = await submitFilter(page, /actor/i, canary);
  expect(retriedSearch.contextResponse.status(), 'retry context status').toBe(200);
  expect(retriedSearch.searchResponse.status(), 'retry search status').toBe(200);
  await assertValueSafe(page, observer, canary, 'failed search and retry');
  await assertExternalPrivacyClean(controlUrl!, 'audit failure and retry');

  const resetResponse = page.waitForResponse((response) => response.url().includes('/api/v1/admin/audit/entries'));
  await page.getByRole('button', { name: /^reset$/i }).click();
  const resetSearch = await resetResponse;
  expect(new URL(resetSearch.url()).searchParams.has('filter_context'), 'reset retains context').toBe(false);
  await expect(page.getByTestId('audit-applied-filters')).toContainText(/all entries/i);
  await page.reload();
  await expect(page.getByRole('heading', { name: /audit/i }).first()).toBeVisible({ timeout: 15_000 });
  await assertValueSafe(page, observer, canary, 'reset and reload');
  await assertExternalPrivacyClean(controlUrl!, 'audit reset and reload');

  for (const width of [1440, 768, 375]) {
    await page.setViewportSize({ width, height: 900 });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
    expect(overflow, `viewport ${width}: horizontal overflow`).toBe(false);
  }
  await page.goto('/admin/audit?lng=ar');
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  const rtlOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  expect(rtlOverflow, 'Arabic viewport horizontal overflow').toBe(false);
  await assertValueSafe(page, observer, canary, 'responsive English and Arabic');

  await page.goto('/admin/audit?lng=en');
  await signOut(page);
  await signIn(page, usernameB!, passwordB!);
  await page.goto('/admin/audit?lng=en');
  await expect(page.getByRole('heading', { name: /audit/i }).first()).toBeVisible({ timeout: 15_000 });
  const reuseStatus = await page.evaluate(async (filterContext) => {
    const response = await fetch(`/api/v1/admin/audit/entries?filter_context=${encodeURIComponent(filterContext)}`);
    return response.status;
  }, canaryContext);
  expect(reuseStatus, 'prior identity context reuse status').toBe(422);
  await assertValueSafe(page, observer, canary, 'identity replacement');
  await signOut(page);
  await assertValueSafe(page, observer, canary, 'audit final sign-out');
  await assertExternalPrivacyClean(controlUrl!, 'audit identity replacement and sign-out');
  await recordBrowserSummary(controlUrl!, {
    category: 'audit lifecycle',
    apiResponseCount: observer.apiResponseCount,
    apiStatusCounts: observer.apiStatusCounts,
    pageErrorCount: observer.pageErrors,
    consoleErrorCount: observer.unexpectedConsoleErrors,
  });
});
