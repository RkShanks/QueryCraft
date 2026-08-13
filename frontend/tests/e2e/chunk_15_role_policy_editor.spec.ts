import { expect, test, type Page, type Route } from '@playwright/test';

const CONNECTION_ID = 'a1111111-1111-4111-8111-111111111111';
const ROLE_A_ID = 'a2222222-2222-4222-8222-222222222222';
const ROLE_B_ID = 'a3333333-3333-4333-8333-333333333333';

const connectionPolicy = {
  id: 'a4444444-4444-4444-8444-444444444444',
  connection_id: CONNECTION_ID,
  allowed_tables: [{ table: 'users', columns: ['id', 'name', 'email', 'status'] }],
  row_filters: [{ table: 'users', filter: "status = 'persisted'" }],
  column_masks: [{ table: 'users', columns: ['email'] }],
};

const roleA = {
  id: ROLE_A_ID,
  name: 'Disposable Analyst A',
  description: 'Original persisted description A',
  priority: 20,
  permissions: ['query.submit'],
  is_builtin: false,
  group_mappings: [],
  connection_policy_count: 1,
  connection_policies: [connectionPolicy],
  created_at: '2026-08-13T00:00:00Z',
  updated_at: '2026-08-13T00:00:00Z',
};

const roleB = {
  ...roleA,
  id: ROLE_B_ID,
  name: 'Disposable Analyst B',
  description: 'Original persisted description B',
};

interface Deferred {
  promise: Promise<void>;
  resolve: () => void;
}

interface BrowserState {
  consoleErrors: string[];
  createBodies: unknown[];
  detailDelivered: string[];
  detailGates: Map<string, Deferred>;
  failedDetailIds: Set<string>;
  previewBodies: Array<Record<string, unknown>>;
  requestFailures: string[];
  unexpectedApiRequests: string[];
  updateBodies: unknown[];
}

function deferred(): Deferred {
  let resolve = () => undefined;
  const promise = new Promise<void>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function initialState(): BrowserState {
  return {
    consoleErrors: [],
    createBodies: [],
    detailDelivered: [],
    detailGates: new Map(),
    failedDetailIds: new Set(),
    previewBodies: [],
    requestFailures: [],
    unexpectedApiRequests: [],
    updateBodies: [],
  };
}

const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });

