import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AuthUser, ViewKey } from '../types';

interface AppState {
  // Authentication State
  token: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
  
  // Navigation & View State
  currentView: ViewKey;
  activeSourceIds: string[];
  
  // Actions
  setAuth: (token: string, refreshToken: string, user: AuthUser) => void;
  clearAuth: () => void;
  setCurrentView: (view: ViewKey) => void;
  toggleSource: (id: string | null) => void;
  selectSource: (id: string | null, view?: ViewKey) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      token: null,
      refreshToken: null,
      user: null,
      currentView: 'about',
      activeSourceIds: [],
      
      setAuth: (token, refreshToken, user) => set({ token, refreshToken, user }),
      
      clearAuth: () => set({ token: null, refreshToken: null, user: null }),
      
      setCurrentView: (view) => set({ currentView: view }),
      
      toggleSource: (id) => set((state) => {
        if (!id) return { activeSourceIds: [] };
        const isActive = state.activeSourceIds.includes(id);
        return {
          activeSourceIds: isActive 
            ? state.activeSourceIds.filter((i) => i !== id)
            : [...state.activeSourceIds, id]
        };
      }),
      
      selectSource: (id, view) => set((state) => ({
        activeSourceIds: id ? [id] : [],
        currentView: view || state.currentView
      })),
    }),
    {
      name: 'insightify-storage', // unique name
      partialize: (state) => ({ 
        token: state.token, 
        refreshToken: state.refreshToken, 
        user: state.user 
        // We don't persist activeSourceIds or currentView to avoid stale state on reload
      }),
    }
  )
);
