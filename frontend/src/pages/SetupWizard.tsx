// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { useTranslation } from '../i18n';
import LanguageSelector from '../components/LanguageSelector';
import { authAPI, licenseAPI, topologyAPI } from '../api/client';
import { useAppStore } from '../store/appStore';

type Step = 1 | 2 | 3 | 4 | 5;

interface NetworkConfig {
  seedIp: string;
  username: string;
  password: string;
  deviceType: string;
  secret: string;
}

const STEPS = 5;
const DEVICE_TYPES = ['cisco_ios', 'cisco_nxos', 'arista_eos', 'juniper_junos'];

const variants = {
  enter: { opacity: 0, x: 40 },
  center: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -40 },
};

export default function SetupWizard(): JSX.Element {
  const t = useTranslation();
  const navigate = useNavigate();
  const { setTokens, setUsername, setLicenseTier, setSetupComplete } = useAppStore();

  const [step, setStep] = useState<Step>(1);
  const [loading, setLoading] = useState(false);
  const [discoveredCount, setDiscoveredCount] = useState(0);
  const [licenseKey, setLicenseKey] = useState('');
  const [netConfig, setNetConfig] = useState<NetworkConfig>({
    seedIp: '',
    username: '',
    password: '',
    deviceType: 'cisco_ios',
    secret: '',
  });

  const [regUsername, setRegUsername] = useState('admin');
  const [regEmail, setRegEmail] = useState('admin@omninet.local');
  const [regPassword, setRegPassword] = useState('');

  const next = (): void => setStep((s) => Math.min(s + 1, STEPS) as Step);

  const handleStartTrial = async (): Promise<void> => {
    setLoading(true);
    try {
      // Register user; if already exists, proceed to login
      await authAPI.register(regUsername, regEmail, regPassword).catch((err) => {
        const msg = String(err);
        if (!msg.includes('USERNAME_TAKEN') && !msg.includes('already')) {
          throw err;
        }
      });
      const loginRes = await authAPI.login(regUsername, regPassword);
      const { access_token, refresh_token } = loginRes.data.data;
      setTokens(access_token, refresh_token);
      setUsername(regUsername);
      next();
    } catch (err) {
      toast.error(String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleActivateLicense = async (): Promise<void> => {
    if (!licenseKey.trim()) { next(); return; }
    setLoading(true);
    try {
      const res = await licenseAPI.activate(licenseKey.trim());
      setLicenseTier(res.data.data.tier);
      toast.success('License activated!');
      next();
    } catch (err) {
      toast.error(String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleDiscover = async (): Promise<void> => {
    setLoading(true);
    next(); // move to discovery step
    try {
      const res = await topologyAPI.discover({
        seed_ip: netConfig.seedIp,
        username: netConfig.username,
        password: netConfig.password,
        device_type: netConfig.deviceType,
        secret: netConfig.secret,
      });
      setDiscoveredCount(res.data.data.discovered ?? 0);
    } catch {
      setDiscoveredCount(0);
    } finally {
      setLoading(false);
      next(); // move to complete step
    }
  };

  const handleComplete = (): void => {
    setSetupComplete(true);
    navigate('/');
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-950 px-4">
      {/* Header */}
      <div className="mb-8 flex w-full max-w-lg items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold text-brand-500">OmniNet</span>
          <span className="text-xs text-quantum-400">Quantum-Core</span>
        </div>
        <LanguageSelector />
      </div>

      {/* Progress bar */}
      <div className="mb-6 w-full max-w-lg">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>Step {step} of {STEPS}</span>
          <span>{Math.round((step / STEPS) * 100)}%</span>
        </div>
        <div className="h-1.5 w-full rounded-full bg-gray-800">
          <div
            className="h-1.5 rounded-full bg-brand-500 transition-all duration-500"
            style={{ width: `${(step / STEPS) * 100}%` }}
          />
        </div>
      </div>

      {/* Card */}
      <div className="w-full max-w-lg overflow-hidden rounded-2xl border border-gray-800 bg-gray-900 p-8">
        <AnimatePresence mode="wait">
          <motion.div
            key={step}
            variants={variants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.25 }}
          >
            {step === 1 && (
              <div className="space-y-6 text-center">
                <div className="text-5xl">🌐</div>
                <h1 className="text-2xl font-bold">{t('setup.welcome.title')}</h1>
                <p className="text-gray-400">{t('setup.welcome.subtitle')}</p>
                <div className="grid grid-cols-3 gap-3 text-sm">
                  {['🔐 Post-Quantum AAA', '🤖 AI Failure Prediction', '🗺️ Auto-Discovery'].map((f) => (
                    <div key={f} className="rounded-lg border border-gray-700 bg-gray-800 p-3">{f}</div>
                  ))}
                </div>
                <button
                  onClick={next}
                  className="w-full rounded-lg bg-brand-500 py-3 font-semibold hover:bg-brand-600 transition-colors"
                >
                  {t('setup.welcome.cta')}
                </button>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-5">
                <h2 className="text-xl font-bold">{t('setup.license.title')}</h2>
                <div className="space-y-3">
                  <div>
                    <label className="mb-1 block text-sm text-gray-400">Username</label>
                    <input
                      className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
                      value={regUsername}
                      onChange={(e) => setRegUsername(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm text-gray-400">Email</label>
                    <input
                      type="email"
                      className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
                      value={regEmail}
                      onChange={(e) => setRegEmail(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-sm text-gray-400">Password</label>
                    <input
                      type="password"
                      className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
                      value={regPassword}
                      onChange={(e) => setRegPassword(e.target.value)}
                    />
                  </div>
                </div>
                <button
                  onClick={handleStartTrial}
                  disabled={loading}
                  className="w-full rounded-lg bg-brand-500 py-3 font-semibold hover:bg-brand-600 disabled:opacity-50 transition-colors"
                >
                  {loading ? 'Creating account…' : t('setup.license.trial')}
                </button>
              </div>
            )}

            {step === 3 && (
              <div className="space-y-5">
                <h2 className="text-xl font-bold">{t('setup.license.title')}</h2>
                <div>
                  <label className="mb-1 block text-sm text-gray-400">{t('setup.license.placeholder')}</label>
                  <input
                    className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                    placeholder="xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx"
                    value={licenseKey}
                    onChange={(e) => setLicenseKey(e.target.value)}
                  />
                </div>
                <div className="flex gap-3">
                  <button
                    onClick={next}
                    className="flex-1 rounded-lg border border-gray-600 py-3 text-sm hover:bg-gray-800 transition-colors"
                  >
                    Skip
                  </button>
                  <button
                    onClick={handleActivateLicense}
                    disabled={loading}
                    className="flex-1 rounded-lg bg-brand-500 py-3 font-semibold hover:bg-brand-600 disabled:opacity-50 transition-colors"
                  >
                    {loading ? 'Activating…' : t('setup.license.activate')}
                  </button>
                </div>
              </div>
            )}

            {step === 4 && (
              <div className="space-y-4">
                <h2 className="text-xl font-bold">{t('setup.network.title')}</h2>
                {(['seedIp', 'username', 'password', 'secret'] as const).map((field) => (
                  <div key={field}>
                    <label className="mb-1 block text-sm capitalize text-gray-400">
                      {t(`setup.network.${field === 'seedIp' ? 'ip' : field}`)}
                    </label>
                    <input
                      type={field === 'password' ? 'password' : 'text'}
                      className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
                      value={netConfig[field]}
                      onChange={(e) => setNetConfig((c) => ({ ...c, [field]: e.target.value }))}
                    />
                  </div>
                ))}
                <div>
                  <label className="mb-1 block text-sm text-gray-400">{t('setup.network.device_type')}</label>
                  <select
                    className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
                    value={netConfig.deviceType}
                    onChange={(e) => setNetConfig((c) => ({ ...c, deviceType: e.target.value }))}
                  >
                    {DEVICE_TYPES.map((d) => <option key={d} value={d}>{d}</option>)}
                  </select>
                </div>
                <button
                  onClick={handleDiscover}
                  disabled={loading || !netConfig.seedIp}
                  className="w-full rounded-lg bg-brand-500 py-3 font-semibold hover:bg-brand-600 disabled:opacity-50 transition-colors"
                >
                  {t('setup.network.next')}
                </button>
                <button onClick={handleComplete} className="w-full text-center text-sm text-gray-500 hover:text-gray-300">
                  Skip →
                </button>
              </div>
            )}

            {step === 5 && loading && (
              <div className="space-y-6 text-center">
                <div className="text-4xl">📡</div>
                <h2 className="text-xl font-bold">{t('setup.discovery.title')}</h2>
                <div className="h-2 w-full rounded-full bg-gray-800">
                  <div className="h-2 w-1/3 rounded-full bg-brand-500 animate-pulse" />
                </div>
                <p className="text-gray-400 animate-pulse">
                  {t('setup.discovery.scanning', { ip: netConfig.seedIp })}
                </p>
              </div>
            )}

            {step === 5 && !loading && (
              <div className="space-y-6 text-center">
                <div className="text-5xl">✅</div>
                <h2 className="text-2xl font-bold">{t('setup.complete.title')}</h2>
                <p className="text-gray-400">
                  {t('setup.complete.found', { count: String(discoveredCount) })}
                </p>
                <button
                  onClick={handleComplete}
                  className="w-full rounded-lg bg-brand-500 py-3 font-semibold hover:bg-brand-600 transition-colors"
                >
                  {t('setup.complete.cta')}
                </button>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
