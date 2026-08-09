import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIState {
  sidebarCollapsed: boolean;
  activeSessionId: string | null;
  hoveredSessionId: string | null;
  promptDraft: string;
  toggleSidebar: () => void;
  collapseSidebar: () => void;
  setActiveSessionId: (id: string | null) => void;
  setHoveredSessionId: (id: string | null) => void;
  setPromptDraft: (draft: string) => void;
  resetIdentityState: () => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      activeSessionId: null,
      hoveredSessionId: null,
      promptDraft: '',
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      collapseSidebar: () => set({ sidebarCollapsed: true }),
      setActiveSessionId: (id) => set({ activeSessionId: id }),
      setHoveredSessionId: (id) => set({ hoveredSessionId: id }),
      setPromptDraft: (draft) => set({ promptDraft: draft }),
      resetIdentityState: () => set({
        activeSessionId: null,
        hoveredSessionId: null,
        promptDraft: '',
      }),
    }),
    {
      name: 'querycraft-ui',
      partialize: (state) => ({ sidebarCollapsed: state.sidebarCollapsed }),
    }
  )
);
