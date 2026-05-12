import { describe, it, expect, beforeEach } from 'vitest';
import { useUIStore } from '../../stores/uiStore';

describe('uiStore', () => {
  beforeEach(() => {
    // Reset store to default state before each test
    const store = useUIStore.getState();
    store.setActiveSessionId(null);
    store.setHoveredSessionId(null);
    store.setPromptDraft('');
    if (store.sidebarCollapsed) {
      store.toggleSidebar();
    }
  });

  it('has correct default state', () => {
    const state = useUIStore.getState();
    expect(state.sidebarCollapsed).toBe(false);
    expect(state.activeSessionId).toBeNull();
    expect(state.hoveredSessionId).toBeNull();
    expect(state.promptDraft).toBe('');
  });

  it('toggles sidebarCollapsed', () => {
    const store = useUIStore.getState();
    store.toggleSidebar();
    expect(useUIStore.getState().sidebarCollapsed).toBe(true);
    store.toggleSidebar();
    expect(useUIStore.getState().sidebarCollapsed).toBe(false);
  });

  it('sets activeSessionId', () => {
    useUIStore.getState().setActiveSessionId('sess-123');
    expect(useUIStore.getState().activeSessionId).toBe('sess-123');
  });

  it('sets hoveredSessionId', () => {
    useUIStore.getState().setHoveredSessionId('sess-456');
    expect(useUIStore.getState().hoveredSessionId).toBe('sess-456');
  });

  it('sets promptDraft', () => {
    useUIStore.getState().setPromptDraft('Hello world');
    expect(useUIStore.getState().promptDraft).toBe('Hello world');
  });
});
