// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AppState {
  accessToken: string | null;
  refreshToken: string | null;
  username: string | null;
  licenseTier: string;
  setupComplete: boolean;

  setTokens: (access: string, refresh: string) => void;
  setUsername: (u: string) => void;
  setLicenseTier: (t: string) => void;
  setSetupComplete: (v: boolean) => void;
  logout: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      username: null,
      licenseTier: 'TRIAL',
      setupComplete: false,

      setTokens: (access, refresh) =>
        set({ accessToken: access, refreshToken: refresh }),
      setUsername: (u) => set({ username: u }),
      setLicenseTier: (t) => set({ licenseTier: t }),
      setSetupComplete: (v) => set({ setupComplete: v }),
      logout: () =>
        set({
          accessToken: null,
          refreshToken: null,
          username: null,
          setupComplete: false,
        }),
    }),
    { name: 'omninet-store' }
  )
);
