import { expect, test, type Page, type Route } from '@playwright/test';

const ALL_PERMISSIONS = [
  'query.submit',
  'query.history.view',
  'admin.connections.manage',
  'admin.roles.manage',
  'admin.sso.manage',
  'admin.audit.verify',
  'admin.quotas.manage',
  'admin.security.manage',
] as const;

type Permission = (typeof ALL_PERMISSIONS)[number];
type Persona = { id: string; username: string; permissions: Permission[] };

const personas: Record<string, Persona> = {
  submit: { id: 'disposable-submit', username: 'submit', permissions: ['query.submit'] },
  history: {
    id: 'disposable-history',
    username: 'history',
    permissions: ['query.history.view'],
  },
  connections: {
    id: 'disposable-connections',
    username: 'connections',
    permissions: ['admin.connections.manage'],
  },
  roles: { id: 'disposable-roles', username: 'roles', permissions: ['admin.roles.manage'] },
  sso: { id: 'disposable-sso', username: 'sso', permissions: ['admin.sso.manage'] },
  audit: { id: 'disposable-audit', username: 'audit', permissions: ['admin.audit.verify'] },
  quotas: {
    id: 'disposable-quotas',
    username: 'quotas',
    permissions: ['admin.quotas.manage'],
  },
  security: {
    id: 'disposable-security',
    username: 'security',
    permissions: ['admin.security.manage'],
  },
  none: { id: 'disposable-none', username: 'none', permissions: [] },
};

type RoleState = {
  id: string;
  name: string;
  description: string;
  priority: number;
  permissions: string[];
  is_builtin: boolean;
  group_mappings: Array<{ id: string; sso_group_value: string }>;
  connection_policy_count: number;
  connection_policies: unknown[];
  created_at: string;
  updated_at: string;
};

const futureRole = (): RoleState => ({
  id: 'future-role',
  name: 'Disposable Future Role',
  description: 'Disposable role',
  priority: 20,
  permissions: [...ALL_PERMISSIONS, 'future.exports.manage'],
  is_builtin: false,
  group_mappings: [],
  connection_policy_count: 0,
  connection_policies: [],
  created_at: '2026-08-09T00:00:00Z',
  updated_at: '2026-08-09T00:00:00Z',
});

function profile(persona: Persona) {
  return {
    id: persona.id,
    username: persona.username,
    display_name: 'Disposable User',
    role: 'admin',
    role_name: 'admin',
    permissions: persona.permissions,
    auth_provider: 'local',
  };
}

async function signIn(page: Page, username: string) {
  await page.goto('/sign-in?lng=en');
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill('disposable-password');
  await page.getByRole('button', { name: 'Sign In', exact: true }).click();
}

async function signOut(page: Page) {
  await page.getByRole('button', { name: 'Sign Out', exact: true }).click();
  await expect(page).toHaveURL(/\/sign-in/);
}

