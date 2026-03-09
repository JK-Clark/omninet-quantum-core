// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import React, { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'
import apiClient from '../api/client'
import useAppStore from '../store/appStore'
import { t } from '../i18n'

const FALLBACK_LICENSE = { tier: 'trial', is_active: true, expires_at: '2026-12-31' }

export default function LicenseGuard({ children, requiredTiers }) {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const { setLicense, language } = useAppStore()
  const navigate = useNavigate()

  useEffect(() => {
    apiClient
      .get('/license/status')
      .then((res) => {
        const data = res.data
        setStatus(data)
        setLicense({
          tier: data.tier,
          expiresAt: data.expires_at,
          isValid: data.is_active,
        })
      })
      .catch(() => {
        setStatus(FALLBACK_LICENSE)
        setLicense({
          tier: FALLBACK_LICENSE.tier,
          expiresAt: FALLBACK_LICENSE.expires_at,
          isValid: FALLBACK_LICENSE.is_active,
        })
      })
      .finally(() => setLoading(false))
  }, [setLicense])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-dark-bg">
        <span className="text-neon-green font-mono animate-pulse">
          Checking license…
        </span>
      </div>
    )
  }

  const tierOk =
    !requiredTiers || requiredTiers.includes(status?.tier?.toLowerCase())

  if (!status?.is_active || !tierOk) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-dark-bg gap-6 px-4">
        <ShieldAlert className="text-alert-red w-16 h-16" />
        <h2 className="text-alert-red font-mono text-2xl font-bold">
          {t('license.expired', language)}
        </h2>
        <p className="text-gray-400 font-mono text-sm text-center max-w-md">
          Your license is inactive or does not grant access to this section.
          Please activate a valid license to continue.
        </p>
        <Link
          to="/login"
          className="mt-2 px-6 py-2 border border-neon-green text-neon-green font-mono rounded hover:bg-neon-green hover:text-dark-bg transition-colors"
        >
          {t('login.activate_license', language)}
        </Link>
      </div>
    )
  }

  return children
}
