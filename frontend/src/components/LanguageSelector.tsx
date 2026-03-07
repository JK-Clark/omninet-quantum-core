// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import React from 'react';
import { useLang, type Locale } from '../App';

const LOCALES: { code: Locale; label: string; flag: string }[] = [
  { code: 'en', label: 'English', flag: '🇬🇧' },
  { code: 'fr', label: 'Français', flag: '🇫🇷' },
  { code: 'hi', label: 'हिन्दी', flag: '🇮🇳' },
  { code: 'ko', label: '한국어', flag: '🇰🇷' },
];

export default function LanguageSelector(): JSX.Element {
  const { locale, setLocale } = useLang();

  return (
    <select
      value={locale}
      onChange={(e) => setLocale(e.target.value as Locale)}
      className="rounded-md border border-gray-600 bg-gray-800 px-2 py-1 text-sm text-gray-200 focus:outline-none focus:ring-2 focus:ring-brand-500"
      aria-label="Language selector"
    >
      {LOCALES.map((l) => (
        <option key={l.code} value={l.code}>
          {l.flag} {l.label}
        </option>
      ))}
    </select>
  );
}