test('CHUNK-07 isolates identity state and enforces the exact permission matrix', async ({ page }) => {
  let consoleErrorCount = 0;
  let pageErrorCount = 0;
  let authenticated: Persona | null = null;
  let failSignOut = false;
  let delayNextSubmitSessions = false;
  let releaseLateSessions: (() => void) | undefined;
  const featurePaths: Array<{ permissionSet: string; path: string }> = [];
  let roles: RoleState[] = [futureRole()];

  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrorCount += 1;
  });
  page.on('pageerror', () => {
    pageErrorCount += 1;
  });

  await page.route('**/api/v1/**', async (route: Route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace('/api/v1', '');
    const method = request.method();

    if (path === '/auth/me') {
      if (!authenticated) {
        await route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'unauthorized', message_key: 'error.unauthorized' }),
        });
        return;
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(profile(authenticated)) });
      return;
    }
    if (path === '/auth/sign-in') {
      const body = request.postDataJSON() as { username: string };
      authenticated = personas[body.username] ?? null;
      await route.fulfill({
        status: authenticated ? 200 : 401,
        contentType: 'application/json',
        body: JSON.stringify(authenticated ? profile(authenticated) : { error: 'unauthorized' }),
      });
      return;
    }
    if (path === '/auth/sign-out') {
      if (failSignOut) {
        await route.fulfill({ status: 503, contentType: 'application/json', body: '{}' });
      } else {
        authenticated = null;
        await route.fulfill({ status: 204 });
      }
      return;
    }
    if (path === '/auth/sso/providers') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"providers":[]}' });
      return;
    }

    featurePaths.push({
      permissionSet: [...(authenticated?.permissions ?? [])].sort().join(','),
      path,
    });

    if (path === '/sessions' && method === 'GET') {
      const sessionsIdentity = authenticated?.username;
      if (delayNextSubmitSessions && authenticated?.username === 'submit') {
        delayNextSubmitSessions = false;
        await new Promise<void>((resolve) => {
          releaseLateSessions = resolve;
        });
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: sessionsIdentity === 'submit'
            ? [{
                id: 'submit-session',
                preview_text: 'Disposable submit session',
                created_at: '2026-08-09T00:00:00Z',
                last_activity_at: '2026-08-09T00:00:00Z',
              }]
            : [],
          total: sessionsIdentity === 'submit' ? 1 : 0,
        }),
      }).catch(() => undefined);
      return;
    }
    if (path === '/connections') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          connections: authenticated?.username === 'submit'
            ? [{ id: 'submit-connection', display_name: 'Disposable Submit DB', database_type: 'postgresql' }]
            : [],
        }),
      });
      return;
    }
    if (path === '/history' && method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: authenticated?.username === 'history'
            ? [{
                id: 'history-entry',
                question_text: 'Disposable history entry',
                generated_sql: 'SELECT 1',
                accepted_at: '2026-08-09T00:00:00Z',
              }]
            : [],
          total: authenticated?.username === 'history' ? 1 : 0,
          next_cursor: null,
        }),
      });
      return;
    }
    if (path === '/admin/settings') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"llm_context_cap":3}' });
      return;
    }
    if (path === '/admin/connections') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"connections":[]}' });
      return;
    }
    if (path === '/admin/roles' && method === 'GET') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ roles }) });
      return;
    }
    if (path === '/admin/roles' && method === 'POST') {
      const body = request.postDataJSON() as Partial<RoleState>;
      const role: RoleState = {
        ...futureRole(),
        ...body,
        id: 'created-role',
        group_mappings: [],
        connection_policy_count: 0,
        connection_policies: body.connection_policies ?? [],
      };
      roles = [...roles, role];
      await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(role) });
      return;
    }
    if (path.startsWith('/admin/roles/') && method === 'GET') {
      const role = roles.find(({ id }) => path.endsWith(`/${id}`));
      await route.fulfill({ status: role ? 200 : 404, contentType: 'application/json', body: JSON.stringify(role ?? {}) });
      return;
    }
    if (path.startsWith('/admin/roles/') && method === 'PUT') {
      const roleId = path.split('/').at(-1);
      const body = request.postDataJSON() as Partial<RoleState>;
      roles = roles.map((role) => role.id === roleId ? { ...role, ...body } : role);
      const role = roles.find(({ id }) => id === roleId);
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(role) });
      return;
    }
    if (path === '/admin/sso/group-mappings') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"mappings":[]}' });
      return;
    }
    if (path === '/admin/sso/providers') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"providers":[]}' });
      return;
    }
    if (path === '/admin/audit/status') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"total_entries":0,"last_verification":null}' });
      return;
    }
    if (path === '/admin/audit/verify') {
      if (!authenticated?.permissions.includes('admin.audit.verify')) {
        await route.fulfill({ status: 403, contentType: 'application/json', body: '{"error":"forbidden","message_key":"error.forbidden"}' });
      } else {
        await route.fulfill({ status: 200, contentType: 'application/json', body: '{"verified":true,"entries_checked":0,"first_break_at":null,"verified_at":"2026-08-09T00:00:00Z"}' });
      }
      return;
    }
    if (path === '/admin/audit/entries') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"entries":[],"pagination":{"page":1,"page_size":10,"total_entries":0,"total_pages":0}}' });
      return;
    }
    if (path === '/admin/audit/retention') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"retention_months":6,"last_purge_at":null,"purged_count":null}' });
      return;
    }
    if (path === '/admin/quotas') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"quotas":[]}' });
      return;
    }
    if (path === '/admin/quotas/status') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":[]}' });
      return;
    }
    if (path === '/admin/detection/config') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"block_confidence":0.8,"flag_confidence":0.5}' });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });

  await signIn(page, 'submit');
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText('Disposable submit session')).toBeVisible();
  await signOut(page);

  await signIn(page, 'history');
  await expect(page).toHaveURL(/\/history$/);
  await expect(page.getByText('Disposable history entry')).toBeVisible();
  await expect(page.getByText('Disposable submit session')).toHaveCount(0);

  failSignOut = true;
  await page.getByRole('button', { name: 'Sign Out', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('server session is still active');
  await expect(page).toHaveURL(/\/history$/);
  failSignOut = false;
  await signOut(page);

  await signIn(page, 'submit');
  delayNextSubmitSessions = true;
  await page.reload();
  await expect.poll(() => releaseLateSessions !== undefined).toBe(true);
  await page.getByRole('button', { name: 'Sign Out', exact: true }).click();
  await expect(page).toHaveURL(/\/sign-in/);
  await page.evaluate(() => {
    const state = { watch: true, observed: false };
    Object.assign(window, { __chunk07OldIdentityWatch: state });
    new MutationObserver(() => {
      const bodyText = document.body.textContent ?? '';
      if (
        state.watch &&
        (bodyText.includes('Disposable submit session') ||
          bodyText.includes('Disposable Submit DB'))
      ) {
        state.observed = true;
      }
    }).observe(document.body, { childList: true, subtree: true, characterData: true });
  });
  await signIn(page, 'history');
  releaseLateSessions?.();
  await expect(page.getByText('Disposable history entry')).toBeVisible();
  await expect.poll(() => page.evaluate(() => {
    const state = (window as unknown as { __chunk07OldIdentityWatch: { observed: boolean } })
      .__chunk07OldIdentityWatch;
    return state.observed;
  })).toBe(false);

  await signOut(page);
  const requestsBeforeDenied = featurePaths.length;
  await signIn(page, 'none');
  await expect(page).toHaveURL(/\/access-denied$/);
  await expect(page.getByRole('heading', { name: 'Access denied' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sign Out' })).toBeVisible();
  expect(featurePaths.length).toBe(requestsBeforeDenied);
  const accessDeniedA11y = await page.locator('body').ariaSnapshot();
  expect(accessDeniedA11y).toContain('Access denied');
  expect(accessDeniedA11y).toContain('Sign Out');
  await page.goto('/access-denied?lng=ar');
  await expect(page.getByRole('heading', { name: 'تم رفض الوصول' })).toBeVisible();
  await page.goto('/access-denied?lng=en');
  await signOut(page);

  const routeMatrix: Array<{
    username: string;
    path: string;
    visible: string[];
    allowedPrefixes: string[];
  }> = [
    { username: 'submit', path: '/', visible: ['sidebar-new-chat'], allowedPrefixes: ['/sessions', '/connections'] },
    { username: 'history', path: '/history', visible: ['sidebar-nav-history'], allowedPrefixes: ['/history'] },
    { username: 'connections', path: '/admin/connections', visible: ['sidebar-nav-settings', 'sidebar-nav-connections'], allowedPrefixes: ['/admin/connections'] },
    { username: 'roles', path: '/admin/roles', visible: ['sidebar-nav-roles'], allowedPrefixes: ['/admin/roles', '/admin/sso/group-mappings'] },
    { username: 'sso', path: '/admin/sso', visible: ['sidebar-nav-sso'], allowedPrefixes: ['/admin/sso/providers'] },
    { username: 'audit', path: '/admin/audit', visible: ['sidebar-nav-audit'], allowedPrefixes: ['/admin/audit'] },
    { username: 'quotas', path: '/admin/quotas', visible: ['sidebar-nav-quotas'], allowedPrefixes: ['/admin/quotas'] },
    { username: 'security', path: '/admin/detection', visible: ['sidebar-nav-detection'], allowedPrefixes: ['/admin/detection'] },
  ];
  const allNavigationIds = [
    'sidebar-new-chat',
    'sidebar-nav-history',
    'sidebar-nav-settings',
    'sidebar-nav-connections',
    'sidebar-nav-roles',
    'sidebar-nav-sso',
    'sidebar-nav-audit',
    'sidebar-nav-quotas',
    'sidebar-nav-detection',
  ];

  for (const scenario of routeMatrix) {
    const requestStart = featurePaths.length;
    await signIn(page, scenario.username);
    await expect(page).toHaveURL(new RegExp(`${scenario.path.replace('/', '\\/')}$`));
    for (const testId of allNavigationIds) {
      await expect(page.getByTestId(testId)).toHaveCount(scenario.visible.includes(testId) ? 1 : 0);
    }
    await page.waitForLoadState('networkidle');
    const scenarioRequests = featurePaths.slice(requestStart);
    expect(
      scenarioRequests.every(({ path }) =>
        scenario.allowedPrefixes.some((prefix) => path.startsWith(prefix))
      )
    ).toBe(true);
    if (scenario.username === 'sso') {
      expect(scenarioRequests.some(({ path }) => path.includes('group-mappings'))).toBe(false);
    }
    if (scenario.username === 'quotas') {
      expect(scenarioRequests.some(({ path }) => path.startsWith('/admin/roles'))).toBe(false);
    }
    await signOut(page);
  }

  await signIn(page, 'roles');
  await page.getByTestId('edit-role-future-role').click();
  const permissionCheckboxes = page.locator('input[id^="perm-"]');
  await expect(permissionCheckboxes).toHaveCount(8);
  for (let index = 0; index < 8; index += 1) {
    await expect(permissionCheckboxes.nth(index)).toBeChecked();
  }
  await expect(page.getByText('future.exports.manage')).toHaveCount(0);
  await page.locator('#perm-admin\\.quotas\\.manage').uncheck();
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.getByTestId('roles-table-scroll')).toBeVisible();
  expect(roles[0].permissions).toContain('future.exports.manage');
  expect(roles[0].permissions).toContain('admin.security.manage');
  expect(roles[0].permissions).not.toContain('admin.quotas.manage');

  await page.getByRole('button', { name: 'Add Role' }).click();
  await page.getByLabel('Name').fill('Disposable Catalog Role');
  await page.getByLabel('Priority').fill('30');
  const createPermissionCheckboxes = page.locator('input[id^="perm-"]');
  for (let index = 0; index < 8; index += 1) {
    await createPermissionCheckboxes.nth(index).check();
  }
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.getByText('Disposable Catalog Role')).toBeVisible();
  expect(roles.find(({ id }) => id === 'created-role')?.permissions).toEqual(ALL_PERMISSIONS);
  await page.reload();
  await expect(page.getByText('Disposable Catalog Role')).toBeVisible();
  await signOut(page);

  await signIn(page, 'audit');
  await expect(page).toHaveURL(/\/admin\/audit$/);
  personas.audit.permissions = [];
  await page.getByRole('button', { name: /verify/i }).click();
  await expect(page).toHaveURL(/\/access-denied$/);
  expect(authenticated?.username).toBe('audit');
  personas.audit.permissions = ['admin.audit.verify'];
  await page.evaluate(() => {
    window.history.pushState({}, '', '/permission-grant-check');
    window.dispatchEvent(new PopStateEvent('popstate'));
  });
  await expect(page).toHaveURL(/\/admin\/audit$/);

  await page.goBack();
  await page.goForward();
  await page.reload();
  await expect(page).toHaveURL(/\/admin\/audit$/);
  await expect(page.getByText('Disposable submit session')).toHaveCount(0);
  await expect(page.getByText('Disposable history entry')).toHaveCount(0);

  const storage = await page.evaluate(() => JSON.stringify({ ...localStorage }));
  expect(storage).not.toContain('disposable-submit');
  expect(storage).not.toContain('Disposable submit session');
  expect(storage).not.toContain('Disposable history entry');

  const uiState = await page.evaluate(async () => {
    const { useUIStore } = await import('/src/stores/uiStore.ts');
    const state = useUIStore.getState();
    return {
      hasActiveSession: state.activeSessionId !== null,
      hasHoveredSession: state.hoveredSessionId !== null,
      hasPromptDraft: state.promptDraft.length > 0,
    };
  });
  expect(uiState).toEqual({
    hasActiveSession: false,
    hasHoveredSession: false,
    hasPromptDraft: false,
  });

  expect(featurePaths.some(({ permissionSet }) => permissionSet === '')).toBe(false);
  expect(consoleErrorCount).toBe(0);
  expect(pageErrorCount).toBe(0);
});
