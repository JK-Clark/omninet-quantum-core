// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import React, { useEffect, useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  RadialBarChart,
  RadialBar,
  Legend,
} from 'recharts'
import { AlertTriangle, Download, TrendingDown } from 'lucide-react'
import apiClient from '../api/client'
import useAppStore from '../store/appStore'
import { t } from '../i18n'
import NavBar from '../components/NavBar'

// Demo data when backend is unavailable
const DEMO_PREDICTIONS = [
  {
    device_id: 'sw-01',
    hostname: 'Switch-Core-01',
    health_score: 87,
    risk: false,
    recommendations: [],
    timeline: Array.from({ length: 24 }, (_, i) => ({
      hour: `${String(i).padStart(2, '0')}:00`,
      score: Math.max(60, 87 - Math.round(Math.sin(i / 4) * 8)),
    })),
  },
  {
    device_id: 'sw-02',
    hostname: 'Switch-Edge-02',
    health_score: 62,
    risk: true,
    recommendations: ['Check interface GE0/1 — high error rate', 'Firmware update available'],
    timeline: Array.from({ length: 24 }, (_, i) => ({
      hour: `${String(i).padStart(2, '0')}:00`,
      score: Math.max(40, 62 - Math.round(Math.random() * 15)),
    })),
  },
  {
    device_id: 'r-01',
    hostname: 'Router-WAN-01',
    health_score: 45,
    risk: true,
    recommendations: ['High CPU utilization detected', 'BGP peer flapping', 'Consider traffic redistribution'],
    timeline: Array.from({ length: 24 }, (_, i) => ({
      hour: `${String(i).padStart(2, '0')}:00`,
      score: Math.max(20, 45 - Math.round(Math.sin(i / 3) * 12)),
    })),
  },
]

function HealthGauge({ score }) {
  const color = score >= 70 ? '#00ff88' : score >= 50 ? '#facc15' : '#ff0066'
  const data = [{ name: 'Health', value: score, fill: color }]
  return (
    <div className="flex flex-col items-center gap-2">
      <RadialBarChart
        width={160}
        height={160}
        innerRadius={50}
        outerRadius={70}
        data={data}
        startAngle={180}
        endAngle={0}
      >
        <RadialBar dataKey="value" cornerRadius={6} background={{ fill: '#1a1a1a' }} />
      </RadialBarChart>
      <span
        className="font-mono text-3xl font-bold"
        style={{ color }}
      >
        {score}%
      </span>
      <span className="text-gray-500 font-mono text-xs">Global Health</span>
    </div>
  )
}