async function installBackend(page: Page, state: BrowserState) {
  page.on('console', (message) => {
    if (message.type() === 'error') state.consoleErrors.push(message.text());
  });
  page.on('requestfailed', (request) => {
    state.requestFailures.push(
      `${new URL(request.url()).pathname}: ${request.failure()?.errorText ?? 'unknown'}`
    );
  });
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace('/api/v1', '');
    const method = request.method();

    if (path === '/auth/me') {
      await json(route, {
        id: 'chunk-15-admin',
        username: 'chunk-15-admin',
        display_name: 'CHUNK-15 Administrator',
        role: 'custom',
        role_id: 'chunk-15-admin-role',
        role_name: 'Administrator',
        permissions: ['admin.roles.manage', 'admin.connections.manage', 'query.submit'],
        auth_provider: 'local',
      });
      return;
    }
    if (path === '/auth/sso/providers') {
      await json(route, { providers: [] });
      return;
    }
    if (path === '/connections') {
      await json(route, { connections: [] });
      return;
    }
    if (path === '/sessions') {
      await json(route, { items: [], total: 0, next_cursor: null });
      return;
    }
    if (path === '/admin/sso/group-mappings') {
      await json(route, { mappings: [] });
      return;
    }
    if (path === '/admin/connections' && method === 'GET') {
      await json(route, [
          {
            id: CONNECTION_ID,
            display_name: 'Disposable PostgreSQL',
            database_type: 'postgresql',
            database_name: 'disposable',
            port: 5432,
            ssl_mode: 'require',
            lifecycle_state: 'enabled',
            health_status: 'healthy',
            schema_introspection_status: 'success',
            last_health_check_at: null,
            health_error_category: null,
            schema_last_refreshed_at: '2026-08-13T00:00:00Z',
            created_at: '2026-08-13T00:00:00Z',
            updated_at: '2026-08-13T00:00:00Z',
          },
        ]);
      return;
    }
    if (path === `/admin/connections/${CONNECTION_ID}/schema`) {
      await json(route, {
        connection_id: CONNECTION_ID,
        tables: [
          {
            table_name: 'users',
            column_count: 4,
            columns: ['id', 'name', 'email', 'status'].map((column_name) => ({
              column_name,
              data_type: 'text',
              is_primary_key: column_name === 'id',
              foreign_key: null,
            })),
          },
          {
            table_name: 'audit_log',
            column_count: 1,
            columns: [
              {
                column_name: 'id',
                data_type: 'text',
                is_primary_key: true,
                foreign_key: null,
              },
            ],
          },
        ],
        introspected_at: '2026-08-13T00:00:00Z',
      });
      return;
    }
    if (path === '/admin/roles/test-policy' && method === 'POST') {
      const body = request.postDataJSON() as Record<string, unknown>;
      state.previewBodies.push(body);
      const policy = body.connection_policy as typeof connectionPolicy;
      const invalid = policy.row_filters.some(({ filter }) => filter.includes('LOWER('));
      if (invalid) {
        await json(
          route,
          { error: 'filter_validation_failed', message_key: 'error.filterValidationFailed' },
          422
        );
        return;
      }
      const blocked = String(body.sample_sql ?? '').includes('audit_log');
      await json(route, {
        accessible_tables: policy.allowed_tables.map(({ table }) => table),
        accessible_columns: Object.fromEntries(
          policy.allowed_tables.map(({ table, columns }) => [table, columns])
        ),
        blocked_tables: ['audit_log'],
        applicable_row_filters: policy.row_filters,
        masked_columns: Object.fromEntries(
          policy.column_masks.map(({ table, columns }) => [table, columns])
        ),
        would_be_allowed: !blocked,
        message_key: blocked ? 'error.queryBlockedPolicy' : null,
      });
      return;
    }
    if (path === '/admin/roles' && method === 'GET') {
      const summaries = [roleA, roleB].map((role) => ({
        id: role.id,
        name: role.name,
        description: role.description,
        priority: role.priority,
        permissions: role.permissions,
        is_builtin: role.is_builtin,
        group_mappings: role.group_mappings,
        connection_policy_count: role.connection_policy_count,
        created_at: role.created_at,
        updated_at: role.updated_at,
      }));
      await json(route, { roles: summaries });
      return;
    }
    if (path === '/admin/roles' && method === 'POST') {
      state.createBodies.push(request.postDataJSON());
      await json(route, { ...roleA, ...request.postDataJSON(), id: 'created-role' }, 201);
      return;
    }
    const detail = path === `/admin/roles/${ROLE_A_ID}` ? roleA : path === `/admin/roles/${ROLE_B_ID}` ? roleB : null;
    if (detail && method === 'GET') {
      const gate = state.detailGates.get(detail.id);
      if (gate) await gate.promise;
      if (state.failedDetailIds.has(detail.id)) {
        await json(route, { error: 'internal', message_key: 'error.internal' }, 500);
        return;
      }
      state.detailDelivered.push(detail.id);
      await json(route, detail);
      return;
    }
    if (detail && method === 'PUT') {
      state.updateBodies.push(request.postDataJSON());
      await json(route, { ...detail, ...request.postDataJSON() });
      return;
    }

    state.unexpectedApiRequests.push(`${method} ${path}`);
    await json(route, { error: 'not_found', message_key: 'error.notFound' }, 404);
  });
}

async function expectNoViewportOverflow(page: Page) {
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth
      )
    )
    .toBeLessThanOrEqual(0);
}

async function openNewPolicy(page: Page, locale: 'en' | 'ar') {
  await page.getByRole('button', { name: locale === 'ar' ? 'إضافة دور' : 'Add Role' }).click();
  await page
    .getByRole('button', { name: locale === 'ar' ? 'إضافة سياسة اتصال' : 'Add Connection Policy' })
    .click();
  await page.locator('#policyConnection').selectOption(CONNECTION_ID);
  await page.getByTestId('table-checkbox-users').check();
}

async function enterFilter(page: Page, locale: 'en' | 'ar', filter: string) {
  const addFilterName = locale === 'ar' ? 'إضافة عامل تصفية صف' : 'Add Row Filter';
  if ((await page.getByRole('button', { name: addFilterName }).count()) > 0) {
    await page.getByRole('button', { name: addFilterName }).click();
  }
  const filterSelect = page.locator('select').filter({ has: page.locator('option[value="users"]') }).last();
  await filterSelect.selectOption('users');
  const filterInput = page.locator('input[placeholder*="department_id"]');
  await filterInput.fill(filter);
  return filterInput;
}

