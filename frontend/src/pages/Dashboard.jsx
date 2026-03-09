// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import React, { useEffect, useState, useCallback } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Server, RefreshCw } from 'lucide-react'
import apiClient from '../api/client'
import useAppStore from '../store/appStore'
import { t } from '../i18n'
import NavBar from '../components/NavBar'
import AlertPanel from '../components/AlertPanel'

// Demo topology used when backend is unavailable
const DEMO_NODES = [
  { id: 'r1', position: { x: 300, y: 50 }, data: { label: 'Router-Core', status: 'UP', type: 'router', ip: '10.0.0.1' }, type: 'default' },
  { id: 'r2', position: { x: 600, y: 50 }, data: { label: 'Router-Edge', status: 'UP', type: 'router', ip: '10.0.0.2' }, type: 'default' },
  { id: 's1', position: { x: 100, y: 200 }, data: { label: 'Switch-A', status: 'UP', type: 'switch', ip: '10.0.1.1' }, type: 'default' },
  { id: 's2', position: { x: 400, y: 200 }, data: { label: 'Switch-B', status: 'WARNING', type: 'switch', ip: '10.0.1.2' }, type: 'default' },
  { id: 's3', position: { x: 700, y: 200 }, data: { label: 'Switch-C', status: 'DOWN', type: 'switch', ip: '10.0.1.3' }, type: 'default' },
]

const DEMO_EDGES = [
  { id: 'e1', source: 'r1', target: 's1' },
  { id: 'e2', source: 'r1', target: 's2' },
  { id: 'e3', source: 'r2', target: 's2' },
  { id: 'e4', source: 'r2', target: 's3' },
]

const STATUS_COLOR = { UP: '#00ff88', WARNING: '#facc15', DOWN: '#ff0066' }

function buildFlowNodes(apiNodes) {
  return apiNodes.map((n, idx) => ({
    id: String(n.id || idx),
    position: n.position || { x: (idx % 5) * 180 + 50, y: Math.floor(idx / 5) * 150 + 50 },
    data: { label: n.hostname || n.ip || `Node-${idx}`, status: n.status || 'UP', ...n },
    style: {
      background: '#1a1a1a',
      border: `1.5px solid ${STATUS_COLOR[n.status] || STATUS_COLOR.UP}`,
      color: '#e0e0e0',
      fontFamily: 'monospace',
      fontSize: 11,
      borderRadius: 6,
      padding: '6px 12px',
    },
  }))
}

function buildFlowEdges(apiEdges) {
  return apiEdges.map((e, idx) => ({
    id: String(e.id || idx),
    source: String(e.source),
    target: String(e.target),
    style: { stroke: '#00ff8844' },
  }))
}

const demoNodes = buildFlowNodes(
  DEMO_NODES.map((n) => ({ id: n.id, hostname: n.data.label, status: n.data.status, ip: n.data.ip, position: n.position }))
)
const demoEdges = buildFlowEdges(DEMO_EDGES)

