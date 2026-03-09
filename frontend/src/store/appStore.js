// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const useAppStore = create(
  persist(
    (set) => ({
      auth: { token: null, user: null, isAuthenticated: false },
      license: { tier: 'trial', expiresAt: null, isValid: false },
      devices: [],
      language: 'en',

      login: (token, user) =>
        set({ auth: { token, user, isAuthenticated: true } }),

      logout: () =>
        set({ auth: { token: null, user: null, isAuthenticated: false } }),

      setLicense: (license) => set({ license }),

      setDevices: (devices) => set({ devices }),

      setLanguage: (language) => set({ language }),
    }),
    {
      name: 'omninet-store',
      partialize: (state) => ({ auth: state.auth, language: state.language }),
    }
  )
)

export default useAppStore
