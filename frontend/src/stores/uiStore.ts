import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UIState {
  sidebarCollapsed: boolean;
  activeSessionId: string | null;
  hoveredSessionId: string | null;
  promptDraft: string;
  toggleSidebar: () => void;
  setActiveSessionId: (id: string | null) => void;
  setHoveredSessionId: (id: string | null) => void;
  setPromptDraft: (draft: string) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      activeSessionId: null,
      hoveredSessionId: null,
      promptDraft: '',
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setActiveSessionId: (id) => set({ activeSessionId: id }),
      setHoveredSessionId: (id) => set({ hoveredSessionId: id }),
      setPromptDraft: (draft) => set({ promptDraft: draft }),
    }),
    {
      name: 'querycraft-ui',
      partialize: (state) => ({ sidebarCollapsed: state.sidebarCollapsed }),
    }
  )
);
