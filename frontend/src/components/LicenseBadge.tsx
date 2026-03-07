import React from 'react';
import { useTranslation } from '../i18n';

const TIER_COLORS: Record<string, string> = {
  TRIAL: 'bg-yellow-700 text-yellow-100',
  COMMUNITY: 'bg-blue-700 text-blue-100',
  BANK: 'bg-quantum-600 text-white',
};

interface Props {
  tier: string;
}

export default function LicenseBadge({ tier }: Props): JSX.Element {
  const t = useTranslation();
  const colorClass = TIER_COLORS[tier] ?? 'bg-gray-700 text-gray-100';
  const label = t(`badge.${tier.toLowerCase()}`);

  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-0.5 text-xs font-semibold ${colorClass}`}
    >
      {tier === 'BANK' && <span className="mr-1">🔐</span>}
      {label}
    </span>
  );
}
