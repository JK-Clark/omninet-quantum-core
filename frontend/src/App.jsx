// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import useAppStore from './store/appStore'
import LicenseGuard from './components/LicenseGuard'
import LoginPage from './pages/LoginPage'
import SetupWizard from './pages/SetupWizard'
import Dashboard from './pages/Dashboard'
import AIPredictor from './pages/AIPredictor'

function PrivateRoute({ children }) {
  const isAuthenticated = useAppStore((s) => s.auth.isAuthenticated)
  return isAuthenticated ? children : <Navigate to="/login" replace />
}

function RootRedirect() {
  const isAuthenticated = useAppStore((s) => s.auth.isAuthenticated)
  return <Navigate to={isAuthenticated ? '/dashboard' : '/login'} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<RootRedirect />} />
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/setup"
          element={
            <PrivateRoute>
              <SetupWizard />
            </PrivateRoute>
          }
        />
        <Route
          path="/dashboard"
          element={
            <PrivateRoute>
              <LicenseGuard>
                <Dashboard />
              </LicenseGuard>
            </PrivateRoute>
          }
        />
        <Route
          path="/ai-predictor"
          element={
            <PrivateRoute>
              <LicenseGuard requiredTiers={['bank', 'community']}>
                <AIPredictor />
              </LicenseGuard>
            </PrivateRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

