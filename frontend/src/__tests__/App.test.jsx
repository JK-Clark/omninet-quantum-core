// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// frontend/src/__tests__/App.test.jsx — Minimal smoke test: App renders without crashing

import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import React from 'react'

// ── Mock react-router-dom ─────────────────────────────────────────────────────
vi.mock('react-router-dom', () => ({
  BrowserRouter: ({ children }) => <div>{children}</div>,
  Routes: ({ children }) => <div>{children}</div>,
  Route: () => null,
  Navigate: () => null,
}))

// ── Mock zustand store ────────────────────────────────────────────────────────
vi.mock('../store/appStore', () => ({
  default: (selector) =>
    selector({
      auth: { isAuthenticated: false, token: null, user: null },
      license: { tier: 'trial', isActive: true },
    }),
}))

// ── Mock page components to avoid deep dependency chains ─────────────────────
vi.mock('../pages/LoginPage', () => ({ default: () => <div>LoginPage</div> }))
vi.mock('../pages/SetupWizard', () => ({ default: () => <div>SetupWizard</div> }))
vi.mock('../pages/Dashboard', () => ({ default: () => <div>Dashboard</div> }))
vi.mock('../pages/AIPredictor', () => ({ default: () => <div>AIPredictor</div> }))
vi.mock('../components/LicenseGuard', () => ({ default: ({ children }) => <>{children}</> }))

import App from '../App'

describe('App', () => {
  it('renders without crashing', () => {
    const { container } = render(<App />)
    expect(container).toBeTruthy()
  })
})
