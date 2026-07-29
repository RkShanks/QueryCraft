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