export default function AIPredictor() {
  const { language } = useAppStore()
  const [predictions, setPredictions] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)
  const [reportLoading, setReportLoading] = useState(false)

  useEffect(() => {
    apiClient
      .get('/ai/predictions')
      .then((res) => {
        const data = Array.isArray(res.data) ? res.data : res.data.predictions || []
        setPredictions(data.length ? data : DEMO_PREDICTIONS)
        setSelected(data[0] || DEMO_PREDICTIONS[0])
      })
      .catch(() => {
        setPredictions(DEMO_PREDICTIONS)
        setSelected(DEMO_PREDICTIONS[0])
      })
      .finally(() => setLoading(false))
  }, [])

  const globalScore =
    predictions.length > 0
      ? Math.round(predictions.reduce((acc, p) => acc + (p.health_score || 0), 0) / predictions.length)
      : 0

  const atRisk = predictions.filter((p) => (p.health_score || 0) < 70)

  const handleReport = async (deviceId) => {
    setReportLoading(true)
    try {
      const res = await apiClient.get(`/reports/generate?device_id=${deviceId}`, {
        responseType: 'blob',
      })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `report-${deviceId}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      console.warn('Report generation failed:', err.message)
    } finally {
      setReportLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-dark-bg flex flex-col">
        <NavBar />
        <div className="flex-1 flex items-center justify-center">
          <span className="text-neon-green font-mono animate-pulse">Loading predictions…</span>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-dark-bg flex flex-col">
      <NavBar />

      <main className="flex-1 p-6 flex flex-col gap-6">
        <h1 className="text-neon-green font-mono font-bold text-xl tracking-wider">
          {t('ai.title', language)}
        </h1>

        <div className="flex flex-col xl:flex-row gap-6">
          {/* Left column */}
          <div className="flex flex-col gap-6 flex-1 min-w-0">
            {/* Global health gauge */}
            <div className="bg-dark-card border border-neon-green/10 rounded-lg p-6 flex flex-col sm:flex-row items-center gap-6">
              <HealthGauge score={globalScore} />
              <div className="flex flex-col gap-2">
                <h2 className="text-gray-300 font-mono text-sm font-semibold">
                  {t('ai.health_score', language)}
                </h2>
                <p className="text-gray-500 font-mono text-xs max-w-xs">
                  Predictive health across {predictions.length} monitored device
                  {predictions.length !== 1 ? 's' : ''}. Scores below 70% indicate
                  elevated risk and require attention.
                </p>
                {atRisk.length > 0 && (
                  <span className="flex items-center gap-1 text-alert-red font-mono text-xs mt-1">
                    <AlertTriangle size={12} /> {atRisk.length} device{atRisk.length !== 1 ? 's' : ''} at risk
                  </span>
                )}
              </div>
            </div>

            {/* Device selector + chart */}
            <div className="bg-dark-card border border-neon-green/10 rounded-lg p-6 flex flex-col gap-4">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <h2 className="text-gray-300 font-mono text-sm font-semibold">
                  {t('ai.prediction', language)} — 24h
                </h2>
                <select
                  value={selected?.device_id || ''}
                  onChange={(e) =>
                    setSelected(predictions.find((p) => p.device_id === e.target.value) || null)
                  }
                  className="bg-dark-surface border border-neon-green/20 text-neon-green font-mono text-xs rounded px-2 py-1 focus:outline-none"
                >
                  {predictions.map((p) => (
                    <option key={p.device_id} value={p.device_id} className="bg-dark-surface">
                      {p.hostname || p.device_id}
                    </option>
                  ))}
                </select>
              </div>
              {selected?.timeline && (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={selected.timeline} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff08" />
                    <XAxis
                      dataKey="hour"
                      tick={{ fill: '#6b7280', fontFamily: 'monospace', fontSize: 10 }}
                      tickLine={false}
                      axisLine={{ stroke: '#374151' }}
                      interval={3}
                    />
                    <YAxis
                      domain={[0, 100]}
                      tick={{ fill: '#6b7280', fontFamily: 'monospace', fontSize: 10 }}
                      tickLine={false}
                      axisLine={{ stroke: '#374151' }}
                    />
                    <Tooltip
                      contentStyle={{
                        background: '#111111',
                        border: '1px solid #00ff8833',
                        fontFamily: 'monospace',
                        fontSize: 12,
                        color: '#e0e0e0',
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="score"
                      stroke="#00ff88"
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4, fill: '#00ff88' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>

          {/* Right column — at-risk devices */}
          <div className="w-full xl:w-80 flex flex-col gap-4">
            <h2 className="text-gray-300 font-mono text-sm font-semibold flex items-center gap-2">
              <TrendingDown size={14} className="text-alert-red" /> Devices at Risk
            </h2>
            {atRisk.length === 0 ? (
              <div className="bg-dark-card border border-neon-green/10 rounded-lg p-4 text-gray-600 font-mono text-xs">
                ✅ All devices healthy
              </div>
            ) : (
              atRisk.map((p) => (
                <div
                  key={p.device_id}
                  className="bg-dark-card border border-alert-red/20 rounded-lg p-4 flex flex-col gap-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-gray-200 font-mono text-xs font-semibold">
                      {p.hostname || p.device_id}
                    </span>
                    <span
                      className={`font-mono text-sm font-bold ${
                        p.health_score < 50 ? 'text-alert-red' : 'text-yellow-400'
                      }`}
                    >
                      {p.health_score}%
                    </span>
                  </div>
                  {p.recommendations?.length > 0 && (
                    <ul className="flex flex-col gap-1">
                      {p.recommendations.map((rec, i) => (
                        <li key={i} className="text-gray-400 font-mono text-[11px] flex gap-1.5">
                          <span className="text-alert-red">›</span> {rec}
                        </li>
                      ))}
                    </ul>
                  )}
                  <button
                    onClick={() => handleReport(p.device_id)}
                    disabled={reportLoading}
                    className="flex items-center justify-center gap-1.5 py-1.5 border border-cyber-blue/40 text-cyber-blue font-mono text-xs rounded hover:bg-cyber-blue/10 transition-colors disabled:opacity-50"
                  >
                    <Download size={11} /> {t('ai.generate_report', language)}
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
