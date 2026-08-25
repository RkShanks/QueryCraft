import { describe, it, expect } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../test/server';
import { renderWithClient } from '../test/utils';
import i18n from '../i18n';
import { AdminDetectionPage } from './AdminDetectionPage';

describe('AdminDetectionPage', () => {
  it('renders sliders/inputs with current thresholds from API', async () => {
    server.use(
      http.get('/api/v1/admin/detection/config', () => {
        return HttpResponse.json(
          { block_confidence: 0.8, flag_confidence: 0.5, updated_at: '2026-06-22T00:00:00Z' },
          { status: 200 }
        );
      })
    );

    renderWithClient(<AdminDetectionPage />);

    // Wait for sliders/inputs to render
    const blockInput = await screen.findByRole('slider', { name: /block/i });
    const flagInput = await screen.findByRole('slider', { name: /flag/i });

    expect(blockInput).toHaveValue('0.8');
    expect(flagInput).toHaveValue('0.5');
  });

  it('gives both synchronized numeric inputs localized accessible names', async () => {
    server.use(
      http.get('/api/v1/admin/detection/config', () => {
        return HttpResponse.json(
          { block_confidence: 0.8, flag_confidence: 0.5, updated_at: '2026-06-22T00:00:00Z' },
          { status: 200 }
        );
      })
    );

    renderWithClient(<AdminDetectionPage />);

    expect(
      await screen.findByRole('spinbutton', { name: /block threshold/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('spinbutton', { name: /flag threshold/i })
    ).toBeInTheDocument();

    for (const control of [
      ...screen.getAllByRole('slider'),
      ...screen.getAllByRole('spinbutton'),
    ]) {
      expect(control).toHaveClass('focus-visible:ring-2');
    }
  });

  it('localizes and isolates the Arabic update timestamp', async () => {
    server.use(
      http.get('/api/v1/admin/detection/config', () => {
        return HttpResponse.json(
          { block_confidence: 0.8, flag_confidence: 0.5, updated_at: '2026-06-22T00:00:00Z' },
          { status: 200 }
        );
      })
    );

    await i18n.changeLanguage('ar');
    try {
      renderWithClient(<AdminDetectionPage />);

      const timestamp = await screen.findByTestId('detection-updated-at');
      expect(timestamp).toHaveTextContent('آخر تحديث');
      const timestampValue = screen.getByTestId('detection-updated-at-value');
      expect(timestampValue).toHaveAttribute('dir', 'ltr');
      expect(timestampValue).not.toHaveTextContent(/\b(?:AM|PM)\b/);
    } finally {
      await i18n.changeLanguage('en');
    }
  });

  it('submits updated config when inputs are valid', async () => {
    let putPayload: unknown = null;
    server.use(
      http.get('/api/v1/admin/detection/config', () => {
        return HttpResponse.json(
          { block_confidence: 0.8, flag_confidence: 0.5, updated_at: '2026-06-22T00:00:00Z' },
          { status: 200 }
        );
      }),
      http.put('/api/v1/admin/detection/config', async ({ request }) => {
        putPayload = await request.json();
        return HttpResponse.json(
          { block_confidence: 0.9, flag_confidence: 0.6, updated_at: '2026-06-23T00:00:00Z' },
          { status: 200 }
        );
      })
    );

    renderWithClient(<AdminDetectionPage />);

    const blockInput = await screen.findByRole('slider', { name: /block/i });
    const flagInput = await screen.findByRole('slider', { name: /flag/i });
    const saveButton = screen.getByRole('button', { name: /save/i });

    // Change values
    fireEvent.change(blockInput, { target: { value: '0.9' } });
    fireEvent.change(flagInput, { target: { value: '0.6' } });

    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(putPayload).toEqual({
        block_confidence: 0.9,
        flag_confidence: 0.6,
      });
    });
  });

  it('renders validation error when block threshold is less than or equal to flag threshold', async () => {
    server.use(
      http.get('/api/v1/admin/detection/config', () => {
        return HttpResponse.json(
          { block_confidence: 0.8, flag_confidence: 0.5, updated_at: '2026-06-22T00:00:00Z' },
          { status: 200 }
        );
      })
    );

    renderWithClient(<AdminDetectionPage />);

    const blockInput = await screen.findByRole('slider', { name: /block/i });
    const flagInput = await screen.findByRole('slider', { name: /flag/i });
    const saveButton = screen.getByRole('button', { name: /save/i });

    // Set block <= flag (e.g. block = 0.5, flag = 0.6)
    fireEvent.change(blockInput, { target: { value: '0.5' } });
    fireEvent.change(flagInput, { target: { value: '0.6' } });

    fireEvent.click(saveButton);

    const errorMsg = await screen.findByText(/greater than/i);
    expect(errorMsg).toBeInTheDocument();
  });

  it('renders localized access-denied state without raw backend error text', async () => {
    server.use(
      http.get('/api/v1/admin/detection/config', () => {
        return HttpResponse.json(
          {
            message_key: 'error.forbidden',
            error: 'Forbidden raw_payload confidence=0.99 stack=trace',
          },
          { status: 403 }
        );
      })
    );

    const { container } = renderWithClient(<AdminDetectionPage />);

    expect(await screen.findByTestId('access-denied-error')).toHaveTextContent(
      'This request was blocked for security reasons.'
    );
    expect(container).not.toHaveTextContent('Forbidden');
    expect(container).not.toHaveTextContent('raw_payload');
    expect(container).not.toHaveTextContent('confidence=0.99');
    expect(container).not.toHaveTextContent('stack=trace');
  });

  it('renders with RTL direction and verified logical classes without physical inline styles', async () => {
    server.use(
      http.get('/api/v1/admin/detection/config', () => {
        return HttpResponse.json(
          { block_confidence: 0.8, flag_confidence: 0.5, updated_at: '2026-06-22T00:00:00Z' },
          { status: 200 }
        );
      })
    );

    const { container } = renderWithClient(
      <div dir="rtl">
        <AdminDetectionPage />
      </div>
    );

    // Wait for content
    await screen.findByRole('slider', { name: /block/i });

    expect(container.firstChild).toHaveAttribute('dir', 'rtl');

    const allElements = container.querySelectorAll('*');
    allElements.forEach((el) => {
      const style = el.getAttribute('style') || '';
      expect(style).not.toContain('text-align' + ': left');
      expect(style).not.toContain('text-align' + ': right');
      expect(style).not.toContain('margin-left');
      expect(style).not.toContain('margin-right');
      expect(style).not.toContain('padding-left');
      expect(style).not.toContain('padding-right');
    });
  });
});

