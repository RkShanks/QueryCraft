import { expect, test, type Page, type Route } from '@playwright/test';

const ROLE_ID = 'b1111111-1111-4111-8111-111111111111';
const CREATED_ROLE_ID = 'b2222222-2222-4222-8222-222222222222';

interface Mapping {
  id: string;
  sso_group_value: string;
}

interface BrowserRole {
  id: string;
  name: string;
  description: string | null;
  priority: number;
  permissions: string[];
  is_builtin: false;
  group_mappings: Mapping[];
  connection_policy_count: number;
  connection_policies: unknown[];
  created_at: string;
  updated_at: string;
}

type WriteOutcome = 'success' | 'conflict' | 'abort-committed' | 'abort-uncommitted';

interface Deferred {
  promise: Promise<void>;
  resolve: () => void;
}

interface RoleWrite {
  body: Record<string, unknown>;
  method: 'POST' | 'PUT';
  outcome: WriteOutcome;
}

interface BrowserState {
  consoleErrors: string[];
  mappingCounter: number;
  nextWriteOutcome: WriteOutcome;
  requestFailures: string[];
  roleWrites: RoleWrite[];
  roles: Map<string, BrowserRole>;
  standaloneMappingWrites: string[];
  unexpectedApiRequests: string[];
  writeGate?: Deferred;
}

const initialRole = (): BrowserRole => ({
  id: ROLE_ID,
  name: 'Disposable Analyst',
  description: 'Authoritative role state',
  priority: 20,
  permissions: ['query.submit'],
  is_builtin: false,
  group_mappings: [
    { id: 'mapping-existing-a', sso_group_value: 'chunk16-existing-a' },
    { id: 'mapping-existing-b', sso_group_value: 'chunk16-existing-b' },
  ],
  connection_policy_count: 0,
  connection_policies: [],
  created_at: '2026-08-14T00:00:00Z',
  updated_at: '2026-08-14T00:00:00Z',
});

function initialState(includeRole = true): BrowserState {
  const roles = new Map<string, BrowserRole>();
  if (includeRole) roles.set(ROLE_ID, initialRole());
  return {
    consoleErrors: [],
    mappingCounter: 0,
    nextWriteOutcome: 'success',
    requestFailures: [],
    roleWrites: [],
    roles,
    standaloneMappingWrites: [],
    unexpectedApiRequests: [],
  };
}

function deferred(): Deferred {
  let resolve: () => void = () => undefined;
  const promise = new Promise<void>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });

function roleSummary(role: BrowserRole) {
  return {
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
  };
}

function applyRoleBody(
  state: BrowserState,
  body: Record<string, unknown>,
  existing?: BrowserRole
): BrowserRole {
  const groupValues = (body.group_mappings as string[] | undefined) ??
    existing?.group_mappings.map((mapping) => mapping.sso_group_value) ?? [];
  const existingMappings = new Map(
    existing?.group_mappings.map((mapping) => [mapping.sso_group_value, mapping]) ?? []
  );
  const groupMappings = groupValues.map((sso_group_value) => {
    const unchanged = existingMappings.get(sso_group_value);
    if (unchanged) return unchanged;
    state.mappingCounter += 1;
    return { id: `mapping-created-${state.mappingCounter}`, sso_group_value };
  });
  const now = '2026-08-14T01:00:00Z';
  return {
    id: existing?.id ?? CREATED_ROLE_ID,
    name: (body.name as string | undefined) ?? existing?.name ?? '',
    description:
      Object.hasOwn(body, 'description')
        ? (body.description as string | null | undefined) ?? null
        : existing?.description ?? null,
    priority: (body.priority as number | undefined) ?? existing?.priority ?? 0,
    permissions: (body.permissions as string[] | undefined) ?? existing?.permissions ?? [],
    is_builtin: false,
    group_mappings: groupMappings,
    connection_policy_count:
      (body.connection_policies as unknown[] | undefined)?.length ??
      existing?.connection_policy_count ??
      0,
    connection_policies:
      (body.connection_policies as unknown[] | undefined) ?? existing?.connection_policies ?? [],
    created_at: existing?.created_at ?? now,
    updated_at: now,
  };
}

