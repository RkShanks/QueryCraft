import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeAll } from 'vitest';
import { SignInPage } from './SignInPage';
import { createWrapper } from '../test/utils';
import { http, HttpResponse } from 'msw';
import { server } from '../test/server';

describe('SignInPage', () => {
  beforeAll(() => {
    server.use(
      http.get('/api/v1/auth/me', () => {
        return new HttpResponse(null, { status: 401 });
      })
    );
  });

  it('renders branded premium layout with title and subtitle', async () => {
    render(<SignInPage />, { wrapper: createWrapper() });
    
    // Wait for the page to finish loading and show the sign in text
    await screen.findByRole('heading', { name: /Sign In/i });

    // These premium branding elements should fail to be found on the unpolished page (RED step)
    expect(screen.getByRole('heading', { name: /QueryCraft/i, level: 1 })).toBeInTheDocument();
    expect(screen.getByText(/Text-to-SQL Analytics Platform/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Sign In/i, level: 2 })).toBeInTheDocument();
  });
});
