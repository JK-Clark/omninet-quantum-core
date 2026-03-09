// © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
// Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
import React from 'react'
import { AlertTriangle, AlertCircle, Info } from 'lucide-react'

const SEVERITY_ICONS = {
  critical: <AlertCircle className="text-alert-red w-4 h-4 shrink-0" />,
  warning: <AlertTriangle className="text-yellow-400 w-4 h-4 shrink-0" />,
  info: <Info className="text-cyber-blue w-4 h-4 shrink-0" />,
}

const SEVERITY_BORDER = {
  critical: 'border-alert-red/40',
  warning: 'border-yellow-400/40',
  info: 'border-cyber-blue/40',
}

export default function AlertPanel({ alerts = [] }) {
  if (alerts.length === 0) {
    return (
      <div className="text-gray-600 font-mono text-xs text-center py-6">
        No active alerts
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2 max-h-72 overflow-y-auto pr-1">
      {alerts.map((alert, idx) => {
        const severity = alert.severity?.toLowerCase() || 'info'
        return (
          <div
            key={alert.id || idx}
            className={`flex items-start gap-3 bg-dark-card border rounded p-3 ${SEVERITY_BORDER[severity] || SEVERITY_BORDER.info}`}
          >
            {SEVERITY_ICONS[severity] || SEVERITY_ICONS.info}
            <div className="flex flex-col gap-0.5 min-w-0">
              <span className="text-gray-200 font-mono text-xs font-semibold truncate">
                {alert.device || alert.source || 'Unknown device'}
              </span>
              <span className="text-gray-400 font-mono text-xs break-words">
                {alert.message || alert.description || 'No details'}
              </span>
              {alert.timestamp && (
                <span className="text-gray-600 font-mono text-[10px]">
                  {new Date(alert.timestamp).toLocaleString()}
                </span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