async function submitPreview(page: Page, locale: 'en' | 'ar', sampleSql: string) {
  await page
    .getByLabel(locale === 'ar' ? 'سؤال تجريبي' : 'Sample question')
    .fill(locale === 'ar' ? 'اعرض المستخدمين' : 'Show draft users');
  await page
    .getByLabel(locale === 'ar' ? 'SQL تجريبي اختياري' : 'Optional sample SQL')
    .fill(sampleSql);
  await page
    .getByRole('button', { name: locale === 'ar' ? 'اختبار مسودة السياسة' : 'Test draft policy' })
    .click();
}

test('blocks delayed/failed hydration and ignores a late role-A detail', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const state = initialState();
  const roleAGate = deferred();
  state.detailGates.set(ROLE_A_ID, roleAGate);
  await installBackend(page, state);
  await page.goto('/admin/roles?lng=en');

  await page.getByTestId(`edit-role-${ROLE_A_ID}`).click();
  await expect(page.getByText('Loading the complete role policy...')).toBeVisible();
  const save = page.getByRole('button', { name: 'Save' });
  await expect(save).toBeDisabled();
  await page.keyboard.press('Enter');
  await page.keyboard.press('Enter');
  expect(state.updateBodies).toEqual([]);

  await page.getByRole('button', { name: 'Cancel' }).click();
  await page.getByTestId(`edit-role-${ROLE_B_ID}`).click();
  await expect(page.getByLabel('Name')).toHaveValue(roleB.name);
  roleAGate.resolve();
  await expect.poll(() => state.detailDelivered).toContain(ROLE_A_ID);
  await expect(page.getByLabel('Name')).toHaveValue(roleB.name);
  expect(state.updateBodies).toEqual([]);

  await page.getByRole('button', { name: 'Cancel' }).click();
  state.failedDetailIds.add(ROLE_A_ID);
  state.detailGates.delete(ROLE_A_ID);
  await page.reload();
  await page.getByTestId(`edit-role-${ROLE_A_ID}`).click();
  await expect(page.getByRole('alert')).toContainText(
    'The complete role policy could not be loaded. Retry or cancel without saving.'
  );
  await expect(page.getByRole('button', { name: 'Save' })).toBeDisabled();
  expect(state.updateBodies).toEqual([]);
  expect(state.consoleErrors.length).toBeGreaterThan(0);
  expect(
    state.consoleErrors.every((message) =>
      message.includes('the server responded with a status of 500')
    )
  ).toBe(true);
  state.consoleErrors.length = 0;

  state.failedDetailIds.delete(ROLE_A_ID);
  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByLabel('Name')).toHaveValue(roleA.name);
  await expect(page.getByText('Row Filters:')).toBeVisible();
  await expectNoViewportOverflow(page);
  expect(state.unexpectedApiRequests).toEqual([]);
  expect(state.consoleErrors).toEqual([]);
  expect(state.requestFailures).toEqual([]);
});

