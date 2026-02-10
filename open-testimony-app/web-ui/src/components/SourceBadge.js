import React from 'react';

export default function SourceBadge({ source }) {
  if (source === 'live') {
    return (
      <span className="px-1.5 py-0.5 bg-green-900/30 border border-green-500/50 rounded text-[10px] text-green-400 font-bold uppercase tracking-wider">
        LIVE
      </span>
    );
  }
  if (source === 'upload') {
    return (
      <span className="px-1.5 py-0.5 bg-purple-900/30 border border-purple-500/50 rounded text-[10px] text-purple-400 font-bold uppercase tracking-wider">
        IMPORTED
      </span>
    );
  }
  return null;
}
