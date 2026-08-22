import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ShikiHighlighter } from '../ShikiHighlighter';

/**
 * CHUNK-21 / IS-GAP-031 — a rejected Shiki highlighter construction must not
 * produce an unhandled rejection or an empty island; the SQL stays readable.
 */
vi.mock('shiki', () => ({
  createHighlighter: vi.fn(() => Promise.reject(new Error('wasm/language bundle unavailable'))),
}));

describe('ShikiHighlighter internal failure', () => {
  it('renders readable plain text without unhandled rejections or raw detail', async () => {
    const unhandled: unknown[] = [];
    const handler = (event: PromiseRejectionEvent) => unhandled.push(event.reason);
    window.addEventListener('unhandledrejection', handler);

    render(<ShikiHighlighter code="SELECT 1;" />);

    expect(await screen.findByText('SELECT 1;')).toBeInTheDocument();
    await waitFor(() => expect(unhandled).toEqual([]));
    expect(screen.queryByText(/wasm|bundle/i)).not.toBeInTheDocument();

    window.removeEventListener('unhandledrejection', handler);
  });
});
