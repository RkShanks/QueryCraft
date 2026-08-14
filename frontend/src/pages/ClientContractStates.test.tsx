import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ConnectionResponse } from '../api/generated/types.gen';
import i18n from '../i18n';
import { server } from '../test/server';
import { renderWithClient } from '../test/utils';
import { AdminConnectionsPage } from './AdminConnectionsPage';

const VALID_CONNECTION = {
  id: 'd290f1ee-6c54-4b01-90e6-d701748f0851',
  display_name: 'Validated production database',
  database_name: 'querycraft',
  database_type: 'postgresql',
  port: 5432,
  ssl_mode: 'require',
  lifecycle_state: 'active',
  health_status: 'healthy',
  health_error_category: null,
  last_health_check_at: '2026-08-14T08:00:00Z',
  schema_introspection_status: 'success',
  schema_last_refreshed_at: '2026-08-14T08:00:00Z',
  created_at: '2026-08-14T07:00:00Z',
  updated_at: '2026-08-14T08:00:00Z',
} satisfies ConnectionResponse;

const MALFORMED_CANARY = 'malformed-response-canary-17';

describe('client contract response states', () => {
  afterEach(async () => {
    localStorage.clear();
    sessionStorage.clear();
    await i18n.changeLanguage('en');
  });

  it.each([
    ['en', 'The server returned an invalid response. Please try again.'],
    ['ar', 'أعاد الخادم استجابة غير صالحة. يُرجى المحاولة مرة أخرى.'],
  ] as const)(
    'shows a localized retry for a malformed initial response in %s without leaking it',
    async (language, expectedMessage) => {
      let responseCount = 0;
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
      const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
      server.use(
        http.get('/api/v1/admin/connections', () => {
          responseCount += 1;
          return HttpResponse.json(
            responseCount === 1
              ? [{ ...VALID_CONNECTION, port: MALFORMED_CANARY }]
              : [],
            { status: 200 }
          );
        })
      );
      await i18n.changeLanguage(language);

      const { queryClient } = renderWithClient(<AdminConnectionsPage />);

      expect(await screen.findByRole('alert')).toHaveTextContent(expectedMessage);
      const retry = screen.getByRole('button', {
        name: language === 'ar' ? 'إعادة المحاولة' : 'Retry',
      });
      expect(document.body).not.toHaveTextContent(MALFORMED_CANARY);
      expect(JSON.stringify(queryClient.getQueryCache().getAll())).not.toContain(MALFORMED_CANARY);
      expect(JSON.stringify({ ...localStorage })).not.toContain(MALFORMED_CANARY);
      expect(JSON.stringify({ ...sessionStorage })).not.toContain(MALFORMED_CANARY);
      expect(consoleError.mock.calls.flat().join(' ')).not.toContain(MALFORMED_CANARY);
      expect(consoleWarn.mock.calls.flat().join(' ')).not.toContain(MALFORMED_CANARY);

      fireEvent.click(retry);

      expect(await screen.findByText('No database connections configured.')).toBeInTheDocument();
      expect(responseCount).toBe(2);
      consoleError.mockRestore();
      consoleWarn.mockRestore();
    }
  );

  it('preserves prior validated data when a background refresh is malformed', async () => {
    let returnMalformed = false;
    server.use(
      http.get('/api/v1/admin/connections', () =>
        HttpResponse.json(
          returnMalformed
            ? [{ ...VALID_CONNECTION, lifecycle_state: MALFORMED_CANARY }]
            : [VALID_CONNECTION],
          { status: 200 }
        )
      )
    );

    const { queryClient } = renderWithClient(<AdminConnectionsPage />);
    expect(await screen.findByText(VALID_CONNECTION.display_name)).toBeInTheDocument();

    returnMalformed = true;
    await act(async () => {
      await queryClient.invalidateQueries({ queryKey: ['adminConnections'] });
    });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'The latest refresh was invalid. Showing the last valid data.'
      );
    });
    expect(screen.getByText(VALID_CONNECTION.display_name)).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(MALFORMED_CANARY);
    expect(queryClient.getQueryData(['adminConnections'])).toEqual({
      connections: [
        expect.objectContaining({
          id: VALID_CONNECTION.id,
          display_name: VALID_CONNECTION.display_name,
        }),
      ],
    });
    expect(JSON.stringify(queryClient.getQueryData(['adminConnections']))).not.toContain(
      MALFORMED_CANARY
    );
  });
});
