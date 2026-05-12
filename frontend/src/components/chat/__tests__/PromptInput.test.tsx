import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PromptInput } from '../PromptInput';

describe('PromptInput', () => {
  it('renders textarea with placeholder', () => {
    render(<PromptInput onSubmit={vi.fn()} />);
    expect(screen.getByPlaceholderText('Ask a question about your data...')).toBeInTheDocument();
  });

  it('submits on Enter key', () => {
    const onSubmit = vi.fn();
    render(<PromptInput onSubmit={onSubmit} />);
    const textarea = screen.getByPlaceholderText('Ask a question about your data...') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Hello' } });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    expect(onSubmit).toHaveBeenCalledWith('Hello');
  });

  it('does not submit on Shift+Enter', () => {
    const onSubmit = vi.fn();
    render(<PromptInput onSubmit={onSubmit} />);
    const textarea = screen.getByPlaceholderText('Ask a question about your data...') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Hello' } });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('submits on Send button click', () => {
    const onSubmit = vi.fn();
    render(<PromptInput onSubmit={onSubmit} />);
    const textarea = screen.getByPlaceholderText('Ask a question about your data...') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Hello' } });
    fireEvent.click(screen.getByTestId('prompt-send'));
    expect(onSubmit).toHaveBeenCalledWith('Hello');
  });

  it('has Send button positioned with logical end property', () => {
    render(<PromptInput onSubmit={vi.fn()} />);
    const sendBtn = screen.getByTestId('prompt-send');
    expect(sendBtn).toBeInTheDocument();
    expect(sendBtn.className).toContain('prompt-input-send');
  });

  it('disables send button when empty', () => {
    render(<PromptInput onSubmit={vi.fn()} />);
    expect(screen.getByTestId('prompt-send')).toBeDisabled();
  });

  it('enables send button when text is entered', () => {
    render(<PromptInput onSubmit={vi.fn()} />);
    const textarea = screen.getByPlaceholderText('Ask a question about your data...') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Hello' } });
    expect(screen.getByTestId('prompt-send')).not.toBeDisabled();
  });

  it('clears textarea after submit', () => {
    const onSubmit = vi.fn();
    render(<PromptInput onSubmit={onSubmit} />);
    const textarea = screen.getByPlaceholderText('Ask a question about your data...') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: 'Hello' } });
    fireEvent.click(screen.getByTestId('prompt-send'));
    expect(textarea.value).toBe('');
  });

  it('respects disabled prop', () => {
    render(<PromptInput onSubmit={vi.fn()} disabled />);
    const textarea = screen.getByPlaceholderText('Ask a question about your data...') as HTMLTextAreaElement;
    expect(textarea).toBeDisabled();
    expect(screen.getByTestId('prompt-send')).toBeDisabled();
  });
});
