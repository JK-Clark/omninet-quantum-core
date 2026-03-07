// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useTranslation } from '../i18n';
import LanguageSelector from '../components/LanguageSelector';
import LicenseBadge from '../components/LicenseBadge';
import { useAppStore } from '../store/appStore';
import { licenseAPI } from '../api/client';
import type { LicenseStatus } from '../api/client';

const TIER_FEATURES: Record<string, string[]> = {
  TRIAL: ['Basic topology (10 devices)', '7-day access', 'Community support'],
  COMMUNITY: ['Unlimited devices', 'Topology + Alerts', 'No AI / Quantum features'],
  BANK: ['AI failure prediction', 'Post-quantum AAA', 'Unlimited devices', 'Priority support'],
};

export default function LicenseManager(): JSX.Element {
  const t = useTranslation();
  const navigate = useNavigate();
  const { licenseTier, setLicenseTier, username, logout } = useAppStore();

  const [status, setStatus] = useState<LicenseStatus | null>(null);
  const [key, setKey] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    licenseAPI.status().then((r) => setStatus(r.data.data)).catch(console.error);
  }, []);

  const handleActivate = async (): Promise<void> => {
    if (!key.trim()) return;
    setLoading(true);
    try {
      const res = await licenseAPI.activate(key.trim());
      const newTier: string = (res.data as { data: { tier: string } }).data.tier;
      setLicenseTier(newTier);
      toast.success(`License activated — ${newTier} tier`);
      const refreshed = await licenseAPI.status();
      setStatus(refreshed.data.data);
      setKey('');
    } catch (err) {
      toast.error(String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen flex-col bg-gray-950 text-gray-100">
      {/* Navbar */}
      <nav className="flex items-center justify-between border-b border-gray-800 px-6 py-3">
        <div className="flex items-center gap-4">
          <span className="text-lg font-bold text-brand-500">OmniNet</span>
          <button onClick={() => navigate('/')} className="text-sm text-gray-400 hover:text-white">{t('nav.dashboard')}</button>
          <button onClick={() => navigate('/ai')} className="text-sm text-gray-400 hover:text-white">{t('nav.ai')}</button>
          <button onClick={() => navigate('/license')} className="text-sm text-brand-400">{t('nav.license')}</button>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-400">{username}</span>
          <LicenseBadge tier={licenseTier} />
          <LanguageSelector />
          <button onClick={() => { logout(); navigate('/setup'); }} className="text-sm text-red-400 hover:text-red-300">{t('nav.logout')}</button>
        </div>
      </nav>

      <div className="flex-1 overflow-y-auto p-6 max-w-4xl mx-auto w-full">
        <h1 className="mb-8 text-2xl font-bold">{t('license.title')}</h1>

        {/* Current status */}
        {status && (
          <div className="mb-8 rounded-2xl border border-gray-800 bg-gray-900 p-6">
            <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-gray-400">
              {t('license.current')}
            </h2>
            <div className="flex flex-wrap gap-6">
              <div>
                <p className="text-xs text-gray-500">{t('license.tier')}</p>
                <LicenseBadge tier={status.tier} />
              </div>
              <div>
                <p className="text-xs text-gray-500">{t('license.expires')}</p>
                <p className="font-semibold">
                  {status.expires_at
                    ? new Date(status.expires_at).toLocaleDateString()
                    : '—'}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500">{t('license.devices')}</p>
                <p className="font-semibold">
                  {status.max_devices ?? t('license.unlimited')}
                </p>
              </div>
              {status.days_remaining !== null && (
                <div>
                  <p className="text-xs text-gray-500">Remaining</p>
                  <p className="font-semibold text-yellow-400">
                    {t('license.days_remaining', { days: String(status.days_remaining) })}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Feature matrix */}
        <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {(['TRIAL', 'COMMUNITY', 'BANK'] as const).map((tier) => (
            <div
              key={tier}
              className={`rounded-2xl border p-5 ${
                licenseTier === tier
                  ? 'border-brand-500 bg-gray-800'
                  : 'border-gray-700 bg-gray-900'
              }`}
            >
              <div className="mb-3 flex items-center justify-between">
                <LicenseBadge tier={tier} />
                {licenseTier === tier && (
                  <span className="text-xs text-brand-400 font-semibold">Current</span>
                )}
              </div>
              <ul className="space-y-1.5 text-sm text-gray-300">
                {TIER_FEATURES[tier].map((f) => (
                  <li key={f} className="flex items-start gap-2">
                    <span className="mt-0.5 text-green-400">✓</span>
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Activate form */}
        <div className="rounded-2xl border border-gray-800 bg-gray-900 p-6">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-gray-400">
            {t('license.activate')}
          </h2>
          <div className="flex gap-3">
            <input
              className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
              placeholder={t('license.key_placeholder')}
              value={key}
              onChange={(e) => setKey(e.target.value)}
            />
            <button
              onClick={handleActivate}
              disabled={loading || !key.trim()}
              className="rounded-lg bg-brand-500 px-5 py-2 font-semibold hover:bg-brand-600 disabled:opacity-50 transition-colors"
            >
              {loading ? '…' : t('license.submit')}
            </button>
          </div>
          <p className="mt-2 text-xs text-gray-500">
            License keys are UUID v4 format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
          </p>
        </div>
      </div>
    </div>
  );
}
