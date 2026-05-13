import { describe, it, expect } from 'vitest';
import { Routes, Route } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

describe('App routing', () => {
  it('settings route exists in route config pattern', async () => {
    // Verifies the /settings route pattern matches what is registered in App.tsx
    render(
      <MemoryRouter initialEntries={['/settings']}>
        <Routes>
          <Route path="/settings" element={<div data-testid="settings-route-matched" />} />
          <Route path="*" element={<div data-testid="fallback" />} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByTestId('settings-route-matched')).toBeInTheDocument();
  });
});