test('previews new/edit unsaved policies without persistence or execution', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const state = initialState();
  const forbiddenExecutionRequests: string[] = [];
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname;
    if (
      path.startsWith('/api/v1/') &&
      /\/(query|llm|generate|execute)(\/|$)/.test(path)
    ) {
      forbiddenExecutionRequests.push(path);
    }
  });
  await installBackend(page, state);
  await page.goto('/admin/roles?lng=en');

  await openNewPolicy(page, 'en');
  const filterInput = await enterFilter(page, 'en', `"name" = 'from union --'`);
  await submitPreview(page, 'en', 'SELECT id, name FROM users');
  await expect(page.getByTestId('policy-preview-status')).toHaveAttribute('data-state', 'allowed');
  expect(state.previewBodies.at(-1)).toMatchObject({
    question: 'Show draft users',
    sample_sql: 'SELECT id, name FROM users',
    connection_policy: {
      connection_id: CONNECTION_ID,
      row_filters: [{ table: 'users', filter: `"name" = 'from union --'` }],
    },
  });
  expect(state.createBodies).toEqual([]);
  expect(state.updateBodies).toEqual([]);

  await filterInput.fill("status = 'changed'");
  await expect(page.getByTestId('policy-preview-status')).toHaveAttribute('data-state', 'stale');
  await filterInput.fill("LOWER(name) = 'admin'");
  await page.getByRole('button', { name: 'Test draft policy' }).click();
  await expect(page.getByTestId('policy-preview-status')).toHaveAttribute('data-state', 'invalid');
  await expect(page.getByText('The draft policy is invalid.')).toBeVisible();
  expect(state.consoleErrors).toEqual([
    'Failed to load resource: the server responded with a status of 422 (Unprocessable Entity)',
  ]);
  state.consoleErrors.length = 0;

  await filterInput.fill("status = 'active'");
  await page.getByLabel('Optional sample SQL').fill('SELECT id FROM audit_log');
  await page.getByRole('button', { name: 'Test draft policy' }).click();
  await expect(page.getByTestId('policy-preview-status')).toHaveAttribute('data-state', 'blocked');
  await expect(page.getByText('No AI model or source query is run.')).toBeVisible();

  await page.getByRole('button', { name: 'Cancel' }).first().click();
  await page.getByRole('button', { name: 'Add Connection Policy' }).click();
  await page.locator('#policyConnection').selectOption(CONNECTION_ID);
  await page.getByTestId('table-checkbox-users').check();
  await expect(page.getByTestId('policy-preview-status')).toHaveAttribute('data-state', 'empty');
  await expect(page.getByLabel('Sample question')).toHaveValue('');
  await page.getByRole('button', { name: 'Cancel' }).first().click();
  await page.getByRole('button', { name: 'Cancel' }).click();
  expect(state.createBodies).toEqual([]);

  await page.getByTestId(`edit-role-${ROLE_A_ID}`).click();
  await expect(page.getByLabel('Description')).toHaveValue(roleA.description);
  await page.getByLabel('Description').fill('Dirty unsaved role description');
  await page.getByTestId('policy-editor').getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(page.locator('input[placeholder*="department_id"]')).toHaveValue(
    "status = 'persisted'"
  );
  await submitPreview(page, 'en', 'SELECT id FROM users');
  await expect(page.getByTestId('policy-preview-status')).toHaveAttribute('data-state', 'allowed');
  expect(state.updateBodies).toEqual([]);
  await page.getByRole('button', { name: 'Save' }).first().click();
  expect(state.updateBodies).toEqual([]);
  await page.getByRole('button', { name: 'Cancel' }).click();
  await page.getByTestId(`edit-role-${ROLE_A_ID}`).click();
  await expect(page.getByLabel('Description')).toHaveValue(roleA.description);
  await expect(page.getByText('Row Filters:')).toBeVisible();

  expect(forbiddenExecutionRequests).toEqual([]);
  expect(state.unexpectedApiRequests).toEqual([]);
  expect(state.consoleErrors).toEqual([]);
  expect(state.requestFailures).toEqual([]);
  await page.screenshot({ path: '/tmp/querycraft-chunk15-1440-en.png', fullPage: true });
});

for (const scenario of [
  { locale: 'ar' as const, width: 768, height: 1024 },
  { locale: 'en' as const, width: 375, height: 812 },
]) {
  test(`keeps ${scenario.locale} preview usable at ${scenario.width}px`, async ({ page }) => {
    await page.setViewportSize(scenario);
    const state = initialState();
    await installBackend(page, state);
    await page.goto(`/admin/roles?lng=${scenario.locale}`);
    await expect(page.locator('html')).toHaveAttribute(
      'dir',
      scenario.locale === 'ar' ? 'rtl' : 'ltr'
    );
    await openNewPolicy(page, scenario.locale);
    await enterFilter(page, scenario.locale, `"name" = 'from union --'`);
    await submitPreview(page, scenario.locale, 'SELECT id FROM users');
    await expect(page.getByTestId('policy-preview-status')).toHaveAttribute('data-state', 'allowed');
    await expect(
      page.getByLabel(
        scenario.locale === 'ar' ? 'SQL تجريبي اختياري' : 'Optional sample SQL'
      )
    ).toHaveAttribute('dir', 'ltr');
    await expectNoViewportOverflow(page);
    expect(state.createBodies).toEqual([]);
    expect(state.updateBodies).toEqual([]);
    expect(state.unexpectedApiRequests).toEqual([]);
    expect(state.consoleErrors).toEqual([]);
    expect(state.requestFailures).toEqual([]);
    await page.screenshot({
      path: `/tmp/querycraft-chunk15-${scenario.width}-${scenario.locale}.png`,
      fullPage: true,
    });
  });
}