async function handleRoleWrite(
  route: Route,
  state: BrowserState,
  method: 'POST' | 'PUT',
  roleId?: string
) {
  const body = route.request().postDataJSON() as Record<string, unknown>;
  const outcome = state.nextWriteOutcome;
  state.nextWriteOutcome = 'success';
  state.roleWrites.push({ body, method, outcome });
  if (state.writeGate) await state.writeGate.promise;

  if (outcome === 'conflict') {
    await json(
      route,
      { error: 'conflict', message_key: 'error.conflict.duplicateGroupMapping' },
      409
    );
    return;
  }

  const existing = roleId ? state.roles.get(roleId) : undefined;
  const persisted = applyRoleBody(state, body, existing);
  if (outcome === 'success' || outcome === 'abort-committed') {
    state.roles.set(persisted.id, persisted);
  }
  if (outcome === 'abort-committed' || outcome === 'abort-uncommitted') {
    await route.abort('failed');
    return;
  }
  await json(route, persisted, method === 'POST' ? 201 : 200);
}

async function installBackend(page: Page, state: BrowserState) {
  page.on('console', (message) => {
    if (message.type() === 'error') state.consoleErrors.push(message.text());
  });
  page.on('requestfailed', (request) => {
    state.requestFailures.push(
      `${request.method()} ${new URL(request.url()).pathname}: ${request.failure()?.errorText}`
    );
  });
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const method = request.method();
    const path = new URL(request.url()).pathname.replace('/api/v1', '');

    if (path === '/auth/me') {
      await json(route, {
        id: 'chunk-16-admin',
        username: 'chunk-16-admin',
        display_name: 'CHUNK-16 Administrator',
        role: 'custom',
        role_id: 'chunk-16-admin-role',
        role_name: 'Administrator',
        permissions: ['admin.roles.manage'],
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
    if (path === '/admin/connections' && method === 'GET') {
      await json(route, []);
      return;
    }
    if (path === '/admin/sso/group-mappings' && method === 'GET') {
      await json(route, {
        mappings: [...state.roles.values()].flatMap((role) =>
          role.group_mappings.map((mapping) => ({
            ...mapping,
            role_id: role.id,
            role_name: role.name,
            created_at: role.created_at,
          }))
        ),
      });
      return;
    }
    if (path === '/admin/sso/group-mappings' && method === 'POST') {
      state.standaloneMappingWrites.push(`${method} ${path}`);
      await json(route, { error: 'internal', message_key: 'error.internal' }, 500);
      return;
    }
    if (path.startsWith('/admin/sso/group-mappings/') && method === 'DELETE') {
      state.standaloneMappingWrites.push(`${method} ${path}`);
      await json(route, { error: 'internal', message_key: 'error.internal' }, 500);
      return;
    }
    if (path === '/admin/roles' && method === 'GET') {
      await json(route, { roles: [...state.roles.values()].map(roleSummary) });
      return;
    }
    if (path === '/admin/roles' && method === 'POST') {
      await handleRoleWrite(route, state, 'POST');
      return;
    }
    const roleMatch = path.match(/^\/admin\/roles\/([^/]+)$/);
    if (roleMatch && method === 'GET') {
      const role = state.roles.get(roleMatch[1]);
      await json(
        route,
        role ?? { error: 'not_found', message_key: 'error.notFound' },
        role ? 200 : 404
      );
      return;
    }
    if (roleMatch && method === 'PUT') {
      await handleRoleWrite(route, state, 'PUT', roleMatch[1]);
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

async function addGroup(page: Page, value: string, locale: 'en' | 'ar') {
  await page
    .getByPlaceholder(locale === 'ar' ? 'اسم مجموعة SSO' : 'SSO group name')
    .fill(value);
  await page.getByTestId('group-mapping-editor').getByRole('button', {
    name: locale === 'ar' ? 'إضافة' : 'Add',
  }).click();
}

async function removeGroup(page: Page, value: string, locale: 'en' | 'ar') {
  await page
    .getByTestId('group-mapping-editor')
    .locator('span')
    .filter({ hasText: value })
    .getByRole('button', { name: locale === 'ar' ? 'حذف' : 'Delete' })
    .click();
}

test('1440px EN performs one composite request per create/update/failure/retry', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const state = initialState(false);
  state.writeGate = deferred();
  await installBackend(page, state);
  await page.goto('/admin/roles?lng=en');

  await page.getByRole('button', { name: 'Add Role' }).click();
  await page.getByLabel('Name').fill('Chunk 16 Created Role');
  await page.getByLabel('Priority').fill('31');
  await addGroup(page, 'chunk16-create-a', 'en');
  await addGroup(page, 'chunk16-create-b', 'en');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('status')).toContainText('Saving role and SSO mappings...');
  await page.keyboard.press('Enter');
  await page.keyboard.press('Enter');
  expect(state.roleWrites).toHaveLength(1);
  state.writeGate.resolve();
  state.writeGate = undefined;
  await expect(
    page.getByRole('status').filter({ hasText: 'Role created successfully' }).last()
  ).toBeVisible();

  expect(state.roleWrites[0]).toMatchObject({
    method: 'POST',
    body: { group_mappings: ['chunk16-create-a', 'chunk16-create-b'] },
  });
  expect(state.standaloneMappingWrites).toEqual([]);

  await page.getByTestId(`edit-role-${CREATED_ROLE_ID}`).click();
  const retainedMappingId = state.roles
    .get(CREATED_ROLE_ID)!
    .group_mappings.find((mapping) => mapping.sso_group_value === 'chunk16-create-b')!.id;
  await removeGroup(page, 'chunk16-create-a', 'en');
  await addGroup(page, 'chunk16-update-c', 'en');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(
    page.getByRole('status').filter({ hasText: 'Role updated successfully' }).last()
  ).toBeVisible();
  expect(state.roleWrites[1]).toMatchObject({
    method: 'PUT',
    body: { group_mappings: ['chunk16-create-b', 'chunk16-update-c'] },
  });
  expect(
    state.roles
      .get(CREATED_ROLE_ID)!
      .group_mappings.find((mapping) => mapping.sso_group_value === 'chunk16-create-b')!.id
  ).toBe(retainedMappingId);

  await page.getByTestId(`edit-role-${CREATED_ROLE_ID}`).click();
  state.nextWriteOutcome = 'conflict';
  await page.getByLabel('Name').fill('Rejected Draft Name');
  await addGroup(page, 'chunk16-conflict', 'en');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('alert')).toContainText(
    'The server rejected the save. Your draft is preserved.'
  );
  await expect(page.getByLabel('Name')).toHaveValue('Rejected Draft Name');
  expect(state.roles.get(CREATED_ROLE_ID)!.name).toBe('Chunk 16 Created Role');

  await page.getByLabel('Name').fill('Corrected Role Name');
  await removeGroup(page, 'chunk16-conflict', 'en');
  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(
    page.getByRole('status').filter({ hasText: 'Role updated successfully' }).last()
  ).toBeVisible();
  expect(state.roles.get(CREATED_ROLE_ID)!.name).toBe('Corrected Role Name');

  await page.getByTestId(`edit-role-${CREATED_ROLE_ID}`).click();
  await page.getByLabel('Name').fill('Unsaved Cancelled Name');
  await page.getByRole('button', { name: 'Cancel' }).click();
  await page.getByTestId(`edit-role-${CREATED_ROLE_ID}`).click();
  await expect(page.getByLabel('Name')).toHaveValue('Corrected Role Name');
  await page.getByRole('button', { name: 'Cancel' }).click();
  await page.reload();
  await expect(page.getByText('Corrected Role Name')).toBeVisible();

  expect(state.roleWrites.map((write) => write.method)).toEqual(['POST', 'PUT', 'PUT', 'PUT']);
  expect(state.standaloneMappingWrites).toEqual([]);
  expect(state.unexpectedApiRequests).toEqual([]);
  expect(state.requestFailures).toEqual([]);
  expect(state.consoleErrors.every((message) => message.includes('409'))).toBe(true);
  await expectNoViewportOverflow(page);
  await page.screenshot({ path: '/tmp/querycraft-chunk16-1440-en.png', fullPage: true });
});

test('768px AR reconciles committed and uncommitted lost responses truthfully', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 });
  const state = initialState();
  await installBackend(page, state);
  await page.goto('/admin/roles?lng=ar');
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');

  await page.getByTestId(`edit-role-${ROLE_ID}`).click();
  state.nextWriteOutcome = 'abort-committed';
  await page.getByLabel('الاسم').fill('Committed After Lost Response');
  await removeGroup(page, 'chunk16-existing-a', 'ar');
  await addGroup(page, 'chunk16-ar-added', 'ar');
  await page.getByRole('button', { name: 'حفظ' }).click();
  await expect(
    page.getByRole('status').filter({ hasText: 'تم تحديث الدور بنجاح' }).last()
  ).toBeVisible();
  expect(state.roles.get(ROLE_ID)!.name).toBe('Committed After Lost Response');

  await page.getByTestId(`edit-role-${ROLE_ID}`).click();
  state.nextWriteOutcome = 'abort-uncommitted';
  await page.getByLabel('الاسم').fill('Uncommitted Preserved Draft');
  await page.getByRole('button', { name: 'حفظ' }).click();
  await expect(page.getByRole('alert')).toContainText('تعذر تأكيد نتيجة الحفظ');
  await expect(page.getByLabel('الاسم')).toHaveValue('Uncommitted Preserved Draft');
  expect(state.roles.get(ROLE_ID)!.name).toBe('Committed After Lost Response');

  await page.getByLabel('الاسم').fill('Arabic Corrected Retry');
  await page.getByRole('button', { name: 'إعادة المحاولة' }).click();
  await expect(
    page.getByRole('status').filter({ hasText: 'تم تحديث الدور بنجاح' }).last()
  ).toBeVisible();
  expect(state.roles.get(ROLE_ID)!.name).toBe('Arabic Corrected Retry');

  expect(state.roleWrites.map((write) => write.outcome)).toEqual([
    'abort-committed',
    'abort-uncommitted',
    'success',
  ]);
  expect(state.standaloneMappingWrites).toEqual([]);
  expect(state.unexpectedApiRequests).toEqual([]);
  expect(state.requestFailures).toHaveLength(2);
  await expectNoViewportOverflow(page);
  await page.screenshot({ path: '/tmp/querycraft-chunk16-768-ar.png', fullPage: true });
});

