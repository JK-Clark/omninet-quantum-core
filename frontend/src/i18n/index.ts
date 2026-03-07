// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import { useCallback } from 'react';
import { useLang } from '../App';
import en from './en.json';
import fr from './fr.json';
import hi from './hi.json';
import ko from './ko.json';

const translations: Record<string, Record<string, string>> = { en, fr, hi, ko };

export function useTranslation(): (key: string, vars?: Record<string, string>) => string {
  const { locale } = useLang();

  const t = useCallback(
    (key: string, vars?: Record<string, string>): string => {
      const dict = translations[locale] ?? translations['en'];
      let text: string = dict[key] ?? translations['en'][key] ?? key;
      if (vars) {
        Object.entries(vars).forEach(([k, v]) => {
          text = text.replace(new RegExp(`\\{\\{${k}\\}\\}`, 'g'), v);
        });
      }
      return text;
    },
    [locale]
  );

  return t;
}