export default function Dashboard() {
  const { language } = useAppStore()
  const [nodes, setNodes, onNodesChange] = useNodesState(demoNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(demoEdges)
  const [alerts, setAlerts] = useState([])
  const [selectedNode, setSelectedNode] = useState(null)
  const [stats, setStats] = useState({ total: 0, up: 0, down: 0, alertCount: 0 })
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [topoRes, alertsRes] = await Promise.allSettled([
        apiClient.get('/topology'),
        apiClient.get('/devices/alerts'),
      ])

      if (topoRes.status === 'fulfilled') {
        const topo = topoRes.value.data
        const flowNodes = buildFlowNodes(topo.nodes || [])
        const flowEdges = buildFlowEdges(topo.edges || topo.links || [])
        setNodes(flowNodes.length ? flowNodes : demoNodes)
        setEdges(flowEdges.length ? flowEdges : demoEdges)

        const allNodes = topo.nodes || []
        const upCount = allNodes.filter((n) => n.status === 'UP').length
        const downCount = allNodes.filter((n) => n.status === 'DOWN').length
        setStats({
          total: allNodes.length || demoNodes.length,
          up: upCount,
          down: downCount,
          alertCount: 0,
        })
      } else {
        setNodes(demoNodes)
        setEdges(demoEdges)
        setStats({ total: demoNodes.length, up: 4, down: 1, alertCount: 0 })
      }

      if (alertsRes.status === 'fulfilled') {
        const alertData = alertsRes.value.data
        const list = Array.isArray(alertData) ? alertData : alertData.alerts || []
        setAlerts(list)
        setStats((s) => ({ ...s, alertCount: list.length }))
      }
    } catch {
      // fallback already set
    } finally {
      setLoading(false)
      setLastRefresh(new Date())
    }
  }, [setNodes, setEdges])

  // Initial fetch
  useEffect(() => { fetchData() }, [fetchData])

  // Auto-refresh every 30s
  useEffect(() => {
    const timer = setInterval(fetchData, 30000)
    return () => clearInterval(timer)
  }, [fetchData])

  // WebSocket for real-time updates
  useEffect(() => {
    let ws
    try {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${window.location.host}/ws/topology`)
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.nodes) setNodes(buildFlowNodes(data.nodes))
          if (data.edges || data.links) setEdges(buildFlowEdges(data.edges || data.links))
        } catch {
          // ignore parse errors
        }
      }
    } catch {
      // WebSocket not available
    }
    return () => { if (ws) ws.close() }
  }, [setNodes, setEdges])

  const nodeStyle = (status) => ({
    background: '#1a1a1a',
    border: `1.5px solid ${STATUS_COLOR[status] || STATUS_COLOR.UP}`,
    color: '#e0e0e0',
    fontFamily: 'monospace',
    fontSize: 11,
    borderRadius: 6,
    padding: '6px 12px',
  })

  const styledNodes = nodes.map((n) => ({
    ...n,
    style: nodeStyle(n.data?.status),
  }))

  return (
    <div className="min-h-screen bg-dark-bg flex flex-col">
      <NavBar />

      <main className="flex-1 p-6 flex flex-col gap-6">
        {/* Stats bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: t('dashboard.devices', language), value: stats.total, color: 'text-gray-300' },
            { label: 'UP', value: stats.up, color: 'text-neon-green' },
            { label: 'DOWN', value: stats.down, color: 'text-alert-red' },
            { label: 'Alerts', value: stats.alertCount, color: 'text-yellow-400' },
          ].map((s) => (
            <div
              key={s.label}
              className="bg-dark-card border border-neon-green/10 rounded-lg p-4 flex flex-col gap-1"
            >
              <span className="text-gray-500 font-mono text-xs uppercase tracking-widest">
                {s.label}
              </span>
              <span className={`font-mono text-3xl font-bold ${s.color}`}>{s.value}</span>
            </div>
          ))}
        </div>

        <div className="flex flex-col lg:flex-row gap-6 flex-1 min-h-0">
          {/* Topology */}
          <div className="flex-1 bg-dark-card border border-neon-green/10 rounded-lg flex flex-col overflow-hidden min-h-[400px]">
            <div className="flex items-center justify-between px-4 py-3 border-b border-neon-green/10">
              <h2 className="text-gray-300 font-mono text-sm font-semibold">
                {t('dashboard.topology', language)}
              </h2>
              <div className="flex items-center gap-3">
                {lastRefresh && (
                  <span className="text-gray-600 font-mono text-[10px]">
                    Updated {lastRefresh.toLocaleTimeString()}
                  </span>
                )}
                <button
                  onClick={fetchData}
                  disabled={loading}
                  className="text-gray-500 hover:text-neon-green transition-colors disabled:opacity-40"
                  title="Refresh"
                >
                  <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
                </button>
              </div>
            </div>
            <div className="flex-1 relative">
              <ReactFlow
                nodes={styledNodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onNodeClick={(_, node) => setSelectedNode(node)}
                fitView
                proOptions={{ hideAttribution: true }}
              >
                <Background color="#00ff8811" gap={24} />
                <Controls showInteractive={false} className="!bg-dark-surface !border-neon-green/20" />
                <MiniMap
                  nodeColor={(n) => STATUS_COLOR[n.data?.status] || '#00ff88'}
                  style={{ background: '#111111', border: '1px solid #00ff8822' }}
                />
              </ReactFlow>

              {/* Node detail panel */}
              {selectedNode && (
                <div className="absolute top-4 right-4 w-56 bg-dark-surface border border-neon-green/20 rounded-lg p-4 shadow-lg z-10">
                  <div className="flex items-center justify-between mb-3">
                    <Server size={14} className="text-neon-green" />
                    <button
                      onClick={() => setSelectedNode(null)}
                      className="text-gray-600 hover:text-gray-300 font-mono text-xs"
                    >
                      ✕
                    </button>
                  </div>
                  {Object.entries(selectedNode.data).map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-2 font-mono text-xs py-0.5 border-b border-gray-800 last:border-0">
                      <span className="text-gray-500 capitalize">{k}</span>
                      <span className="text-gray-300 truncate max-w-[110px]">
                        {String(v)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Alerts panel */}
          <div className="w-full lg:w-80 bg-dark-card border border-neon-green/10 rounded-lg flex flex-col">
            <div className="px-4 py-3 border-b border-neon-green/10">
              <h2 className="text-gray-300 font-mono text-sm font-semibold">
                Recent Alerts
              </h2>
            </div>
            <div className="p-4 flex-1 overflow-y-auto">
              <AlertPanel alerts={alerts} />
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
