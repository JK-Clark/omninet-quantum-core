import React from 'react';
import { useTranslation } from '../i18n';

export interface Alert {
  id: number;
  device_id: number;
  severity: string;
  message: string;
  predicted_at: string;
  is_resolved: boolean;
}

interface Props {
  alerts: Alert[];
  onAcknowledge?: (alertId: number) => void;
}

export default function AlertPanel({ alerts, onAcknowledge }: Props): JSX.Element {
  const t = useTranslation();
  const active = alerts.filter((a) => !a.is_resolved);

  if (active.length === 0) {
    return (
      <div className="rounded-lg border border-gray-700 bg-gray-900 p-4 text-center text-sm text-gray-400">
        {t('alerts.none')}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-400">
        {t('alerts.title')}
      </h3>
      {active.map((alert) => (
        <div
          key={alert.id}
          className={`flex items-start justify-between rounded-lg border p-3 ${
            alert.severity === 'critical'
              ? 'border-red-700 bg-red-950 text-red-200'
              : 'border-yellow-700 bg-yellow-950 text-yellow-200'
          }`}
        >
          <div className="flex-1">
            <div className="flex items-center gap-2 text-xs font-bold uppercase">
              <span
                className={`h-2 w-2 rounded-full ${
                  alert.severity === 'critical' ? 'bg-red-400' : 'bg-yellow-400'
                }`}
              />
              {t(`alerts.severity.${alert.severity}`)} — Device #{alert.device_id}
            </div>
            <p className="mt-1 text-sm">{alert.message}</p>
            <p className="mt-0.5 text-xs opacity-70">
              {new Date(alert.predicted_at).toLocaleString()}
            </p>
          </div>
          {onAcknowledge && (
            <button
              onClick={() => onAcknowledge(alert.id)}
              className="ml-3 shrink-0 rounded bg-gray-700 px-2 py-1 text-xs hover:bg-gray-600"
            >
              ✓
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