test('375px EN keeps composite create and cancellation usable', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  const state = initialState(false);
  await installBackend(page, state);
  await page.goto('/admin/roles?lng=en');

  await page.getByRole('button', { name: 'Add Role' }).click();
  await page.getByLabel('Name').fill('Cancelled Mobile Draft');
  await page.getByLabel('Priority').fill('41');
  await addGroup(page, 'chunk16-mobile-cancelled', 'en');
  await page.getByRole('button', { name: 'Cancel' }).click();
  expect(state.roleWrites).toEqual([]);

  await page.getByRole('button', { name: 'Add Role' }).click();
  await page.getByLabel('Name').fill('Mobile Composite Role');
  await page.getByLabel('Priority').fill('42');
  await addGroup(page, 'chunk16-mobile-a', 'en');
  await addGroup(page, 'chunk16-mobile-b', 'en');
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(
    page.getByRole('status').filter({ hasText: 'Role created successfully' }).last()
  ).toBeVisible();

  expect(state.roleWrites).toHaveLength(1);
  expect(state.roleWrites[0].body.group_mappings).toEqual([
    'chunk16-mobile-a',
    'chunk16-mobile-b',
  ]);
  expect(state.standaloneMappingWrites).toEqual([]);
  expect(state.unexpectedApiRequests).toEqual([]);
  expect(state.requestFailures).toEqual([]);
  await expectNoViewportOverflow(page);
  await page.screenshot({ path: '/tmp/querycraft-chunk16-375-en.png', fullPage: true });
});
