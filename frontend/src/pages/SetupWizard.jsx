// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, ChevronLeft, CheckCircle, Loader } from 'lucide-react'
import apiClient from '../api/client'
import useAppStore from '../store/appStore'
import { t } from '../i18n'

const STEPS = ['setup.step1', 'setup.step2', 'setup.step3']

export default function SetupWizard() {
  const navigate = useNavigate()
  const { language } = useAppStore()
  const [step, setStep] = useState(0)

  // Step 1 — DB config
  const [db, setDb] = useState({ host: 'localhost', port: '5432', user: 'omninet', password: '' })

  // Step 2 — Network scan
  const [cidr, setCidr] = useState('192.168.1.0/24')
  const [scanLoading, setScanLoading] = useState(false)
  const [scanResult, setScanResult] = useState(null)
  const [scanError, setScanError] = useState('')

  // Step 3 — Branding
  const [orgName, setOrgName] = useState('')
  const [logoFile, setLogoFile] = useState(null)

  const handleScan = async () => {
    setScanLoading(true)
    setScanError('')
    setScanResult(null)
    try {
      const res = await apiClient.post('/devices/discover', { cidr })
      setScanResult(res.data)
    } catch (err) {
      setScanError(
        err.response?.data?.detail ||
          err.response?.data?.message ||
          'Scan failed or backend not reachable. You can continue anyway.'
      )
    } finally {
      setScanLoading(false)
    }
  }

  const handleFinish = () => {
    navigate('/dashboard')
  }

  const inputCls =
    'w-full bg-dark-surface border border-neon-green/20 text-gray-200 font-mono text-sm rounded px-3 py-2 focus:outline-none focus:border-neon-green transition-colors'
  const labelCls = 'text-gray-400 font-mono text-xs'

  return (
    <div className="min-h-screen bg-dark-bg flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-lg bg-dark-card border border-neon-green/20 rounded-lg p-8 shadow-[0_0_40px_#00ff8814]">
        {/* Header */}
        <h1 className="text-neon-green font-mono font-bold text-xl mb-2 tracking-wider">
          {t('setup.title', language)}
        </h1>

        {/* Step indicator */}
        <div className="flex items-center gap-2 mb-8">
          {STEPS.map((s, idx) => (
            <React.Fragment key={s}>
              <div
                className={`w-7 h-7 rounded-full border-2 flex items-center justify-center font-mono text-xs font-bold transition-colors ${
                  idx < step
                    ? 'bg-neon-green border-neon-green text-dark-bg'
                    : idx === step
                    ? 'border-neon-green text-neon-green'
                    : 'border-gray-700 text-gray-600'
                }`}
              >
                {idx < step ? <CheckCircle size={14} /> : idx + 1}
              </div>
              {idx < STEPS.length - 1 && (
                <div
                  className={`flex-1 h-px transition-colors ${
                    idx < step ? 'bg-neon-green' : 'bg-gray-700'
                  }`}
                />
              )}
            </React.Fragment>
          ))}
        </div>

        <h2 className="text-gray-300 font-mono text-sm font-semibold mb-6">
          {t(STEPS[step], language)}
        </h2>

        {/* Step 1 — DB Config */}
        {step === 0 && (
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-1">
                <label className={labelCls}>HOST</label>
                <input
                  value={db.host}
                  onChange={(e) => setDb({ ...db, host: e.target.value })}
                  className={inputCls}
                  placeholder="localhost"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className={labelCls}>PORT</label>
                <input
                  value={db.port}
                  onChange={(e) => setDb({ ...db, port: e.target.value })}
                  className={inputCls}
                  placeholder="5432"
                />
              </div>
            </div>
            <div className="flex flex-col gap-1">
              <label className={labelCls}>USER</label>
              <input
                value={db.user}
                onChange={(e) => setDb({ ...db, user: e.target.value })}
                className={inputCls}
                placeholder="omninet"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className={labelCls}>PASSWORD</label>
              <input
                type="password"
                value={db.password}
                onChange={(e) => setDb({ ...db, password: e.target.value })}
                className={inputCls}
                placeholder="••••••••"
                autoComplete="new-password"
              />
            </div>
          </div>
        )}

        {/* Step 2 — Network scan */}
        {step === 1 && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <label className={labelCls}>CIDR Range</label>
              <input
                value={cidr}
                onChange={(e) => setCidr(e.target.value)}
                className={inputCls}
                placeholder="192.168.1.0/24"
              />
            </div>
            <button
              type="button"
              onClick={handleScan}
              disabled={scanLoading}
              className="flex items-center justify-center gap-2 py-2 border border-neon-green text-neon-green font-mono text-sm rounded hover:bg-neon-green hover:text-dark-bg transition-colors disabled:opacity-50"
            >
              {scanLoading ? (
                <>
                  <Loader size={14} className="animate-spin" /> Scanning…
                </>
              ) : (
                t('setup.scan_button', language)
              )}
            </button>
            {scanError && (
              <p className="text-yellow-400 font-mono text-xs border border-yellow-400/20 rounded px-3 py-2 bg-yellow-400/5">
                ⚠ {scanError}
              </p>
            )}
            {scanResult && (
              <div className="bg-dark-surface border border-neon-green/20 rounded p-3">
                <p className="text-neon-green font-mono text-xs">
                  ✅ {scanResult.discovered ?? scanResult.count ?? 'Unknown'} device(s) discovered
                </p>
              </div>
            )}
          </div>
        )}

        {/* Step 3 — Branding */}
        {step === 2 && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-1">
              <label className={labelCls}>Organisation name</label>
              <input
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                className={inputCls}
                placeholder="Genio Elite Corp"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className={labelCls}>Logo (optional)</label>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setLogoFile(e.target.files[0])}
                className="bg-dark-surface border border-neon-green/20 text-gray-400 font-mono text-xs rounded px-3 py-2 file:mr-3 file:py-1 file:px-2 file:border-0 file:bg-neon-green/10 file:text-neon-green file:font-mono file:text-xs file:rounded cursor-pointer"
              />
              {logoFile && (
                <p className="text-gray-500 font-mono text-xs mt-1">
                  Selected: {logoFile.name}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Navigation buttons */}
        <div className="flex justify-between mt-8">
          <button
            onClick={() => setStep((s) => s - 1)}
            disabled={step === 0}
            className="flex items-center gap-1.5 px-4 py-2 border border-gray-600 text-gray-400 font-mono text-sm rounded hover:border-gray-400 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ChevronLeft size={14} /> {t('setup.prev', language)}
          </button>
          {step < STEPS.length - 1 ? (
            <button
              onClick={() => setStep((s) => s + 1)}
              className="flex items-center gap-1.5 px-4 py-2 bg-neon-green text-dark-bg font-mono font-bold text-sm rounded hover:bg-neon-green/90 transition-colors"
            >
              {t('setup.next', language)} <ChevronRight size={14} />
            </button>
          ) : (
            <button
              onClick={handleFinish}
              className="flex items-center gap-1.5 px-4 py-2 bg-neon-green text-dark-bg font-mono font-bold text-sm rounded hover:bg-neon-green/90 transition-colors"
            >
              <CheckCircle size={14} /> {t('setup.finish', language)}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
