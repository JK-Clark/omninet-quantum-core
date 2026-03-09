// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import React from 'react'
import useAppStore from '../store/appStore'
import { t } from '../i18n'

const TIER_COLORS = {
  trial: 'text-yellow-400 border-yellow-400/40',
  community: 'text-cyber-blue border-cyber-blue/40',
  bank: 'text-neon-green border-neon-green/40',
  expired: 'text-alert-red border-alert-red/40',
}

export default function LicenseBadge() {
  const { license, language } = useAppStore()
  const tier = license?.isValid === false ? 'expired' : (license?.tier || 'trial')
  const colorClass = TIER_COLORS[tier] || TIER_COLORS.trial
  const label = t(`license.${tier}`, language)
  const expires = license?.expiresAt
    ? new Date(license.expiresAt).toLocaleDateString()
    : null

  return (
    <span
      className={`inline-flex items-center gap-1 border rounded px-2 py-0.5 text-xs font-mono ${colorClass}`}
    >
      <span className="uppercase tracking-widest">{label}</span>
      {expires && (
        <span className="opacity-60 text-[10px]">· {expires}</span>
      )}
    </span>
  )
}
