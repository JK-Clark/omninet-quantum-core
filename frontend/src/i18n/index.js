// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import en from './en.json'
import fr from './fr.json'
import hi from './hi.json'
import ko from './ko.json'

const translations = { en, fr, hi, ko }

export function t(key, lang = 'en') {
  const dict = translations[lang] || translations['en']
  return dict[key] || key
}

export const supportedLanguages = [
  { code: 'en', label: 'English' },
  { code: 'fr', label: 'Français' },
  { code: 'hi', label: 'हिन्दी' },
  { code: 'ko', label: '한국어' },
]

export default translations
