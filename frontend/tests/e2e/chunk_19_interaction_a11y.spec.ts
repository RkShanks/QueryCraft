import { expect, test, type Page } from '@playwright/test';

import { PERMISSIONS } from '../../src/auth/permissions';
import { signInLocalUser } from './helpers/auth';
import { mockLocalAuth } from './helpers/mock-backend';

const SECRET = 'live-signin-secret-C19';
const ALL_PERMISSIONS = Object.values(PERMISSIONS);

test.use({ screenshot: 'off', trace: 'off', video: 'off' });

const SESSION_A = '650e8400-e29b-41d4-a716-446655440201';
const SESSION_B = '650e8400-e29b-41d4-a716-446655440202';

const SELECTOR_CONNECTIONS = {
  connections: [
    {
      id: '550e8400-e29b-41d4-a716-4466554400a1',
      display_name: 'Analytics MySQL',
      database_type: 'mysql',
    },
    {
      id: '550e8400-e29b-41d4-a716-4466554400a2',
      display_name: 'Production PG',
      database_type: 'postgresql',
    },
    {
      id: '550e8400-e29b-41d4-a716-4466554400a3',
      display_name: 'Warehouse MSSQL',
      database_type: 'mssql',
    },
  ],
};

function sessionsPage(items: Array<{ id: string; preview_text: string }>) {
  return {
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      items: items.map((item) => ({
        ...item,
        created_at: '2026-08-20T09:00:00Z',
        last_activity_at: '2026-08-21T15:30:00Z',
      })),
      total: items.length,
      next_cursor: null,
    }),
  };
}

async function mockWorkspaceShell(page: Page, connections: object = SELECTOR_CONNECTIONS) {
  await mockLocalAuth(page);
  await page.route('**/api/v1/connections', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(connections),
    })
  );
  await page.route('**/api/v1/query/limits', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ max_question_length: 2000 }),
    })
  );
}

async function mockSessions(page: Page) {
  await page.route(/\/api\/v1\/sessions(?:\?.*)?$/, (route) =>
    route.fulfill(
      sessionsPage([
        { id: SESSION_A, preview_text: 'Quarterly revenue question' },
        { id: SESSION_B, preview_text: 'Warehouse inventory question' },
      ])
    )
  );
}

