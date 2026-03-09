// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
// frontend/src/__tests__/App.test.jsx — Minimal smoke test for the App component

import React from 'react'
import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'

// Mock react-router-dom to avoid needing a real browser environment
vi.mock('react-router-dom', () => ({
  BrowserRouter: ({ children }) => <div>{children}</div>,
  Routes: ({ children }) => <div>{children}</div>,
  Route: () => null,
  Navigate: () => null,
}))

// Mock zustand store to return a predictable unauthenticated state
vi.mock('../store/appStore', () => ({
  default: (selector) =>
    selector({
      auth: { token: null, user: null, isAuthenticated: false },
      license: { tier: 'trial', expiresAt: null, isValid: false },
      devices: [],
      language: 'en',
    }),
}))

// Mock page components to avoid pulling in the full component tree
vi.mock('../pages/LoginPage', () => ({ default: () => <div>LoginPage</div> }))
vi.mock('../pages/SetupWizard', () => ({ default: () => <div>SetupWizard</div> }))
vi.mock('../pages/Dashboard', () => ({ default: () => <div>Dashboard</div> }))
vi.mock('../pages/AIPredictor', () => ({ default: () => <div>AIPredictor</div> }))
vi.mock('../components/LicenseGuard', () => ({ default: ({ children }) => <div>{children}</div> }))

import App from '../App'

describe('App', () => {
  it('renders without crashing', () => {
    const { container } = render(<App />)
    expect(container).toBeTruthy()
  })
})
