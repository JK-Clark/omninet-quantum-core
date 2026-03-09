// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// frontend/src/__tests__/App.test.jsx — Smoke test: App renders without crashing

import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'

// Mock react-router-dom to avoid MemoryRouter/BrowserRouter issues in jsdom
vi.mock('react-router-dom', () => ({
  BrowserRouter: ({ children }) => <div>{children}</div>,
  Routes: ({ children }) => <div>{children}</div>,
  Route: () => null,
  Navigate: () => null,
  useNavigate: () => vi.fn(),
  useLocation: () => ({ pathname: '/' }),
}))

// Mock zustand store
vi.mock('../store/appStore', () => ({
  default: (selector) =>
    selector({
      auth: { isAuthenticated: false, token: null, user: null },
      license: { status: null },
    }),
}))

import App from '../App'

describe('App', () => {
  it('renders without crashing', () => {
    const { container } = render(<App />)
    expect(container).toBeTruthy()
  })
})