const VALID_CONFIG = {
  block_confidence: 0.8,
  flag_confidence: 0.5,
  updated_at: '2026-06-22T00:00:00Z',
};

function mockConfigGet(
  body: unknown = VALID_CONFIG,
  status = 200
) {
  return http.get('/api/v1/admin/detection/config', () =>
    HttpResponse.json(body, { status })
  );
}

function trackConfigPuts(respond: () => Promise<HttpResponse> | HttpResponse) {
  let putCount = 0;
  return {
    get count() {
      return putCount;
    },
    handler: http.put('/api/v1/admin/detection/config', async () => {
      putCount += 1;
      return await respond();
    }),
  };
}

function setNativeValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype,
    'value'
  )?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}

async function renderDetectionPage() {
  server.use(mockConfigGet());
  const rendered = renderWithClient(<AdminDetectionPage />);
  const blockInput = (await screen.findByRole('spinbutton', {
    name: /block threshold/i,
  })) as HTMLInputElement;
  const flagInput = screen.getByRole('spinbutton', {
    name: /flag threshold/i,
  }) as HTMLInputElement;
  return { ...rendered, blockInput, flagInput };
}

describe('detection form boundary (IS-GAP-040)', () => {
  it.each([
    ['NaN text bypass', 'abc'],
    ['positive infinity bypass', '1e999'],
    ['negative infinity bypass', '-1e999'],
    ['below zero', '-0.5'],
    ['above one', '1.5'],
  ])('blocks %s with zero mutation requests and announces the error', async (_name, raw) => {
    const puts = trackConfigPuts(() => HttpResponse.json(VALID_CONFIG));
    server.use(puts.handler);
    const { blockInput } = await renderDetectionPage();

    fireEvent.change(blockInput, { target: { value: raw } });
    fireEvent.submit(blockInput.closest('form')!);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/between 0 and 1/);

    for (const input of [blockInput, screen.getByRole('spinbutton', { name: /flag threshold/i })]) {
      expect(input).toHaveAttribute('aria-invalid', 'true');
      const describedBy = input.getAttribute('aria-describedby');
      expect(describedBy).toBeTruthy();
      expect(document.getElementById(describedBy!)).toHaveTextContent(/between 0 and 1/);
    }
    expect(puts.count).toBe(0);
  });

  it.each([
    ['equal thresholds', '0.7', '0.7'],
    ['inverted thresholds', '0.5', '0.8'],
  ])('blocks %s with zero mutation requests', async (_name, block, flag) => {
    const puts = trackConfigPuts(() => HttpResponse.json(VALID_CONFIG));
    server.use(puts.handler);
    const { blockInput, flagInput } = await renderDetectionPage();

    fireEvent.change(blockInput, { target: { value: block } });
    fireEvent.change(flagInput, { target: { value: flag } });
    fireEvent.submit(blockInput.closest('form')!);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Block threshold must be greater than flag threshold'
    );
    expect(puts.count).toBe(0);
  });

  it('blocks direct DOM property bypass values before mutation', async () => {
    const puts = trackConfigPuts(() => HttpResponse.json(VALID_CONFIG));
    server.use(puts.handler);
    const { blockInput } = await renderDetectionPage();

    setNativeValue(blockInput, '2');
    fireEvent.submit(blockInput.closest('form')!);

    expect(await screen.findByRole('alert')).toHaveTextContent(/between 0 and 1/);
    expect(puts.count).toBe(0);
  });

  it('saves exact valid boundary values successfully once', async () => {
    let payload: unknown = null;
    server.use(
      http.put('/api/v1/admin/detection/config', async ({ request }) => {
        payload = await request.json();
        return HttpResponse.json({
          ...VALID_CONFIG,
          block_confidence: 1,
          flag_confidence: 0,
        });
      })
    );
    const { blockInput, flagInput } = await renderDetectionPage();

    fireEvent.change(blockInput, { target: { value: '1' } });
    fireEvent.change(flagInput, { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: /save configuration/i }));

    await waitFor(() => {
      expect(payload).toEqual({ block_confidence: 1, flag_confidence: 0 });
    });
    expect(
      await screen.findByText('Changes saved successfully')
    ).toBeInTheDocument();
  });

  it('fails closed on a malformed initial config response with a localized retry state', async () => {
    server.use(
      mockConfigGet({ block_confidence: 'oops', flag_confidence: null })
    );
    renderWithClient(<AdminDetectionPage />);

    expect(
      await screen.findByText(
        'The server returned an invalid response. Please try again.'
      )
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument();
  });

  it('fails closed on a malformed save response while preserving valid edits', async () => {
    const puts = trackConfigPuts(() =>
      HttpResponse.json({ block_confidence: 2 }, { status: 200 })
    );
    server.use(puts.handler);
    const { blockInput, flagInput } = await renderDetectionPage();

    fireEvent.change(blockInput, { target: { value: '0.9' } });
    fireEvent.change(flagInput, { target: { value: '0.6' } });
    fireEvent.click(screen.getByRole('button', { name: /save configuration/i }));

    const toast = await screen.findByRole('alert', {
      name: /failed to save configuration/i,
    });
    expect(toast).toBeInTheDocument();
    expect(document.body.textContent).not.toContain('client_contract_invalid_response');

    expect(blockInput).toHaveValue('0.9');
    expect(flagInput).toHaveValue('0.6');

    server.resetHandlers();
    server.use(mockConfigGet(), trackConfigPuts(() => HttpResponse.json(VALID_CONFIG)).handler);
    fireEvent.click(screen.getByRole('button', { name: /save configuration/i }));
    expect(await screen.findByText('Changes saved successfully')).toBeInTheDocument();
  });

  it('shows a sanitized localized rejection and preserves edits after a server 422', async () => {
    let rejectedOnce = false;
    server.use(
      http.put('/api/v1/admin/detection/config', async ({ request }) => {
        if (!rejectedOnce) {
          rejectedOnce = true;
          return HttpResponse.json(
            {
              detail: [
                {
                  loc: ['body', 'block_confidence'],
                  msg: 'Input should be less than or equal to 1',
                  type: 'less_than_equal',
                },
              ],
            },
            { status: 422 }
          );
        }
        void request;
        return HttpResponse.json({ ...VALID_CONFIG, block_confidence: 0.9 });
      })
    );
    const { blockInput, flagInput } = await renderDetectionPage();

    fireEvent.change(blockInput, { target: { value: '0.9' } });
    fireEvent.change(flagInput, { target: { value: '0.85' } });
    fireEvent.click(screen.getByRole('button', { name: /save configuration/i }));

    expect(
      await screen.findByRole('alert', { name: /failed to save configuration/i })
    ).toBeInTheDocument();
    expect(document.body.textContent).not.toContain('less_than_equal');
    expect(document.body.textContent).not.toContain('greater_than_equal');
    expect(blockInput).toHaveValue('0.9');
    expect(flagInput).toHaveValue('0.85');
    expect(blockInput).not.toHaveAttribute('aria-invalid');

    fireEvent.click(screen.getByRole('button', { name: /save configuration/i }));
    expect(await screen.findByText('Changes saved successfully')).toBeInTheDocument();
  });

  it('reset restores authoritative values, clears errors, and issues no mutations', async () => {
    const puts = trackConfigPuts(() => HttpResponse.json(VALID_CONFIG));
    server.use(puts.handler);
    const { blockInput, flagInput } = await renderDetectionPage();

    fireEvent.change(blockInput, { target: { value: '2' } });
    fireEvent.submit(blockInput.closest('form')!);
    await screen.findByRole('alert');

    fireEvent.click(screen.getByRole('button', { name: /reset/i }));

    expect(blockInput).toHaveValue('0.8');
    expect(flagInput).toHaveValue('0.5');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(blockInput).not.toHaveAttribute('aria-invalid');
    expect(puts.count).toBe(0);
  });

  it('suppresses duplicate submissions while a save is pending', async () => {
    let settled = false;
    const puts = trackConfigPuts(async () => {
      await new Promise((resolve) => setTimeout(resolve, 120));
      settled = true;
      return HttpResponse.json(VALID_CONFIG);
    });
    server.use(puts.handler);
    const { blockInput, flagInput } = await renderDetectionPage();

    fireEvent.change(blockInput, { target: { value: '0.9' } });
    fireEvent.change(flagInput, { target: { value: '0.6' } });
    fireEvent.click(screen.getByRole('button', { name: /save configuration/i }));
    fireEvent.submit(blockInput.closest('form')!);

    expect(screen.getByRole('status')).toHaveTextContent(/saving/i);
    await waitFor(() => expect(settled).toBe(true));
    await screen.findByText('Changes saved successfully');
    expect(puts.count).toBe(1);
  });

  it('localizes the range error and reset control in Arabic', async () => {
    const puts = trackConfigPuts(() => HttpResponse.json(VALID_CONFIG));
    server.use(puts.handler);
    await i18n.changeLanguage('ar');
    try {
      const { blockInput } = await renderDetectionPage();
      fireEvent.change(blockInput, { target: { value: '2' } });
      fireEvent.submit(blockInput.closest('form')!);

      const arabicError = await screen.findByText(
        'يجب أن يكون كل حد رقمًا بين 0 و1.'
      );
      expect(arabicError).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'إعادة تعيين' })).toBeInTheDocument();
      expect(puts.count).toBe(0);
    } finally {
      await i18n.changeLanguage('en');
    }
  });
});
