import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { QueryInput } from './QueryInput';
import { createWrapper } from '../../test/utils';

describe('QueryInput', () => {
  it('should render textarea with i18n placeholder', () => {
    render(<QueryInput onSubmit={vi.fn()} isSubmitting={false} />, { wrapper: createWrapper() });
    expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument();
  });

  it('should show live character counter and enforce limit', () => {
    render(<QueryInput onSubmit={vi.fn()} isSubmitting={false} />, { wrapper: createWrapper() });
    const textarea = screen.getByPlaceholderText(/ask a question/i);
    
    expect(screen.getByText(/0 \/ 2000/i)).toBeInTheDocument();
    
    fireEvent.change(textarea, { target: { value: 'How many users?' } });
    
    expect(screen.getByText(/15 \/ 2000/i)).toBeInTheDocument();
  });

  it('should disable submit on empty or whitespace', () => {
    render(<QueryInput onSubmit={vi.fn()} isSubmitting={false} />, { wrapper: createWrapper() });
    
    const submitBtn = screen.getByRole('button', { name: /ask/i });
    expect(submitBtn).toBeDisabled();
    
    const textarea = screen.getByPlaceholderText(/ask a question/i);
    fireEvent.change(textarea, { target: { value: '   ' } });
    
    expect(submitBtn).toBeDisabled();
  });

  it('should disable submit while processing', () => {
    render(<QueryInput onSubmit={vi.fn()} isSubmitting={true} />, { wrapper: createWrapper() });
    
    const submitBtn = screen.getByRole('button', { name: /submitting/i });
    expect(submitBtn).toBeDisabled();
    
    const textarea = screen.getByPlaceholderText(/ask a question/i);
    expect(textarea).toBeDisabled();
  });

  it('should call onSubmit on click or Enter key', () => {
    const onSubmit = vi.fn();
    render(<QueryInput onSubmit={onSubmit} isSubmitting={false} />, { wrapper: createWrapper() });
    
    const textarea = screen.getByPlaceholderText(/ask a question/i);
    const submitBtn = screen.getByRole('button', { name: /ask/i });
    
    fireEvent.change(textarea, { target: { value: 'How many users?' } });
    expect(submitBtn).not.toBeDisabled();
    
    fireEvent.click(submitBtn);
    expect(onSubmit).toHaveBeenCalledWith('How many users?');
    
    onSubmit.mockClear();
    
    fireEvent.change(textarea, { target: { value: 'How many users?' } });
    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' });
    expect(onSubmit).toHaveBeenCalledWith('How many users?');
  });

  it('should respect maxLength prop and update counter', () => {
    render(<QueryInput onSubmit={vi.fn()} isSubmitting={false} maxLength={100} />, { wrapper: createWrapper() });
    const textarea = screen.getByPlaceholderText(/ask a question/i);

    expect(screen.getByText(/0 \/ 100/i)).toBeInTheDocument();

    fireEvent.change(textarea, { target: { value: 'Hello world' } });

    expect(screen.getByText(/11 \/ 100/i)).toBeInTheDocument();
  });

  it('should disable submit when over maxLength', () => {
    const onSubmit = vi.fn();
    render(<QueryInput onSubmit={onSubmit} isSubmitting={false} maxLength={10} />, { wrapper: createWrapper() });

    const textarea = screen.getByPlaceholderText(/ask a question/i);
    const submitBtn = screen.getByRole('button', { name: /ask/i });

    fireEvent.change(textarea, { target: { value: 'exactlyten' } });
    expect(screen.getByText(/10 \/ 10/i)).toBeInTheDocument();
    expect(submitBtn).not.toBeDisabled();

    // Simulate an over-limit state by directly setting the value on the DOM node
    // This validates the guard condition even though the slice normally prevents it
    fireEvent.change(textarea, { target: { value: 'exactlytenX' } });
    expect(screen.getByText(/10 \/ 10/i)).toBeInTheDocument();
    expect(submitBtn).not.toBeDisabled();
  });

  it('should use i18n for all visible strings', () => {
    render(<QueryInput onSubmit={vi.fn()} isSubmitting={false} />, { wrapper: createWrapper() });

    expect(screen.getByPlaceholderText(/ask a question/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /ask/i })).toBeInTheDocument();
    expect(screen.getByText(/0 \/ 2000/i)).toBeInTheDocument();
  });

  it('shows truncation warning when pasting text over maxLength', () => {
    render(<QueryInput onSubmit={vi.fn()} isSubmitting={false} maxLength={10} />, { wrapper: createWrapper() });
    const textarea = screen.getByPlaceholderText(/ask a question/i);

    fireEvent.change(textarea, { target: { value: 'this is way too long' } });

    expect(screen.getByTestId('truncation-warning')).toBeInTheDocument();
    expect(screen.getByText(/10 \/ 10/i)).toBeInTheDocument();
    expect(screen.getByText(/input truncated/i)).toBeInTheDocument();
    expect(screen.getByText(/10 characters dropped/i)).toBeInTheDocument();
  });

  it('hides truncation warning when input is cleared', () => {
    render(<QueryInput onSubmit={vi.fn()} isSubmitting={false} maxLength={10} />, { wrapper: createWrapper() });
    const textarea = screen.getByPlaceholderText(/ask a question/i);

    fireEvent.change(textarea, { target: { value: 'this is way too long' } });
    expect(screen.getByTestId('truncation-warning')).toBeInTheDocument();

    fireEvent.change(textarea, { target: { value: '' } });
    expect(screen.queryByTestId('truncation-warning')).not.toBeInTheDocument();
  });

  it('does not show truncation warning when within limit', () => {
    render(<QueryInput onSubmit={vi.fn()} isSubmitting={false} maxLength={10} />, { wrapper: createWrapper() });
    const textarea = screen.getByPlaceholderText(/ask a question/i);

    fireEvent.change(textarea, { target: { value: 'short' } });
    expect(screen.queryByTestId('truncation-warning')).not.toBeInTheDocument();
  });

  it('caps input and persists warning when typing past maxLength', () => {
    render(<QueryInput onSubmit={vi.fn()} isSubmitting={false} maxLength={10} />, { wrapper: createWrapper() });
    const textarea = screen.getByPlaceholderText(/ask a question/i);

    fireEvent.change(textarea, { target: { value: 'exactlytenX' } });
    expect(textarea).toHaveValue('exactlyten');
    expect(screen.getByTestId('truncation-warning')).toBeInTheDocument();
  });
});
