// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import ReactFlow, {
  addEdge,
  Background,
  Connection,
  Controls,
  Edge,
  MiniMap,
  Node,
  useEdgesState,
  useNodesState,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../i18n';
import LanguageSelector from '../components/LanguageSelector';
import LicenseBadge from '../components/LicenseBadge';
import AlertPanel from '../components/AlertPanel';
import { useAppStore } from '../store/appStore';
import { devicesAPI, topologyAPI } from '../api/client';
import type { DeviceData } from '../api/client';

// ─── Custom node colors ───────────────────────────────────────────────────────
const TYPE_COLORS: Record<string, string> = {
  cisco_ios: '#0ea5e9',
  cisco_nxos: '#0284c7',
  arista_eos: '#10b981',
  juniper_junos: '#f59e0b',
  unknown: '#6b7280',
};

function deviceLabel(d: DeviceData): string {
  return `${d.hostname}\n${d.ip_address}`;
}

function buildNodes(devices: DeviceData[]): Node[] {
  return devices.map((d, i) => ({
    id: String(d.id),
    data: { label: deviceLabel(d), device: d },
    position: {
      x: 150 + (i % 5) * 220,
      y: 80 + Math.floor(i / 5) * 180,
    },
    style: {
      background: TYPE_COLORS[d.device_type] ?? TYPE_COLORS.unknown,
      color: '#fff',
      borderRadius: 10,
      border: d.status === 'online' ? '2px solid #22c55e' : '2px solid #ef4444',
      padding: 12,
      minWidth: 140,
      fontSize: 12,
      fontFamily: 'monospace',
      whiteSpace: 'pre' as const,
    },
  }));
}

function buildEdges(links: { source_device_id: number; target_device_id: number; bandwidth?: number }[]): Edge[] {
  return links.map((l, i) => ({
    id: `e-${l.source_device_id}-${l.target_device_id}-${i}`,
    source: String(l.source_device_id),
    target: String(l.target_device_id),
    style: {
      stroke:
        l.bandwidth && l.bandwidth >= 1000
          ? '#22c55e'
          : l.bandwidth && l.bandwidth >= 100
          ? '#eab308'
          : '#ef4444',
      strokeWidth: 2,
    },
    animated: true,
  }));
}

export default function Dashboard(): JSX.Element {
  const t = useTranslation();
  const navigate = useNavigate();
  const { logout, licenseTier, username } = useAppStore();
  const wsRef = useRef<WebSocket | null>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedDevice, setSelectedDevice] = useState<DeviceData | null>(null);
  const [alerts, setAlerts] = useState<{ id: number; device_id: number; severity: string; message: string; predicted_at: string; is_resolved: boolean }[]>([]);

  const onConnect = useCallback((params: Connection) => setEdges((eds) => addEdge(params, eds)), [setEdges]);

  // Load initial topology via REST
  useEffect(() => {
    topologyAPI.map().then((res) => {
      const { nodes: n, links: l } = res.data.data;
      setNodes(buildNodes(n));
      setEdges(buildEdges(l));
    }).catch(console.error);
  }, [setNodes, setEdges]);

  // Real-time updates via WebSocket
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/topology`);
    wsRef.current = ws;
    ws.onmessage = (evt) => {
      const msg = JSON.parse(evt.data as string);
      if (msg.type === 'topology_update') {
        setNodes(buildNodes(msg.data.nodes));
        setEdges(buildEdges(msg.data.links));
      }
    };
    return () => ws.close();
  }, [setNodes, setEdges]);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedDevice((node.data as { device: DeviceData }).device);
  }, []);

  return (
    <div className="flex h-screen flex-col bg-gray-950 text-gray-100">
      {/* Navbar */}
      <nav className="flex items-center justify-between border-b border-gray-800 px-6 py-3">
        <div className="flex items-center gap-4">
          <span className="text-lg font-bold text-brand-500">OmniNet</span>
          <button onClick={() => navigate('/')} className="text-sm text-gray-400 hover:text-white">{t('nav.dashboard')}</button>
          <button onClick={() => navigate('/ai')} className="text-sm text-gray-400 hover:text-white">{t('nav.ai')}</button>
          <button onClick={() => navigate('/license')} className="text-sm text-gray-400 hover:text-white">{t('nav.license')}</button>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-400">{username}</span>
          <LicenseBadge tier={licenseTier} />
          <LanguageSelector />
          <button onClick={() => { logout(); navigate('/setup'); }} className="text-sm text-red-400 hover:text-red-300">{t('nav.logout')}</button>
        </div>
      </nav>

      {/* Main */}
      <div className="flex flex-1 overflow-hidden">
        {/* Flow canvas */}
        <div className="flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            fitView
          >
            <Background color="#374151" gap={24} />
            <Controls />
            <MiniMap nodeColor={(n) => (n.style?.background as string) ?? '#6b7280'} maskColor="rgba(0,0,0,0.5)" />
          </ReactFlow>
        </div>

        {/* Sidebar */}
        <aside className="w-72 shrink-0 overflow-y-auto border-l border-gray-800 bg-gray-900 p-4 space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">
            {t('dashboard.title')}
          </h2>

          {selectedDevice && (
            <div className="rounded-lg border border-gray-700 bg-gray-800 p-4 space-y-2 text-sm">
              <h3 className="font-semibold text-white">{t('dashboard.sidebar.device')}</h3>
              <div className="space-y-1 text-gray-300">
                <p><span className="text-gray-500">{t('dashboard.sidebar.ip')}:</span> {selectedDevice.ip_address}</p>
                <p><span className="text-gray-500">{t('dashboard.sidebar.vendor')}:</span> {selectedDevice.vendor}</p>
                <p><span className="text-gray-500">{t('dashboard.sidebar.os')}:</span> {selectedDevice.os_version ?? '—'}</p>
                <p>
                  <span className="text-gray-500">{t('dashboard.sidebar.status')}:</span>{' '}
                  <span className={selectedDevice.status === 'online' ? 'text-green-400' : 'text-red-400'}>
                    {selectedDevice.status}
                  </span>
                </p>
              </div>
            </div>
          )}

          <AlertPanel alerts={alerts} />
        </aside>
      </div>
    </div>
  );
}
