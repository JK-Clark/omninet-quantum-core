// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import React from 'react'
import useAppStore from '../store/appStore'
import { supportedLanguages } from '../i18n'

export default function LanguageSelector() {
  const { language, setLanguage } = useAppStore()
  return (
    <select
      value={language}
      onChange={(e) => setLanguage(e.target.value)}
      className="bg-dark-surface border border-neon-green/20 text-neon-green text-xs rounded px-2 py-1 font-mono focus:outline-none focus:border-neon-green cursor-pointer"
    >
      {supportedLanguages.map((lang) => (
        <option key={lang.code} value={lang.code} className="bg-dark-surface">
          {lang.label}
        </option>
      ))}
    </select>
  )
}
