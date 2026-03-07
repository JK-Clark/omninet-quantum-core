// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import React, {
  createContext,
  lazy,
  Suspense,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useAppStore } from './store/appStore';
import { licenseAPI, setAuthToken } from './api/client';
import type { LicenseStatus } from './api/client';
import { useTranslation } from './i18n';

// ─── Lazy page imports ────────────────────────────────────────────────────────
const SetupWizard = lazy(() => import('./pages/SetupWizard'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const AIPredictor = lazy(() => import('./pages/AIPredictor'));
const LicenseManager = lazy(() => import('./pages/LicenseManager'));

// How often to poll the license status endpoint (5 minutes).
const LICENSE_POLL_INTERVAL_MS = 5 * 60 * 1_000;

// ─── Language context ─────────────────────────────────────────────────────────
export type Locale = 'en' | 'fr' | 'hi' | 'ko';

interface LangContextType {
  locale: Locale;
  setLocale: (l: Locale) => void;
}

export const LangContext = createContext<LangContextType>({
  locale: 'en',
  setLocale: () => undefined,
});

export function useLang(): LangContextType {
  return useContext(LangContext);
}

// ─── Auth guard ───────────────────────────────────────────────────────────────
function RequireAuth({ children }: { children: JSX.Element }): JSX.Element {
  const token = useAppStore((s) => s.accessToken);
  if (!token) return <Navigate to="/setup" replace />;
  return children;
}

// ─── Loading fallback ─────────────────────────────────────────────────────────
function PageLoader(): JSX.Element {
  return (
    <div className="flex h-screen items-center justify-center">
      <div className="h-12 w-12 animate-spin rounded-full border-4 border-brand-500 border-t-transparent" />
    </div>
  );
}

// ─── License expiry banner ────────────────────────────────────────────────────

/**
 * Polls the license status every {@link LICENSE_POLL_INTERVAL_MS} and displays
 * a contextual banner:
 *  - "warning"  (≤30 days)  → dismissible info bar (amber)
 *  - "critical" (≤7 days)   → persistent red banner
 *  - "grace"                → persistent red banner (in grace period)
 *  - "expired"              → persistent dark-red banner (hard expired)
 *
 * The banner is suppressed on the /setup page and when no token is present.
 */
function LicenseExpiryBanner(): JSX.Element | null {
  const t = useTranslation();
  const token = useAppStore((s) => s.accessToken);
  const location = useLocation();
  const [licenseStatus, setLicenseStatus] = useState<LicenseStatus | null>(null);
  const [dismissed, setDismissed] = useState(false);

  // Use a ref so the polling callback can read the current level without being
  // listed as a dependency (which would restart the interval on every change).
  const lastLevelRef = useRef<string>('ok');

  useEffect(() => {
    if (!token) return;

    const poll = (): void => {
      licenseAPI.status()
        .then((r) => {
          const data: LicenseStatus = r.data.data;
          setLicenseStatus(data);
          // Re-show banner whenever the alert level escalates.
          if (data.expiry_alert_level !== lastLevelRef.current) {
            setDismissed(false);
            lastLevelRef.current = data.expiry_alert_level;
          }
        })
        .catch(() => { /* silently ignore — auth may not be ready yet */ });
    };

    poll();
    const id = setInterval(poll, LICENSE_POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [token]);

  // Don't show on the setup page or when no license data yet
  if (location.pathname === '/setup') return null;
  if (!licenseStatus) return null;

  const level = licenseStatus.expiry_alert_level;
  const days = licenseStatus.days_remaining ?? 0;
  const daysStr = String(days);

  if (level === 'ok' || dismissed) return null;

  const isPersistent = level === 'critical' || level === 'grace' || level === 'expired';

  // Build message text from i18n keys
  let text: string;
  if (level === 'critical') {
    text = t('license.banner.critical', { days: daysStr });
  } else if (level === 'grace') {
    text = t('license.banner.grace', { days: daysStr });
  } else if (level === 'expired') {
    text = t('license.banner.expired');
  } else {
    // "warning"
    text = t('license.banner.warning', { days: daysStr });
  }

  // Style variants
  const bannerClass =
    level === 'warning'
      ? 'bg-amber-600 text-amber-50'
      : level === 'expired'
      ? 'bg-red-950 text-red-100 border border-red-700'
      : 'bg-red-700 text-white'; // critical + grace

  return (
    <div
      className={`fixed left-0 right-0 top-0 z-[100] flex items-center justify-between gap-3 px-4 py-2 text-sm font-medium shadow-lg ${bannerClass}`}
      role="alert"
      aria-live="polite"
    >
      <span className="flex-1 text-center">{text}</span>
      {!isPersistent && (
        <button
          onClick={() => setDismissed(true)}
          className="ml-4 shrink-0 rounded px-2 py-0.5 text-xs font-semibold opacity-80 hover:opacity-100 ring-1 ring-current"
          aria-label={t('license.banner.dismiss')}
        >
          {t('license.banner.dismiss')}
        </button>
      )}
    </div>
  );
}

// ─── Copyright footer ─────────────────────────────────────────────────────────

const COPYRIGHT_START_YEAR = 2021;

function CopyrightFooter(): JSX.Element {
  const currentYear = new Date().getFullYear();
  const yearRange = currentYear === COPYRIGHT_START_YEAR
    ? String(COPYRIGHT_START_YEAR)
    : `${COPYRIGHT_START_YEAR}–${currentYear}`;
  return (
    <footer className="fixed bottom-0 left-0 right-0 z-50 bg-gray-900 py-1 text-center text-xs text-gray-400 select-none">
      © {yearRange} Jonathan Kamu / Genio Elite — All rights reserved.
      Proprietary software — unauthorized reproduction or distribution is strictly prohibited.
    </footer>
  );
}

// ─── App ──────────────────────────────────────────────────────────────────────
const VALID_LOCALES: Locale[] = ['en', 'fr', 'hi', 'ko'];
function isValidLocale(v: string): v is Locale {
  return VALID_LOCALES.includes(v as Locale);
}

export default function App(): JSX.Element {
  const rawLocale = localStorage.getItem('omninet_locale') ?? 'en';
  const initialLocale: Locale = isValidLocale(rawLocale) ? rawLocale : 'en';
  const [locale, setLocaleState] = useState<Locale>(initialLocale);
  const accessToken = useAppStore((s) => s.accessToken);

  const setLocale = (l: Locale): void => {
    setLocaleState(l);
    localStorage.setItem('omninet_locale', l);
  };

  // Keep Axios interceptor in sync with token
  useEffect(() => {
    if (accessToken) setAuthToken(accessToken);
  }, [accessToken]);

  return (
    <LangContext.Provider value={{ locale, setLocale }}>
      <BrowserRouter>
        {/* License expiry banner — shown on all authenticated pages */}
        <LicenseExpiryBanner />
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/setup" element={<SetupWizard />} />
            <Route
              path="/"
              element={
                <RequireAuth>
                  <Dashboard />
                </RequireAuth>
              }
            />
            <Route
              path="/ai"
              element={
                <RequireAuth>
                  <AIPredictor />
                </RequireAuth>
              }
            />
            <Route
              path="/license"
              element={
                <RequireAuth>
                  <LicenseManager />
                </RequireAuth>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
        <CopyrightFooter />
      </BrowserRouter>
    </LangContext.Provider>
  );
}
