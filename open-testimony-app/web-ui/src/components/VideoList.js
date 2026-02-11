import React, { useState } from 'react';
import { format } from 'date-fns';
import { Clock, Tag, CheckSquare, Square } from 'lucide-react';
import { useAuth } from '../auth';
import VerificationBadge from './VerificationBadge';
import SourceBadge from './SourceBadge';
import MediaTypeBadge from './MediaTypeBadge';
import QuickTagMenu from './QuickTagMenu';

export default function VideoList({
  videos, selectedVideo, onVideoClick, loading, onRefresh,
  onTagClick, onCategoryClick,
  availableTags, tagCounts, onVideoTagsChanged,
}) {
  const { user } = useAuth();
  const canEdit = user?.role === 'admin' || user?.role === 'staff';

  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);
  const [showBulkTagMenu, setShowBulkTagMenu] = useState(false);
  const [quickTagVideoId, setQuickTagVideoId] = useState(null);

  const toggleSelect = (videoId) => {
    setSelectedIds(prev =>
      prev.includes(videoId)
        ? prev.filter(id => id !== videoId)
        : [...prev, videoId]
    );
  };

  const exitSelectMode = () => {
    setSelectMode(false);
    setSelectedIds([]);
    setShowBulkTagMenu(false);
  };

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-gray-700 flex justify-between items-center">
        <h2 className="font-semibold text-gray-300 uppercase text-xs tracking-wider">
          Uploaded Media ({videos.length})
        </h2>
        <div className="flex items-center gap-2">
          {canEdit && videos.length > 0 && (
            <button
              onClick={() => selectMode ? exitSelectMode() : setSelectMode(true)}
              className={`flex items-center gap-1 text-xs font-medium transition ${
                selectMode
                  ? 'text-blue-400 hover:text-blue-300'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              <CheckSquare size={12} />
              {selectMode ? 'Cancel' : 'Select'}
            </button>
          )}
          <button onClick={onRefresh} className="text-blue-400 hover:text-blue-300 text-xs font-medium">
            Refresh
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex justify-center items-center h-32">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          </div>
        ) : videos.length === 0 ? (
          <div className="p-8 text-center text-gray-500 italic">No media found.</div>
        ) : (
          videos.map(video => (
            <div
              key={video.id}
              onClick={() => selectMode ? toggleSelect(video.id) : onVideoClick(video)}
              className={`p-4 border-b border-gray-700 cursor-pointer transition hover:bg-gray-750 relative ${
                selectedVideo?.id === video.id ? 'bg-gray-700 border-l-4 border-l-blue-500' : 'bg-transparent'
              }`}
            >
              <div className="flex justify-between items-start mb-1">
                <div className="flex items-center gap-2 min-w-0">
                  {selectMode && (
                    <span className="shrink-0">
                      {selectedIds.includes(video.id) ? (
                        <CheckSquare size={14} className="text-blue-400" />
                      ) : (
                        <Square size={14} className="text-gray-600" />
                      )}
                    </span>
                  )}
                  <MediaTypeBadge mediaType={video.media_type} />
                  <span className="text-xs font-mono text-blue-400 truncate">{video.device_id}</span>
                </div>
                <div className="flex items-center gap-1.5 shrink-0 ml-2">
                  {canEdit && !selectMode && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setQuickTagVideoId(prev => prev === video.id ? null : video.id);
                      }}
                      className="p-1.5 rounded hover:bg-gray-700 transition text-gray-400 hover:text-blue-400"
                      title="Quick Tag"
                    >
                      <Tag size={18} />
                    </button>
                  )}
                  <SourceBadge source={video.source} />
                  <VerificationBadge status={video.verification_status} />
                </div>
              </div>
              <div className="flex items-center text-sm text-gray-300 mb-2 mt-1">
                <Clock size={14} className="mr-1.5 text-gray-500" />
                {format(new Date(video.timestamp), 'MMM d, yyyy HH:mm:ss')}
              </div>
              <div className="flex flex-wrap gap-1">
                {video.category && (
                  <button
                    onClick={(e) => { e.stopPropagation(); onCategoryClick?.(video.category); }}
                    className="px-2 py-0.5 bg-indigo-900/30 border border-indigo-500/40 rounded-full text-[10px] text-indigo-300 uppercase tracking-tighter cursor-pointer hover:border-indigo-400 hover:bg-indigo-900/50 transition"
                  >
                    {video.category}
                  </button>
                )}
                {video.incident_tags?.map(tag => (
                  <button
                    key={tag}
                    onClick={(e) => { e.stopPropagation(); onTagClick?.(tag); }}
                    className="px-2 py-0.5 bg-gray-900 border border-gray-600 rounded-full text-[10px] text-gray-400 uppercase tracking-tighter cursor-pointer hover:border-blue-500 hover:text-blue-300 transition"
                  >
                    {tag}
                  </button>
                ))}
              </div>

              {/* QuickTagMenu for this video */}
              {quickTagVideoId === video.id && canEdit && (
                <div className="absolute top-0 right-0 z-50" onClick={e => e.stopPropagation()}>
                  <QuickTagMenu
                    videoIds={[video.id]}
                    availableTags={availableTags || []}
                    tagCounts={tagCounts}
                    onClose={() => setQuickTagVideoId(null)}
                    onTagsChanged={onVideoTagsChanged}
                  />
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* Bulk selection sticky bar */}
      {selectMode && selectedIds.length > 0 && (
        <div className="shrink-0 bg-gray-800 border-t border-gray-600 p-3 flex items-center justify-between">
          <span className="text-sm text-gray-300">
            {selectedIds.length} video{selectedIds.length !== 1 ? 's' : ''} selected
          </span>
          <div className="flex items-center gap-2 relative">
            <button
              onClick={() => setShowBulkTagMenu(prev => !prev)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium rounded-lg transition"
            >
              <Tag size={12} />
              Tag Selected
            </button>
            <button
              onClick={() => setSelectedIds([])}
              className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs font-medium rounded-lg transition"
            >
              Clear
            </button>
            {showBulkTagMenu && (
              <div className="absolute bottom-full right-0 mb-2">
                <QuickTagMenu
                  videoIds={selectedIds}
                  availableTags={availableTags || []}
                  tagCounts={tagCounts}
                  onClose={() => setShowBulkTagMenu(false)}
                  onTagsChanged={onVideoTagsChanged}
                />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
