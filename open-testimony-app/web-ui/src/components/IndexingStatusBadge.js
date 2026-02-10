import React from 'react';
import { Loader, CheckCircle, AlertCircle, Clock } from 'lucide-react';

const STATUS_CONFIG = {
  completed: { icon: CheckCircle, color: 'text-green-400', bg: 'bg-green-900/20 border-green-500/30', label: 'Indexed' },
  processing: { icon: Loader, color: 'text-yellow-400', bg: 'bg-yellow-900/20 border-yellow-500/30', label: 'Indexing' },
  pending: { icon: Clock, color: 'text-blue-400', bg: 'bg-blue-900/20 border-blue-500/30', label: 'Pending' },
  failed: { icon: AlertCircle, color: 'text-red-400', bg: 'bg-red-900/20 border-red-500/30', label: 'Failed' },
};

export default function IndexingStatusBadge({ status }) {
  if (!status) return null;

  const config = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
  const Icon = config.icon;

  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 border rounded text-[10px] font-bold uppercase tracking-wider ${config.bg} ${config.color}`}>
      <Icon size={10} className={status === 'processing' ? 'animate-spin' : ''} />
      {config.label}
    </span>
  );
}
