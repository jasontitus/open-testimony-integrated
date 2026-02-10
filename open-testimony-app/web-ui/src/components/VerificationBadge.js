import React from 'react';
import { CheckCircle, AlertCircle, Clock, ShieldAlert, ShieldCheck, AlertTriangle } from 'lucide-react';

const STATUS_CONFIG = {
  'verified': { label: 'Verified', icon: CheckCircle, className: 'bg-green-900/30 border-green-500/50 text-green-400' },
  'verified-mvp': { label: 'Verified (MVP)', icon: ShieldCheck, className: 'bg-green-900/30 border-green-500/50 text-green-400' },
  'signed-upload': { label: 'Signed Upload', icon: ShieldCheck, className: 'bg-blue-900/30 border-blue-500/50 text-blue-400' },
  'error-mvp': { label: 'Unverified', icon: AlertTriangle, className: 'bg-yellow-900/30 border-yellow-500/50 text-yellow-400' },
  'error': { label: 'Error', icon: ShieldAlert, className: 'bg-orange-900/30 border-orange-500/50 text-orange-400' },
  'failed': { label: 'Failed', icon: AlertCircle, className: 'bg-red-900/30 border-red-500/50 text-red-400' },
  'pending': { label: 'Pending', icon: Clock, className: 'bg-yellow-900/30 border-yellow-500/50 text-yellow-400' },
};

export default function VerificationBadge({ status }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG['pending'];
  const Icon = config.icon;

  return (
    <span className={`flex items-center px-1.5 py-0.5 border rounded text-[10px] font-bold uppercase tracking-wider ${config.className}`}>
      <Icon size={10} className="mr-1" />
      {config.label}
    </span>
  );
}
