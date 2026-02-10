import React from 'react';
import { Clock, Film, MessageSquare } from 'lucide-react';
import VerificationBadge from './VerificationBadge';

function formatTimestamp(ms) {
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min}:${sec.toString().padStart(2, '0')}`;
}

export default function AISearchResultCard({ result, mode, onClick }) {
  const isVisual = mode === 'visual_text' || mode === 'visual_image';
  const score = result.score != null ? result.score : null;
  const scorePercent = score != null ? Math.round(score * 100) : null;

  return (
    <div
      onClick={() => onClick(result)}
      className="bg-gray-800 border border-gray-700 rounded-lg p-4 cursor-pointer hover:border-blue-500 hover:bg-gray-750 transition"
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          {isVisual ? (
            <Film size={14} className="text-purple-400" />
          ) : (
            <MessageSquare size={14} className="text-green-400" />
          )}
          <span className="text-xs font-mono text-gray-400 truncate max-w-[200px]">
            {result.video_id.slice(0, 8)}...
          </span>
        </div>
        {scorePercent != null && (
          <div className="flex items-center gap-2 shrink-0">
            <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${scorePercent}%`,
                  backgroundColor: scorePercent > 70 ? '#22c55e' : scorePercent > 40 ? '#eab308' : '#ef4444',
                }}
              />
            </div>
            <span className="text-xs font-mono text-gray-400">{scorePercent}%</span>
          </div>
        )}
      </div>

      {/* Timestamp */}
      <div className="flex items-center gap-1 text-sm text-gray-300 mb-2">
        <Clock size={12} className="text-gray-500" />
        {isVisual ? (
          <span>Frame at {formatTimestamp(result.timestamp_ms)}</span>
        ) : (
          <span>{formatTimestamp(result.start_ms)} &ndash; {formatTimestamp(result.end_ms)}</span>
        )}
      </div>

      {/* Transcript text (for transcript results) */}
      {result.segment_text && (
        <p className="text-sm text-gray-400 line-clamp-3 leading-relaxed">
          &ldquo;{result.segment_text}&rdquo;
        </p>
      )}

      {/* Verification badge if enriched */}
      {result.verification_status && (
        <div className="mt-2">
          <VerificationBadge status={result.verification_status} />
        </div>
      )}
    </div>
  );
}
