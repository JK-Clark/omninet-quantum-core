import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { useTranslation } from '../i18n';
import LanguageSelector from '../components/LanguageSelector';
import LicenseBadge from '../components/LicenseBadge';
import { useAppStore } from '../store/appStore';
import { aiAPI, devicesAPI } from '../api/client';
import type { DeviceData, PredictionData } from '../api/client';

function GaugeSvg({ value }: { value: number }): JSX.Element {
  const pct = Math.min(100, Math.max(0, value * 100));
  const angle = -135 + (pct / 100) * 270;
  const color = pct >= 75 ? '#ef4444' : pct >= 50 ? '#f59e0b' : '#22c55e';
  const r = 60;
  const cx = 80;
  const cy = 80;
  const radians = (angle * Math.PI) / 180;
  const nx = cx + r * Math.cos(radians);
  const ny = cy + r * Math.sin(radians);

  return (
    <svg viewBox="0 0 160 120" className="w-full max-w-[180px]">
      <path
        d="M 20 100 A 60 60 0 1 1 140 100"
        fill="none"
        stroke="#374151"
        strokeWidth="12"
        strokeLinecap="round"
      />
      <path
        d="M 20 100 A 60 60 0 1 1 140 100"
        fill="none"
        stroke={color}
        strokeWidth="12"
        strokeLinecap="round"
        strokeDasharray={`${(pct / 100) * 188.5} 188.5`}
      />
      <line
        x1={cx}
        y1={cy}
        x2={nx}
        y2={ny}
        stroke="white"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <circle cx={cx} cy={cy} r="4" fill="white" />
      <text x={cx} y={105} textAnchor="middle" fill={color} fontSize="18" fontWeight="bold">
        {pct.toFixed(1)}%
      </text>
    </svg>
  );
}

function generateMockTrend(points = 24): { time: string; cpu: number; ram: number; errors: number }[] {
  return Array.from({ length: points }, (_, i) => ({
    time: `${String(i).padStart(2, '0')}:00`,
    cpu: 20 + Math.random() * 60,
    ram: 30 + Math.random() * 50,
    errors: Math.random() * 5,
  }));
}

export default function AIPredictor(): JSX.Element {
  const t = useTranslation();
  const navigate = useNavigate();
  const { licenseTier, username, logout } = useAppStore();

  const [devices, setDevices] = useState<DeviceData[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [prediction, setPrediction] = useState<PredictionData | null>(null);
  const [trendData] = useState(generateMockTrend());
  const [loading, setLoading] = useState(false);

  const isAllowed = licenseTier === 'BANK';

  useEffect(() => {
    devicesAPI.list().then((r) => setDevices(r.data.data)).catch(console.error);
  }, []);

  const handlePredict = async (): Promise<void> => {
    if (!selectedId) return;
    setLoading(true);
    try {
      const lastPoint = trendData[trendData.length - 1];
      const res = await aiAPI.predict(selectedId, {
        cpu_percent: lastPoint.cpu,
        ram_percent: lastPoint.ram,
        error_rate: lastPoint.errors,
        latency_ms: 10 + Math.random() * 40,
      });
      setPrediction(res.data.data);
    } catch (err) {
      console.error(err);
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
          <button onClick={() => navigate('/ai')} className="text-sm text-brand-400">{t('nav.ai')}</button>
          <button onClick={() => navigate('/license')} className="text-sm text-gray-400 hover:text-white">{t('nav.license')}</button>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-400">{username}</span>
          <LicenseBadge tier={licenseTier} />
          <LanguageSelector />
          <button onClick={() => { logout(); navigate('/setup'); }} className="text-sm text-red-400 hover:text-red-300">{t('nav.logout')}</button>
        </div>
      </nav>

      <div className="flex-1 overflow-y-auto p-6">
        <h1 className="mb-6 text-2xl font-bold">{t('ai.title')}</h1>

        {/* Gate: non-Bank tiers see blurred overlay */}
        <div className={`relative ${!isAllowed ? 'pointer-events-none' : ''}`}>
          {!isAllowed && (
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center rounded-2xl bg-gray-950/80 backdrop-blur-sm">
              <p className="mb-4 text-lg font-semibold text-yellow-300">{t('ai.bank_required')}</p>
              <button
                className="rounded-lg bg-quantum-600 px-6 py-2 font-semibold hover:bg-quantum-500"
                onClick={() => navigate('/license')}
              >
                {t('ai.upgrade')}
              </button>
            </div>
          )}

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Left — device select + trend */}
            <div className="col-span-2 space-y-4">
              <div className="flex gap-3">
                <select
                  className="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-brand-500"
                  value={selectedId ?? ''}
                  onChange={(e) => setSelectedId(Number(e.target.value))}
                >
                  <option value="">{t('ai.select_device')}</option>
                  {devices.map((d) => (
                    <option key={d.id} value={d.id}>{d.hostname} ({d.ip_address})</option>
                  ))}
                </select>
                <button
                  onClick={handlePredict}
                  disabled={!selectedId || loading}
                  className="rounded-lg bg-brand-500 px-4 py-2 font-semibold hover:bg-brand-600 disabled:opacity-50"
                >
                  {loading ? '…' : 'Predict'}
                </button>
              </div>

              <div className="rounded-2xl border border-gray-800 bg-gray-900 p-4">
                <h3 className="mb-3 text-sm font-semibold uppercase text-gray-400">24h Metrics</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={trendData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#9ca3af' }} />
                    <YAxis tick={{ fontSize: 10, fill: '#9ca3af' }} />
                    <Tooltip contentStyle={{ background: '#1f2937', border: 'none' }} />
                    <Line type="monotone" dataKey="cpu" stroke="#0ea5e9" dot={false} name="CPU %" />
                    <Line type="monotone" dataKey="ram" stroke="#8b5cf6" dot={false} name="RAM %" />
                    <Line type="monotone" dataKey="errors" stroke="#ef4444" dot={false} name="Errors/s" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Right — prediction */}
            <div className="space-y-4">
              <div className="rounded-2xl border border-gray-800 bg-gray-900 p-6 text-center">
                <h3 className="mb-4 text-sm font-semibold uppercase text-gray-400">
                  {t('ai.probability')}
                </h3>
                {prediction ? (
                  <>
                    <GaugeSvg value={prediction.failure_probability} />
                    {prediction.time_to_failure_hours !== null && (
                      <p className="mt-3 text-sm text-gray-300">
                        {t('ai.ttf')}: <span className="font-bold text-red-400">
                          {t('ai.ttf_hours', { hours: prediction.time_to_failure_hours.toFixed(1) })}
                        </span>
                      </p>
                    )}
                    <p className="mt-2 text-xs text-gray-500">{prediction.message}</p>
                  </>
                ) : (
                  <p className="text-sm text-gray-500 mt-8">{t('ai.no_data')}</p>
                )}
              </div>

              {prediction?.alert_created && (
                <div className="rounded-lg border border-red-700 bg-red-950 p-4 text-sm text-red-200">
                  ⚠️ Alert created for this device
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
