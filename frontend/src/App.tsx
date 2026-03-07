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
      </BrowserRouter>
    </LangContext.Provider>
  );
}
