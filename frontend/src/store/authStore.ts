// src/store/authStore.ts
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "../types";

interface AuthState {
  accessToken: string | null;
  user: User | null;
  setAccessToken: (token: string) => void;
  setUser: (user: User) => void;
  logout: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      user: null,

      setAccessToken: (token) => set({ accessToken: token }),
      setUser: (user) => set({ user }),

      logout: () => set({ accessToken: null, user: null }),

      isAuthenticated: () => !!get().accessToken,
    }),
    {
      name: "clipsense-auth",
      partialize: (state) => ({ user: state.user }), // Only persist user, not token
    }
  )
);
