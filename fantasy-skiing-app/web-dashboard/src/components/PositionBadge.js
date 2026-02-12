import React from 'react';

const MEDAL_COLORS = {
  1: 'bg-yellow-400 text-yellow-900',
  2: 'bg-gray-300 text-gray-800',
  3: 'bg-amber-600 text-amber-100',
};

export default function PositionBadge({ position }) {
  const style = MEDAL_COLORS[position] || 'bg-snow-100 text-snow-700';
  return (
    <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold ${style}`}>
      {position}
    </span>
  );
}
