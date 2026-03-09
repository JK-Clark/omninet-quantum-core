// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { LayoutDashboard, BrainCircuit, LogOut } from 'lucide-react'
import useAppStore from '../store/appStore'
import { t } from '../i18n'
import LicenseBadge from './LicenseBadge'
import LanguageSelector from './LanguageSelector'

export default function NavBar() {
  const { logout, language } = useAppStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <nav className="w-full bg-dark-surface border-b border-neon-green/20 px-6 py-3 flex items-center justify-between">
      {/* Logo */}
      <Link to="/dashboard" className="font-mono text-neon-green font-bold tracking-widest text-sm">
        <span className="text-cyber-blue">[</span>
        GENIO<span className="text-neon-green"> ELITE</span>
        <span className="text-cyber-blue">]</span>
        <span className="text-gray-500 text-xs ml-2">OmniNet QC</span>
      </Link>

      {/* Nav links */}
      <div className="flex items-center gap-6">
        <Link
          to="/dashboard"
          className="flex items-center gap-1.5 text-gray-400 hover:text-neon-green font-mono text-xs transition-colors"
        >
          <LayoutDashboard size={14} />
          {t('nav.dashboard', language)}
        </Link>
        <Link
          to="/ai-predictor"
          className="flex items-center gap-1.5 text-gray-400 hover:text-neon-green font-mono text-xs transition-colors"
        >
          <BrainCircuit size={14} />
          {t('nav.ai', language)}
        </Link>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-4">
        <LicenseBadge />
        <LanguageSelector />
        <button
          onClick={handleLogout}
          className="flex items-center gap-1.5 text-gray-500 hover:text-alert-red font-mono text-xs transition-colors"
        >
          <LogOut size={14} />
          {t('nav.logout', language)}
        </button>
      </div>
    </nav>
  )
}
