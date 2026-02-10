import React from 'react';
import { format } from 'date-fns';
import { Clock } from 'lucide-react';
import VerificationBadge from './VerificationBadge';
import SourceBadge from './SourceBadge';
import MediaTypeBadge from './MediaTypeBadge';

export default function VideoList({ videos, selectedVideo, onVideoClick, loading, onRefresh, onTagClick, onCategoryClick }) {
  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-gray-700 flex justify-between items-center">
        <h2 className="font-semibold text-gray-300 uppercase text-xs tracking-wider">
          Uploaded Media ({videos.length})
        </h2>
        <button onClick={onRefresh} className="text-blue-400 hover:text-blue-300 text-xs font-medium">
          Refresh
        </button>
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
              onClick={() => onVideoClick(video)}
              className={`p-4 border-b border-gray-700 cursor-pointer transition hover:bg-gray-750 ${
                selectedVideo?.id === video.id ? 'bg-gray-700 border-l-4 border-l-blue-500' : 'bg-transparent'
              }`}
            >
              <div className="flex justify-between items-start mb-1">
                <div className="flex items-center gap-2 min-w-0">
                  <MediaTypeBadge mediaType={video.media_type} />
                  <span className="text-xs font-mono text-blue-400 truncate">{video.device_id}</span>
                </div>
                <div className="flex items-center gap-1.5 shrink-0 ml-2">
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
            </div>
          ))
        )}
      </div>
    </div>
  );
}
