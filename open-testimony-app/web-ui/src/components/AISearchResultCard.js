import React, { useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Clock, Film, MessageSquare, Play, Tag, CheckSquare, Square } from 'lucide-react';
import { useAuth } from '../auth';
import QuickTagMenu from './QuickTagMenu';

function formatTimestamp(ms) {
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min}:${sec.toString().padStart(2, '0')}`;
}

export default function AISearchResultCard({
  result, mode, onClick, availableTags, tagCounts, onVideoTagsChanged,
  selectable, selected, onToggleSelect,
}) {
  const { user } = useAuth();
  const isVisual = mode === 'visual_text' || mode === 'visual_image';
  const score = result.score != null ? result.score : null;
  const scorePercent = score != null ? Math.round(score * 100) : null;
  const [imgError, setImgError] = useState(false);
  const [showTagMenu, setShowTagMenu] = useState(false);
  const [localTags, setLocalTags] = useState(null); // tags fetched/saved via QuickTagMenu
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0 });
  const tagBtnRef = useRef(null);

  const canEdit = user?.role === 'admin' || user?.role === 'staff';

  const thumbnailUrl = result.thumbnail_url
    ? `/ai-search${result.thumbnail_url}`
    : null;

  const handleTagButton = (e) => {
    e.stopPropagation();
    if (!showTagMenu && tagBtnRef.current) {
      const rect = tagBtnRef.current.getBoundingClientRect();
      // Position menu below the button, right-aligned
      setMenuPos({
        top: rect.bottom + 4,
        left: Math.max(8, rect.right - 288), // 288 = w-72 (18rem)
      });
    }
    setShowTagMenu(prev => !prev);
  };

  const handleTagsChanged = (videoId, newTags) => {
    setLocalTags(newTags);
    onVideoTagsChanged?.(videoId, newTags);
  };

  const handleCheckbox = (e) => {
    e.stopPropagation();
    onToggleSelect?.(result);
  };

  const displayTags = localTags || result.incident_tags || null;

  return (
    <div
      onClick={() => onClick(result)}
      className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden cursor-pointer hover:border-blue-500 hover:bg-gray-750 transition relative"
    >
      <div className="flex">
        {/* Checkbox for bulk select */}
        {selectable && (
          <button
            onClick={handleCheckbox}
            className="flex items-center justify-center w-8 shrink-0 bg-gray-900/50 hover:bg-gray-700 transition"
          >
            {selected ? (
              <CheckSquare size={16} className="text-blue-400" />
            ) : (
              <Square size={16} className="text-gray-600" />
            )}
          </button>
        )}

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
            <div className="flex items-center gap-2 shrink-0">
              {canEdit && (
                <button
                  ref={tagBtnRef}
                  onClick={handleTagButton}
                  className="p-1.5 rounded hover:bg-gray-700 transition text-gray-400 hover:text-blue-400"
                  title="Quick Tag"
                >
                  <Tag size={18} />
                </button>
              )}
              {scorePercent != null && (
                <div className="flex items-center gap-2">
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

          {/* Tag pills */}
          {displayTags && displayTags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1.5">
              {displayTags.map(tag => (
                <span
                  key={tag}
                  className="px-1.5 py-0.5 bg-blue-900/20 border border-blue-500/30 rounded-full text-[10px] text-blue-300"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* QuickTagMenu popover — rendered via portal to escape overflow-hidden */}
      {showTagMenu && canEdit && createPortal(
        <div
          className="fixed z-[9999]"
          style={{ top: menuPos.top, left: menuPos.left }}
          onClick={e => e.stopPropagation()}
        >
          <QuickTagMenu
            videoIds={[result.video_id]}
            availableTags={availableTags || []}
            tagCounts={tagCounts}
            onClose={() => setShowTagMenu(false)}
            onTagsChanged={handleTagsChanged}
          />
        </div>,
        document.body
      )}
    </div>
  );
}
