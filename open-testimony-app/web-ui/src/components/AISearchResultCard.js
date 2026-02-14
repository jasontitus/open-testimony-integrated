import React, { useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Clock, Film, Info, MessageSquare, Play, Tag, CheckSquare, Square } from 'lucide-react';
import { useAuth } from '../auth';
import QuickTagMenu from './QuickTagMenu';

function formatTimestamp(ms) {
  if (ms == null || isNaN(ms)) return '0:00';
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min}:${sec.toString().padStart(2, '0')}`;
}

function HighlightText({ text, query }) {
  if (!query || !text) return text || null;
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const parts = text.split(new RegExp(`(${escaped})`, 'gi'));
  return parts.map((part, i) =>
    part.toLowerCase() === query.toLowerCase()
      ? <mark key={i} className="bg-yellow-500/30 text-yellow-200 rounded-sm px-0.5">{part}</mark>
      : part
  );
}

export default function AISearchResultCard({
  result, mode, onClick, availableTags, tagCounts, onVideoTagsChanged, onCategoryChanged,
  selectable, selected, onToggleSelect, searchTiming, searchQuery,
}) {
  const { user } = useAuth();
  const isVisual = mode === 'visual_text' || mode === 'visual_image' || mode === 'combined' || mode === 'caption_semantic' || mode === 'caption_exact';
  const score = result.score != null ? result.score : null;
  const scorePercent = score != null ? Math.round(score * 100) : null;
  const [imgError, setImgError] = useState(false);
  const [showTagMenu, setShowTagMenu] = useState(false);
  const [showDiagnostic, setShowDiagnostic] = useState(false);
  const [localTags, setLocalTags] = useState(null);
  const [localCategory, setLocalCategory] = useState(null);
  const [menuPos, setMenuPos] = useState({ top: 0, left: 0 });
  const annotateBtnRef = useRef(null);

  const canEdit = user?.role === 'admin' || user?.role === 'staff';

  const thumbnailUrl = result.thumbnail_url
    ? `/ai-search${result.thumbnail_url}`
    : null;

  const handleAnnotateClick = (e) => {
    e.stopPropagation();
    if (!showTagMenu && annotateBtnRef.current) {
      const rect = annotateBtnRef.current.getBoundingClientRect();
      setMenuPos({
        top: rect.top - 4,   // position above the button
        left: Math.max(8, rect.right - 320), // 320 = w-80
      });
    }
    setShowTagMenu(prev => !prev);
  };

  const handleTagsChanged = (videoId, newTags) => {
    setLocalTags(newTags);
    onVideoTagsChanged?.(videoId, newTags);
  };

  const handleCategoryChanged = (videoId, newCat) => {
    setLocalCategory(newCat);
    onCategoryChanged?.(videoId, newCat);
  };

  const handleCheckbox = (e) => {
    e.stopPropagation();
    onToggleSelect?.(result);
  };

  const handleInfoClick = (e) => {
    e.stopPropagation();
    setShowDiagnostic(prev => !prev);
  };

  const displayTags = localTags || result.incident_tags || null;
  const displayCategory = localCategory ?? result.category ?? null;

  return (
    <div
      className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden hover:border-blue-500 transition relative"
    >
      <div className="flex cursor-pointer" onClick={() => onClick(result)}>
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
              {/* Source badge */}
              {result.source && (
                <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium ${
                  result.source === 'visual'
                    ? 'bg-purple-900/30 border border-purple-500/30 text-purple-300'
                    : result.source === 'both'
                      ? 'bg-blue-900/30 border border-blue-500/30 text-blue-300'
                      : 'bg-teal-900/30 border border-teal-500/30 text-teal-300'
                }`}>
                  {result.source === 'visual' ? 'Visual' : result.source === 'both' ? 'Both' : 'Caption'}
                </span>
              )}
            </div>
            {scorePercent != null && (
              <div className="flex items-center gap-1.5 shrink-0">
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
                {/* (i) diagnostic button */}
                <button
                  onClick={handleInfoClick}
                  className={`p-0.5 rounded transition ${
                    showDiagnostic
                      ? 'text-blue-400'
                      : 'text-gray-600 hover:text-gray-400'
                  }`}
                  title="Show diagnostic info"
                >
                  <Info size={12} />
                </button>
              </div>
            )}
          </div>

          {/* Timestamp */}
          <div className="flex items-center gap-1 text-xs text-gray-300 mb-1">
            <Clock size={10} className="text-gray-500" />
            {isVisual ? (
              <span>Frame at {formatTimestamp(result.timestamp_ms ?? result.start_ms)}</span>
            ) : (
              <span>{formatTimestamp(result.start_ms)} &ndash; {formatTimestamp(result.end_ms)}</span>
            )}
          </div>

          {/* Transcript text */}
          {result.segment_text && (
            <p className="text-xs text-gray-400 line-clamp-2 leading-relaxed">
              &ldquo;<HighlightText text={result.segment_text} query={searchQuery} />&rdquo;
            </p>
          )}

          {/* Caption text preview (for caption/combined results) */}
          {result.caption_text && !result.segment_text && (
            <p className="text-xs text-teal-400/80 line-clamp-2 leading-relaxed">
              <HighlightText text={result.caption_text} query={searchQuery} />
            </p>
          )}

          {/* Category + Tag pills */}
          {(displayCategory || (displayTags && displayTags.length > 0)) && (
            <div className="flex flex-wrap gap-1 mt-1.5">
              {displayCategory && (
                <span className="px-1.5 py-0.5 bg-amber-900/20 border border-amber-500/30 rounded-full text-[10px] text-amber-300">
                  {displayCategory}
                </span>
              )}
              {displayTags && displayTags.map(tag => (
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

      {/* Diagnostic info popover */}
      {showDiagnostic && (
        <div className="bg-gray-900 border border-gray-600 rounded-lg p-3 mx-2 mb-2 space-y-1.5 text-xs">
          <p className="text-[10px] text-gray-500 uppercase font-bold">Diagnostic Info</p>
          {/* Source — always shown, derived from mode or result.source */}
          <div className="flex justify-between">
            <span className="text-gray-500">Source</span>
            <span className={
              (result.source === 'visual' || mode === 'visual_text' || mode === 'visual_image')
                ? 'text-purple-300'
                : result.source === 'both'
                  ? 'text-blue-300'
                  : (result.source === 'caption' || mode === 'caption_semantic')
                    ? 'text-teal-300'
                    : 'text-green-300'
            }>
              {result.source === 'visual' ? 'Visual (SigLIP)'
                : result.source === 'caption' ? 'Caption (Qwen3-VL)'
                : result.source === 'both' ? 'Both (SigLIP + Qwen3-VL)'
                : mode === 'visual_text' || mode === 'visual_image'
                  ? 'Visual (SigLIP)'
                  : mode === 'caption_semantic'
                    ? 'Caption (Qwen3-VL)'
                    : 'Transcript (Qwen3-Embedding)'
              }
            </span>
          </div>
          {/* Model — show which embedding model was used */}
          <div className="flex justify-between">
            <span className="text-gray-500">Model</span>
            <span className="text-gray-300 font-mono text-[10px]">
              {(result.source === 'both' || mode === 'combined')
                ? 'SigLIP + Qwen3-Embedding'
                : (result.source === 'visual' || mode === 'visual_text' || mode === 'visual_image')
                  ? 'SigLIP SO400M-14'
                  : 'Qwen3-Embedding-8B'
              }
            </span>
          </div>
          {score != null && (
            <div className="flex justify-between">
              <span className="text-gray-500">Score</span>
              <span className="text-gray-300 font-mono">{score.toFixed(4)}</span>
            </div>
          )}
          {result.visual_score != null && (
            <div className="flex justify-between">
              <span className="text-gray-500">Visual score (SigLIP)</span>
              <span className="text-purple-300 font-mono">{result.visual_score.toFixed(4)}</span>
            </div>
          )}
          {result.caption_score != null && (
            <div className="flex justify-between">
              <span className="text-gray-500">Caption score (Qwen3-VL)</span>
              <span className="text-teal-300 font-mono">{result.caption_score.toFixed(4)}</span>
            </div>
          )}
          {result.caption_text && (
            <div>
              <span className="text-gray-500 block mb-0.5">Caption</span>
              <p className="text-gray-300 text-[11px] leading-relaxed">{result.caption_text}</p>
            </div>
          )}
          {searchTiming && (
            <div className="flex justify-between">
              <span className="text-gray-500">Response time</span>
              <span className="text-gray-300 font-mono">{searchTiming.total_ms}ms</span>
            </div>
          )}
        </div>
      )}

      {/* Annotate button — full-width bar at bottom */}
      {canEdit && (
        <button
          ref={annotateBtnRef}
          onClick={handleAnnotateClick}
          className={`w-full flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-semibold border-t transition ${
            showTagMenu
              ? 'bg-blue-600 border-blue-500 text-white'
              : 'bg-gray-700 border-gray-600 text-gray-200 hover:bg-blue-600 hover:border-blue-500 hover:text-white'
          }`}
        >
          <Tag size={12} />
          Annotate
        </button>
      )}

      {/* QuickTagMenu popover — rendered via portal to escape overflow-hidden */}
      {showTagMenu && canEdit && createPortal(
        <div
          className="fixed z-[9999]"
          style={{ top: menuPos.top, left: menuPos.left, transform: 'translateY(-100%)' }}
          onClick={e => e.stopPropagation()}
        >
          <QuickTagMenu
            videoIds={[result.video_id]}
            availableTags={availableTags || []}
            tagCounts={tagCounts}
            onClose={() => setShowTagMenu(false)}
            onTagsChanged={handleTagsChanged}
            onCategoryChanged={handleCategoryChanged}
          />
        </div>,
        document.body
      )}
    </div>
  );
}
