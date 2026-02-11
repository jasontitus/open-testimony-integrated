import React, { useState } from 'react';
import { Clock, Film, MessageSquare, Play } from 'lucide-react';

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
  const [imgError, setImgError] = useState(false);

  const thumbnailUrl = result.thumbnail_url
    ? `/ai-search${result.thumbnail_url}`
    : null;

  return (
    <div
      onClick={() => onClick(result)}
      className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden cursor-pointer hover:border-blue-500 hover:bg-gray-750 transition flex"
    >
      {/* Thumbnail */}
      <div className="w-40 h-24 bg-gray-900 shrink-0 relative">
        {thumbnailUrl && !imgError ? (
          <img
            src={thumbnailUrl}
            alt=""
            className="w-full h-full object-cover"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Film size={24} className="text-gray-700" />
          </div>
        )}
        {/* Play icon overlay */}
        <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 hover:opacity-100 transition-opacity">
          <Play size={28} className="text-white" fill="white" />
        </div>
      </div>

      {/* Info */}
      <div className="flex-1 p-3 min-w-0">
        <div className="flex items-start justify-between mb-1">
          <div className="flex items-center gap-2">
            {isVisual ? (
              <Film size={12} className="text-purple-400" />
            ) : (
              <MessageSquare size={12} className="text-green-400" />
            )}
            <span className="text-xs font-mono text-gray-400 truncate max-w-[140px]">
              {result.video_id.slice(0, 8)}...
            </span>
          </div>
          {scorePercent != null && (
            <div className="flex items-center gap-2 shrink-0">
              <div className="w-12 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${scorePercent}%`,
                    backgroundColor: scorePercent > 70 ? '#22c55e' : scorePercent > 40 ? '#eab308' : '#ef4444',
                  }}
                />
              </div>
              <span className="text-[10px] font-mono text-gray-400">{scorePercent}%</span>
            </div>
          )}
        </div>

        {/* Timestamp */}
        <div className="flex items-center gap-1 text-xs text-gray-300 mb-1">
          <Clock size={10} className="text-gray-500" />
          {isVisual ? (
            <span>Frame at {formatTimestamp(result.timestamp_ms)}</span>
          ) : (
            <span>{formatTimestamp(result.start_ms)} &ndash; {formatTimestamp(result.end_ms)}</span>
          )}
        </div>

        {/* Transcript text */}
        {result.segment_text && (
          <p className="text-xs text-gray-400 line-clamp-2 leading-relaxed">
            &ldquo;{result.segment_text}&rdquo;
          </p>
        )}
      </div>
    </div>
  );
}
