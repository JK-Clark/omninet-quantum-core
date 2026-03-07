// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import React, {
  createContext,
  lazy,
  Suspense,
  useContext,
  useEffect,
  useState,
} from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { useAppStore } from './store/appStore';
import { setAuthToken } from './api/client';

// ─── Lazy page imports ────────────────────────────────────────────────────────
const SetupWizard = lazy(() => import('./pages/SetupWizard'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const AIPredictor = lazy(() => import('./pages/AIPredictor'));
const LicenseManager = lazy(() => import('./pages/LicenseManager'));

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
