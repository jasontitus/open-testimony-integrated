import React, { useState, useEffect, useRef, useCallback } from 'react';
import { X } from 'lucide-react';
import api from '../api';

/**
 * QuickTagMenu — popover showing all available tags as clickable chip toggles.
 *
 * Props:
 *   videoIds        – array of video IDs to tag (single or bulk)
 *   availableTags   – array of all known tag strings
 *   tagCounts       – [{tag, count}] from /tags/counts (optional, for sorting)
 *   anchorEl        – DOM element to position near (unused for now; we position via CSS)
 *   onClose         – called when the menu should close
 *   onTagsChanged   – (videoId, newTags) => void, called after each successful save
 */
export default function QuickTagMenu({ videoIds, availableTags, tagCounts, onClose, onTagsChanged }) {
  const [filter, setFilter] = useState('');
  const [tagsByVideo, setTagsByVideo] = useState({});  // { videoId: [...tags] }
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState({});             // { videoId: true }
  const menuRef = useRef(null);
  const filterRef = useRef(null);

  // Fetch current tags for each video on open
  useEffect(() => {
    let cancelled = false;
    async function fetchAll() {
      setLoading(true);
      const result = {};
      await Promise.all(videoIds.map(async (id) => {
        try {
          const res = await api.get(`/videos/${id}`);
          result[id] = res.data.incident_tags || [];
        } catch {
          result[id] = [];
        }
      }));
      if (!cancelled) {
        setTagsByVideo(result);
        setLoading(false);
      }
    }
    fetchAll();
    return () => { cancelled = true; };
  }, [videoIds]);

  // Focus filter input on mount
  useEffect(() => {
    filterRef.current?.focus();
  }, [loading]);

  // Click outside to close
  useEffect(() => {
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  // Escape to close
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  // Sort tags: most-used first (by tagCounts), then alphabetical
  const sortedTags = React.useMemo(() => {
    const countMap = {};
    (tagCounts || []).forEach(tc => { countMap[tc.tag] = tc.count; });
    return [...availableTags].sort((a, b) => {
      const ca = countMap[a] || 0;
      const cb = countMap[b] || 0;
      if (cb !== ca) return cb - ca;
      return a.localeCompare(b);
    });
  }, [availableTags, tagCounts]);

  const filteredTags = filter.trim()
    ? sortedTags.filter(t => t.toLowerCase().includes(filter.toLowerCase()))
    : sortedTags;

  // Is a tag active on ALL selected videos?
  const isTagActive = useCallback((tag) => {
    return videoIds.every(id => (tagsByVideo[id] || []).includes(tag));
  }, [videoIds, tagsByVideo]);

  // Is a tag active on SOME (but not all) selected videos?
  const isTagPartial = useCallback((tag) => {
    const ids = videoIds;
    const has = ids.filter(id => (tagsByVideo[id] || []).includes(tag));
    return has.length > 0 && has.length < ids.length;
  }, [videoIds, tagsByVideo]);

  const toggleTag = async (tag) => {
    const active = isTagActive(tag);

    // Compute new tags per video
    const updates = {};
    videoIds.forEach(id => {
      const current = tagsByVideo[id] || [];
      if (active) {
        updates[id] = current.filter(t => t !== tag);
      } else {
        updates[id] = current.includes(tag) ? current : [...current, tag];
      }
    });

    // Optimistic update
    setTagsByVideo(prev => ({ ...prev, ...updates }));

    // Save each video
    const savingState = {};
    videoIds.forEach(id => { savingState[id] = true; });
    setSaving(prev => ({ ...prev, ...savingState }));

    await Promise.all(videoIds.map(async (id) => {
      try {
        await api.put(`/videos/${id}/annotations/web`, {
          incident_tags: updates[id],
        });
        onTagsChanged?.(id, updates[id]);
      } catch {
        // Revert on error
        setTagsByVideo(prev => {
          const reverted = { ...prev };
          // Re-fetch
          api.get(`/videos/${id}`).then(res => {
            setTagsByVideo(p => ({ ...p, [id]: res.data.incident_tags || [] }));
          }).catch(() => {});
          return reverted;
        });
      }
    }));

    const unsaving = {};
    videoIds.forEach(id => { unsaving[id] = false; });
    setSaving(prev => ({ ...prev, ...unsaving }));
  };

  const isBulk = videoIds.length > 1;
  const anySaving = Object.values(saving).some(Boolean);

  return (
    <div
      ref={menuRef}
      className="w-72 bg-gray-800 border border-gray-600 rounded-lg shadow-2xl overflow-hidden"
      onClick={e => e.stopPropagation()}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700">
        <span className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
          {isBulk ? `Tag ${videoIds.length} videos` : 'Quick Tag'}
        </span>
        <button onClick={onClose} className="text-gray-500 hover:text-white transition">
          <X size={14} />
        </button>
      </div>

      {/* Filter */}
      <div className="px-3 py-2 border-b border-gray-700">
        <input
          ref={filterRef}
          type="text"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="Filter tags..."
          className="w-full px-2 py-1 bg-gray-900 border border-gray-700 rounded text-xs text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
        />
      </div>

      {/* Tag list */}
      <div className="max-h-56 overflow-y-auto p-2">
        {loading ? (
          <div className="flex justify-center py-4">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-500"></div>
          </div>
        ) : filteredTags.length === 0 ? (
          <p className="text-xs text-gray-500 text-center py-3">No tags found</p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {filteredTags.map(tag => {
              const active = isTagActive(tag);
              const partial = isTagPartial(tag);
              return (
                <button
                  key={tag}
                  onClick={() => toggleTag(tag)}
                  disabled={anySaving}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium transition border ${
                    active
                      ? 'bg-blue-600 border-blue-500 text-white'
                      : partial
                        ? 'bg-blue-900/40 border-blue-500/50 text-blue-300'
                        : 'bg-gray-900 border-gray-600 text-gray-400 hover:border-gray-500 hover:text-gray-300'
                  } ${anySaving ? 'opacity-50 cursor-wait' : 'cursor-pointer'}`}
                >
                  {tag}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
