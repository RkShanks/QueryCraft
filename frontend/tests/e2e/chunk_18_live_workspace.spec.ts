import { expect, test, type APIResponse } from '@playwright/test';
import { signInLocalUser } from './helpers/auth';

type AdminConnection = {
  id: string;
  display_name: string;
};

type AdminRole = {
  id: string;
  name: string;
};

type ConnectionSchema = {
  tables: Array<{
    table_name: string;
    columns: Array<{ column_name: string }>;
  }>;
};

const originHeaders = { Origin: 'http://localhost:3000' };

async function expectJsonOk(response: APIResponse) {
  const request = response.request();
  const endpoint = new URL(response.url()).pathname;
  expect(
    response.ok(),
    `${request.method()} ${endpoint} returned HTTP ${response.status()}`
  ).toBe(true);
  expect(response.headers()['content-type']).toContain('application/json');
}

test('real authenticated query renders through ResultTable without route mocks', async ({ page }) => {
  const username = process.env.CHUNK18_LIVE_USERNAME;
  const password = process.env.CHUNK18_LIVE_PASSWORD;
  const sourcePassword = process.env.CHUNK18_LIVE_SOURCE_PASSWORD;

  test.skip(!username || !password || !sourcePassword, 'CHUNK-18 disposable live credentials are required.');

  const browserOutput: string[] = [];
  page.on('console', (message) => browserOutput.push(message.text()));
  page.on('pageerror', (error) => browserOutput.push(error.message));

  await signInLocalUser(page, { username, password });

  const connectionsResponse = await page.request.get('/api/v1/admin/connections');
  await expectJsonOk(connectionsResponse);
  const connections = (await connectionsResponse.json()) as AdminConnection[];
  const connection = connections.find((candidate) => candidate.display_name === 'source_analytics');
  expect(connection).toBeDefined();

  const healthResponse = await page.request.post(
    `/api/v1/admin/connections/${connection!.id}/test`,
    { headers: originHeaders }
  );
  await expectJsonOk(healthResponse);
  await expect(healthResponse.json()).resolves.toMatchObject({ status: 'healthy' });

  const refreshResponse = await page.request.post(
    `/api/v1/admin/connections/${connection!.id}/refresh-schema`,
    { headers: originHeaders }
  );
  await expectJsonOk(refreshResponse);

  const schemaResponse = await page.request.get(
    `/api/v1/admin/connections/${connection!.id}/schema`
  );
  await expectJsonOk(schemaResponse);
  const schema = (await schemaResponse.json()) as ConnectionSchema;
  const table = schema.tables.find((candidate) => candidate.columns.length > 0);
  expect(table).toBeDefined();

  const rolesResponse = await page.request.get('/api/v1/admin/roles');
  await expectJsonOk(rolesResponse);
  const roles = (await rolesResponse.json()) as { roles: AdminRole[] };
  const adminRole = roles.roles.find((role) => role.name === 'Admin');
  expect(adminRole).toBeDefined();

  const policyResponse = await page.request.put(`/api/v1/admin/roles/${adminRole!.id}`, {
    headers: originHeaders,
    data: {
      connection_policies: [
        {
          connection_id: connection!.id,
          allowed_tables: [
            {
              table: table!.table_name,
              columns: table!.columns.map((column) => column.column_name),
            },
          ],
          row_filters: [],
          column_masks: [],
        },
      ],
    },
  });
  await expectJsonOk(policyResponse);

  await page.reload();
  const input = page.getByPlaceholder(/Ask a question/i);
  await expect(input).toBeEnabled({ timeout: 15_000 });

  const submitResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes('/api/v1/query/submit') && response.request().method() === 'POST'
  );
  await input.fill('Return one deterministic row');
  await page.getByTestId('prompt-send').click();

  const submitResponse = await submitResponsePromise;
  await expectJsonOk(submitResponse);
  const apiOutput = JSON.stringify(await submitResponse.json());

  const tableResult = page.getByRole('table', { name: 'Results' });
  await expect(tableResult).toBeVisible({ timeout: 15_000 });
  await expect(tableResult.getByRole('columnheader', { name: 'id' })).toBeVisible();
  await expect(tableResult.getByRole('cell', { name: '1', exact: true })).toBeVisible();

  const renderedOutput = await page.locator('body').innerText();
  const inspectedOutput = [apiOutput, renderedOutput, browserOutput.join('\n')].join('\n');
  for (const secret of [password!, sourcePassword!]) {
    expect(inspectedOutput).not.toContain(secret);
  }
  expect(inspectedOutput).not.toMatch(/Traceback \(most recent call last\)|stack trace|password=/i);
  await expect(page.getByText(/invalid response/i)).toHaveCount(0);
});
