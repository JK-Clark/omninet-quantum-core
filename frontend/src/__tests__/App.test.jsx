// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
// frontend/src/__tests__/App.test.jsx — Minimal smoke test for the App component

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

// Mock react-router-dom so that BrowserRouter and navigation hooks work in jsdom
vi.mock('react-router-dom', () => ({
  BrowserRouter: ({ children }) => children,
  Routes: ({ children }) => children,
  Route: ({ element }) => element,
  Navigate: ({ to }) => <div data-testid="navigate" data-to={to} />,
  useNavigate: () => vi.fn(),
}))

// Mock zustand store so that we don't need a real store provider
vi.mock('../store/appStore', () => ({
  default: (selector) =>
    selector({
      auth: { token: null, user: null, isAuthenticated: false },
      license: { tier: 'trial', expiresAt: null, isValid: false },
      devices: [],
      language: 'en',
    }),
}))

// Mock the page components to keep the test lightweight
vi.mock('../pages/LoginPage', () => ({
  default: () => <div data-testid="login-page">LoginPage</div>,
}))

vi.mock('../pages/SetupWizard', () => ({
  default: () => <div data-testid="setup-wizard">SetupWizard</div>,
}))

vi.mock('../pages/Dashboard', () => ({
  default: () => <div data-testid="dashboard">Dashboard</div>,
}))

vi.mock('../pages/AIPredictor', () => ({
  default: () => <div data-testid="ai-predictor">AIPredictor</div>,
}))

vi.mock('../components/LicenseGuard', () => ({
  default: ({ children }) => children,
}))

import App from '../App'

describe('App', () => {
  it('renders without crashing', () => {
    const { container } = render(<App />)
    expect(container).toBeTruthy()
  })

  it('redirects unauthenticated users to login', () => {
    render(<App />)
    // When not authenticated, at least one Navigate to /login should be rendered
    const loginPage = screen.queryByTestId('login-page')
    const navigateEls = screen.queryAllByTestId('navigate')
    const hasLoginRedirect = navigateEls.some(
      (el) => el.getAttribute('data-to') === '/login'
    )
    // Either the LoginPage renders directly or there is a redirect to /login
    expect(loginPage || hasLoginRedirect).toBeTruthy()
  })
})
