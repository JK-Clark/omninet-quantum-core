// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Key } from 'lucide-react'
import apiClient from '../api/client'
import useAppStore from '../store/appStore'
import { t } from '../i18n'

const ASCII_BANNER = `
  ██████╗ ███████╗███╗   ██╗██╗ ██████╗
 ██╔════╝ ██╔════╝████╗  ██║██║██╔═══██╗
 ██║  ███╗█████╗  ██╔██╗ ██║██║██║   ██║
 ██║   ██║██╔══╝  ██║╚██╗██║██║██║   ██║
 ╚██████╔╝███████╗██║ ╚████║██║╚██████╔╝
  ╚═════╝ ╚══════╝╚═╝  ╚═══╝╚═╝ ╚═════╝
          E L I T E  —  Q U A N T U M
`

export default function LoginPage() {
  const navigate = useNavigate()
  const { login, language } = useAppStore()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // License activation modal
  const [showLicenseModal, setShowLicenseModal] = useState(false)
  const [licenseKey, setLicenseKey] = useState('')
  const [licenseMsg, setLicenseMsg] = useState('')
  const [licenseLoading, setLicenseLoading] = useState(false)

  const handleLogin = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      // OAuth2 requires application/x-www-form-urlencoded with `username` field
      const formData = new URLSearchParams()
      formData.append('username', email)
      formData.append('password', password)
      const res = await apiClient.post('/auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      login(res.data.token || res.data.access_token, res.data.user)
      navigate('/dashboard')
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          err.response?.data?.message ||
          'Invalid credentials. Please try again.'
      )
    } finally {
      setLoading(false)
    }
  }

  const handleActivateLicense = async (e) => {
    e.preventDefault()
    setLicenseMsg('')
    setLicenseLoading(true)
    try {
      await apiClient.post('/license/activate', { key: licenseKey })
      setLicenseMsg('✅ License activated successfully!')
      setLicenseKey('')
    } catch (err) {
      setLicenseMsg(
        '❌ ' +
          (err.response?.data?.detail ||
            err.response?.data?.message ||
            'Activation failed. Check your license key.')
      )
    } finally {
      setLicenseLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-dark-bg flex flex-col items-center justify-center px-4">
      {/* ASCII Banner */}
      <pre className="text-neon-green font-mono text-[10px] leading-tight mb-6 text-center select-none">
        {ASCII_BANNER}
      </pre>
      <p className="text-gray-500 font-mono text-xs mb-8 tracking-widest">
        © 2021-2026 JONATHAN KAMU / GENIO ELITE
      </p>

      {/* Login Card */}
      <div className="w-full max-w-sm bg-dark-card border border-neon-green/20 rounded-lg p-8 shadow-[0_0_40px_#00ff8822]">
        <h1 className="text-neon-green font-mono font-bold text-xl mb-6 tracking-wider">
          {t('login.title', language)}
        </h1>

        <form onSubmit={handleLogin} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-gray-400 font-mono text-xs">
              {t('login.email', language)}
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="bg-dark-surface border border-neon-green/20 text-gray-200 font-mono text-sm rounded px-3 py-2 focus:outline-none focus:border-neon-green transition-colors"
              placeholder="admin@omninet.local"
              autoComplete="email"
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-gray-400 font-mono text-xs">
              {t('login.password', language)}
            </label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-dark-surface border border-neon-green/20 text-gray-200 font-mono text-sm rounded px-3 py-2 pr-10 focus:outline-none focus:border-neon-green transition-colors"
                placeholder="••••••••"
                autoComplete="current-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-neon-green transition-colors"
                tabIndex={-1}
              >
                {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>

          {error && (
            <p className="text-alert-red font-mono text-xs border border-alert-red/30 rounded px-3 py-2 bg-alert-red/5">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="mt-2 py-2 bg-neon-green text-dark-bg font-mono font-bold rounded hover:bg-neon-green/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Authenticating…' : t('login.submit', language)}
          </button>
        </form>

        {/* License activation link */}
        <button
          onClick={() => setShowLicenseModal(true)}
          className="mt-4 w-full flex items-center justify-center gap-2 text-cyber-blue font-mono text-xs hover:text-neon-green transition-colors"
        >
          <Key size={12} />
          {t('login.activate_license', language)}
        </button>
      </div>

      {/* License Modal */}
      {showLicenseModal && (
        <div
          className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 px-4"
          onClick={() => setShowLicenseModal(false)}
        >
          <div
            className="bg-dark-card border border-cyber-blue/30 rounded-lg p-6 w-full max-w-sm shadow-[0_0_40px_#00aaff22]"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-cyber-blue font-mono font-bold text-lg mb-4">
              {t('login.activate_license', language)}
            </h2>
            <form onSubmit={handleActivateLicense} className="flex flex-col gap-3">
              <input
                type="text"
                value={licenseKey}
                onChange={(e) => setLicenseKey(e.target.value)}
                placeholder="XXXX-XXXX-XXXX-XXXX"
                className="bg-dark-surface border border-cyber-blue/20 text-gray-200 font-mono text-sm rounded px-3 py-2 focus:outline-none focus:border-cyber-blue transition-colors"
                required
              />
              {licenseMsg && (
                <p
                  className={`font-mono text-xs ${
                    licenseMsg.startsWith('✅') ? 'text-neon-green' : 'text-alert-red'
                  }`}
                >
                  {licenseMsg}
                </p>
              )}
              <div className="flex gap-2 mt-1">
                <button
                  type="button"
                  onClick={() => setShowLicenseModal(false)}
                  className="flex-1 py-2 border border-gray-600 text-gray-400 font-mono text-sm rounded hover:border-gray-400 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={licenseLoading}
                  className="flex-1 py-2 bg-cyber-blue text-dark-bg font-mono font-bold text-sm rounded hover:bg-cyber-blue/90 transition-colors disabled:opacity-50"
                >
                  {licenseLoading ? 'Activating…' : 'Activate'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
