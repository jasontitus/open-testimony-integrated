import React from 'react';

const STATUS_STYLES = {
  upcoming: 'bg-blue-100 text-blue-800',
  live: 'bg-red-100 text-red-800 animate-pulse',
  finished: 'bg-gray-100 text-gray-800',
  pending: 'bg-yellow-100 text-yellow-800',
  won: 'bg-green-100 text-green-800',
  lost: 'bg-red-100 text-red-700',
};

export default function StatusBadge({ status }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wide ${STATUS_STYLES[status] || 'bg-gray-100 text-gray-600'}`}>
      {status === 'live' && <span className="w-2 h-2 bg-red-500 rounded-full mr-1.5" />}
      {status}
    </span>
  );
}
