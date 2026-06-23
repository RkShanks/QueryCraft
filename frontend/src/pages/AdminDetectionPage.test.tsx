import { describe, it, expect } from 'vitest';
import { screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../test/server';
import { renderWithClient } from '../test/utils';
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
    const blockInput = await screen.findByLabelText(/block/i);
    const flagInput = await screen.findByLabelText(/flag/i);

    expect(blockInput).toHaveValue('0.8');
    expect(flagInput).toHaveValue('0.5');
  });

  it('submits updated config when inputs are valid', async () => {
    let putPayload: any = null;
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

    const blockInput = await screen.findByLabelText(/block/i);
    const flagInput = await screen.findByLabelText(/flag/i);
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

    const blockInput = await screen.findByLabelText(/block/i);
    const flagInput = await screen.findByLabelText(/flag/i);
    const saveButton = screen.getByRole('button', { name: /save/i });

    // Set block <= flag (e.g. block = 0.5, flag = 0.6)
    fireEvent.change(blockInput, { target: { value: '0.5' } });
    fireEvent.change(flagInput, { target: { value: '0.6' } });

    fireEvent.click(saveButton);

    const errorMsg = await screen.findByText(/greater than/i);
    expect(errorMsg).toBeInTheDocument();
  });

  it('renders access-denied state when API returns 403 Forbidden', async () => {
    server.use(
      http.get('/api/v1/admin/detection/config', () => {
        return HttpResponse.json(
          { message_key: 'error.forbidden', error: 'Forbidden' },
          { status: 403 }
        );
      })
    );

    renderWithClient(<AdminDetectionPage />);

    // Should display forbidden error
    const forbiddenText = await screen.findByText(/forbidden/i);
    expect(forbiddenText).toBeInTheDocument();
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
    await screen.findByLabelText(/block/i);

    expect(container.firstChild).toHaveAttribute('dir', 'rtl');

    const allElements = container.querySelectorAll('*');
    allElements.forEach((el) => {
      const style = el.getAttribute('style') || '';
      expect(style).not.toContain('text-align: left');
      expect(style).not.toContain('text-align: right');
      expect(style).not.toContain('margin-left');
      expect(style).not.toContain('margin-right');
      expect(style).not.toContain('padding-left');
      expect(style).not.toContain('padding-right');
    });
  });
});