test.describe('CHUNK-19 interaction and form accessibility', () => {
  test('1440px EN selector exposes the full keyboard and typeahead model', async ({
    page,
  }) => {
    await mockWorkspaceShell(page);
    await mockSessions(page);
    await signInLocalUser(page);

    const trigger = page.getByTestId('database-selector-trigger');
    const analytics = page.getByTestId(
      'database-selector-option-550e8400-e29b-41d4-a716-4466554400a1'
    );
    const production = page.getByTestId(
      'database-selector-option-550e8400-e29b-41d4-a716-4466554400a2'
    );
    const warehouse = page.getByTestId(
      'database-selector-option-550e8400-e29b-41d4-a716-4466554400a3'
    );

    await expect(trigger).toBeVisible();
    await expect(trigger).toHaveAttribute('aria-haspopup', 'listbox');

    // Keyboard open focuses the first option while nothing is selected yet.
    await trigger.focus();
    await page.keyboard.press('ArrowDown');
    const listbox = page.getByRole('listbox');
    await expect(listbox).toBeVisible();
    await expect(trigger).toHaveAttribute('aria-expanded', 'true');
    const controls = await trigger.getAttribute('aria-controls');
    expect(controls).toBeTruthy();
    await expect(analytics).toBeFocused();

    // Roving focus with wrap-clamped arrows plus Home/End jumps.
    await page.keyboard.press('ArrowDown');
    await expect(production).toBeFocused();
    await expect(production).toHaveAttribute('aria-selected', 'false');
    await page.keyboard.press('End');
    await expect(warehouse).toBeFocused();
    await page.keyboard.press('Home');
    await expect(analytics).toBeFocused();
    await page.keyboard.press('ArrowUp');
    await expect(analytics).toBeFocused();

    // Escape restores trigger focus without changing selection.
    await page.keyboard.press('Escape');
    await expect(listbox).toHaveCount(0);
    await expect(trigger).toBeFocused();

    // Re-open and jump via localized typeahead, then select with Enter.
    await page.keyboard.press('ArrowDown');
    await expect(listbox).toBeVisible();
    await page.keyboard.press('p');
    await expect(production).toBeFocused();
    await page.keyboard.press('w');
    await expect(warehouse).toBeFocused();
    await page.keyboard.press('Enter');

    await expect(listbox).toHaveCount(0);
    await expect(trigger).toBeFocused();
    await expect(trigger).toContainText('Warehouse MSSQL');
    await expect(trigger).toHaveAttribute('aria-expanded', 'false');

    // Re-opening now focuses the newly selected option; Tab closes without trapping.
    await page.keyboard.press('ArrowDown');
    await expect(listbox).toBeVisible();
    await expect(warehouse).toBeFocused();
    await expect(warehouse).toHaveAttribute('aria-selected', 'true');
    await page.keyboard.press('Tab');
    await expect(listbox).toHaveCount(0);
  });

  test('1440px EN sign-in form covers invalid, rejected, retry, double-submit and success states', async ({
    page,
  }) => {
    let rejectSignIn = true;
    let authenticated = false;
    let signInRequests = 0;
    const browserOutput: string[] = [];
    page.on('console', (message) => browserOutput.push(message.text()));

    await page.route('**/api/v1/auth/me', (route) => {
      if (!authenticated) {
        return route.fulfill({ status: 401, contentType: 'application/json', body: '{}' });
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'd290f1ee-6c54-4b01-90e6-d701748f0851',
          username: 'admin',
          display_name: 'Admin User',
          role: 'admin',
          permissions: ALL_PERMISSIONS,
          auth_provider: 'local',
        }),
      });
    });
    await page.route('**/api/v1/auth/sign-in', async (route) => {
      signInRequests += 1;
      if (rejectSignIn) {
        return route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'unauthorized' }),
        });
      }
      authenticated = true;
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'd290f1ee-6c54-4b01-90e6-d701748f0851',
          username: 'admin',
          display_name: 'Admin User',
          role: 'admin',
          permissions: ALL_PERMISSIONS,
          auth_provider: 'local',
        }),
      });
    });
    await page.route('**/api/v1/auth/sso/providers', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ providers: [] }),
      })
    );

    await page.goto('/sign-in?lng=en');
    const form = page.locator('form.sign-in-form');
    await expect(form).toBeVisible();

    // Invalid boundary: empty submission focuses the first invalid field.
    await form.getByRole('button', { name: /sign in/i }).click();
    const alertRegion = page.getByRole('alert');
    await expect(alertRegion).toContainText('Username cannot be empty.');
    await expect(form.getByLabel(/username/i)).toBeFocused();
    await expect(form.getByLabel(/username/i)).toHaveAttribute('aria-invalid', 'true');

    // Editing clears the field error state.
    await form.getByLabel(/username/i).fill('admin');
    await expect(form.getByLabel(/username/i)).not.toHaveAttribute('aria-invalid');

    await form.getByRole('button', { name: /sign in/i }).click();
    await expect(alertRegion).toContainText('Password cannot be empty.');
    await expect(form.getByLabel(/password/i)).toBeFocused();

    // Server rejection keeps the secret out of DOM text and console output and
    // returns through the app-level auth transition to a clean retryable form.
    await form.getByLabel(/password/i).fill(SECRET);
    await form.getByRole('button', { name: /sign in/i }).click();
    await page.waitForResponse(
      (response) =>
        response.url().includes('/auth/sign-in') && response.status() === 401
    );
    await expect(form).toBeVisible({ timeout: 10_000 });
    for (const message of browserOutput) {
      expect(message).not.toContain(SECRET);
    }
    await expect(page.locator('body')).not.toContainText(SECRET);

    // Retry after rejection succeeds and leaves the sign-in route.
    await form.getByLabel(/username/i).fill('admin');
    await form.getByLabel(/password/i).fill(SECRET);
    rejectSignIn = false;
    await form.getByRole('button', { name: /sign in/i }).click();
    await expect(page).not.toHaveURL(/sign-in/, { timeout: 10_000 });
    expect(signInRequests).toBe(2);
  });

  test('768px AR delete dialog traps focus, honors Escape and holds pending state', async ({
    page,
  }) => {
    await mockLocalAuth(page);
    await page.setViewportSize({ width: 768, height: 900 });
    await page.route('**/api/v1/admin/connections', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: '750e8400-e29b-41d4-a716-446655440301',
            display_name: 'Analytics PG',
            database_type: 'postgresql',
            database_name: 'analytics',
            host: 'localhost',
            port: 5432,
            ssl_mode: 'prefer',
            lifecycle_state: 'active',
            health_status: 'healthy',
            health_error_category: null,
            last_health_check_at: '2026-08-21T15:00:00Z',
            schema_introspection_status: 'success',
            schema_last_refreshed_at: null,
            created_at: '2026-08-01T08:00:00Z',
            updated_at: '2026-08-20T12:00:00Z',
          },
        ]),
      })
    );
    await page.route('**/api/v1/sessions*', (route) =>
      route.fulfill(sessionsPage([]))
    );
    await page.route('**/api/v1/auth/sso/providers', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ providers: [] }),
      })
    );

    let releaseDelete: (() => void) | undefined;
    let deleteRequests = 0;
    await page.route('**/api/v1/admin/connections/*', async (route) => {
      if (route.request().method() === 'DELETE') {
        deleteRequests += 1;
        await new Promise<void>((resolve) => {
          releaseDelete = resolve;
        });
        return route.fulfill({ status: 204 });
      }
      return route.fallback();
    });

    await signInLocalUser(page);
    await page.goto('/admin/connections?lng=ar');

    const deleteButton = page.getByRole('button', { name: 'حذف' }).first();
    await deleteButton.click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute('aria-modal', 'true');
    await expect(dialog).toContainText('هل أنت متأكد من رغبتك في حذف هذا الاتصال؟');

    // Focus enters the dialog at the least destructive control and cycles inside.
    const cancelButton = page.getByRole('button', { name: 'إلغاء' });
    await expect(cancelButton).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    const confirmDelete = page.getByTestId('confirm-delete-btn');
    await expect(confirmDelete).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(cancelButton).toBeFocused();

    // Escape cancels and restores focus to the Delete trigger.
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(deleteButton).toBeFocused();

    // Destructive pending state: controls disable, Escape is held, one request.
    await deleteButton.click();
    await confirmDelete.click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(confirmDelete).toBeDisabled();
    await expect(cancelButton).toBeDisabled();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toBeVisible();
    expect(deleteRequests).toBe(1);

    releaseDelete?.();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    expect(deleteRequests).toBe(1);
  });

  test('375px AR session controls stay independent while undo pauses, resumes and expires', async ({
    page,
  }) => {
    await page.clock.install({ time: new Date('2026-08-22T10:00:00Z') });
    await mockWorkspaceShell(page, {
      connections: [
        {
          id: '550e8400-e29b-41d4-a716-446655440010',
          display_name: 'Local Pagila',
          database_type: 'postgresql',
        },
      ],
    });
    await mockSessions(page);

    const deleteCalls: string[] = [];
    await page.route('**/api/v1/sessions/*', async (route) => {
      if (route.request().method() === 'DELETE') {
        deleteCalls.push(new URL(route.request().url()).pathname);
        return route.fulfill({ status: 204 });
      }
      const path = new URL(route.request().url()).pathname;
      if (path.endsWith('/connection')) {
        const connectionSessionId = path.split('/')[3] ?? '';
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            id: connectionSessionId,
            preview_text: 'Session detail preview',
            created_at: '2026-08-20T09:00:00Z',
            last_activity_at: '2026-08-21T15:30:00Z',
            connection_id: null,
          }),
        });
      }
      const detailId = path.split('/').pop() ?? '';
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: detailId,
          preview_text: 'Session detail preview',
          created_at: '2026-08-20T09:00:00Z',
          last_activity_at: '2026-08-21T15:30:00Z',
          connection_id: null,
          attempts: [],
          attempts_next_cursor: null,
          attempts_total: 0,
        }),
      });
    });

    await signInLocalUser(page);
    await page.setViewportSize({ width: 375, height: 700 });
    // Re-enter under Arabic so the shell mounts in RTL at this width.
    await page.goto('/?lng=ar');
    const itemA = page.getByTestId(`session-item-${SESSION_A}`);
    const mainA = page.getByTestId(`session-item-main-${SESSION_A}`);

    // The rail auto-collapses at this width; expand it once the identity
    // transition settles. The hover-revealed delete affordance is exercised
    // through force clicks because pointer reveal is progressive enhancement;
    // keyboard reachability of the same control is pinned by unit tests.
    await expect(mainA).toBeVisible();
    await page.getByTestId('sidebar-toggle').click();
    const deleteA = page.getByTestId(`session-delete-${SESSION_A}`);
    await expect(deleteA).toBeAttached();

    // Deleting opens the timed toast; the session row disappears immediately.
    // Keyboard activation proves the destructive control is reachable without
    // a pointer while also driving the timed-toast flow deterministically.
    await deleteA.focus();
    await page.keyboard.press('Enter');
    const toastA = page.locator('[data-testid^="undo-toast-"]').first();
    await expect(toastA).toBeVisible();
    expect(deleteCalls).toHaveLength(0);

    // Hovering pauses the destructive countdown past its original deadline.
    await page.clock.runFor(2000);
    const progressMid = parseFloat(
      await page
        .locator('[data-testid^="undo-progress-"]')
        .first()
        .evaluate((el) => el.style.width)
    );
    expect(progressMid).toBeGreaterThan(30);
    expect(progressMid).toBeLessThan(80);

    await toastA.hover();
    await page.clock.runFor(10000);
    await expect(toastA).toBeVisible();
    expect(deleteCalls).toHaveLength(0);

    // Leaving resumes from the remaining duration until expiry deletes once.
    await page.getByTestId('sidebar-toggle').hover();
    await page.clock.runFor(2500);
    await expect(toastA).toBeVisible();
    expect(deleteCalls).toHaveLength(0);

    await page.clock.runFor(700);
    await expect(toastA).toHaveCount(0);
    await expect.poll(() => deleteCalls.length).toBe(1);
    expect(deleteCalls[0]).toContain(SESSION_A);

    // Keyboard-focused undo pauses too; a second toast expires once unfocused.
    const itemB = page.getByTestId(`session-item-${SESSION_B}`);
    await itemB.scrollIntoViewIfNeeded();
    const deleteB = page.getByTestId(`session-delete-${SESSION_B}`);
    await deleteB.focus();
    await page.keyboard.press('Enter');
    const undoB = page.locator('[data-testid^="undo-button-"]').first();
    const toastB = page.locator('[data-testid^="undo-toast-"]').first();
    await undoB.focus();
    await page.clock.runFor(8000);
    await expect(toastB).toBeVisible();
    expect(deleteCalls).toHaveLength(1);

    await undoB.blur();
    await page.clock.runFor(5200);
    await expect(toastB).toHaveCount(0);
    expect(deleteCalls).toHaveLength(2);
    expect(deleteCalls[1]).toContain(SESSION_B);

    // Selecting a session activates it without any deletion side effect; the
    // rail is re-expanded first because activation re-collapses it at this width.
    await expect(itemB).toBeAttached();
    await page.getByTestId('sidebar-toggle').click();
    await mainA.click();
    await expect(itemA).toHaveClass(/session-item-active/);
    expect(deleteCalls).toHaveLength(2);
  });
});
