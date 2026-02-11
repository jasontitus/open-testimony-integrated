import React, { useState, useEffect, useRef, useCallback } from 'react';
import { X, Plus } from 'lucide-react';
import api from '../api';

const CATEGORIES = ['interview', 'incident', 'documentation', 'other'];

/**
 * QuickTagMenu — shows category radio-chips and tag toggle-chips.
 *
 * Props:
 *   videoIds          – array of video IDs to tag (single or bulk)
 *   availableTags     – array of all known tag strings
 *   tagCounts         – [{tag, count}] from /tags/counts (optional, for sorting)
 *   onClose           – called when the menu should close
 *   onTagsChanged     – (videoId, newTags) => void, called after each successful tag save
 *   onCategoryChanged – (videoId, newCategory) => void, called after each successful category save
 *   inline            – if true, renders without popover chrome (header, click-outside)
 */
export default function QuickTagMenu({ videoIds, availableTags, tagCounts, onClose, onTagsChanged, onCategoryChanged, inline }) {
  const [filter, setFilter] = useState('');
  const [tagsByVideo, setTagsByVideo] = useState({});    // { videoId: [...tags] }
  const [categoryByVideo, setCategoryByVideo] = useState({}); // { videoId: 'category' }
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState({});               // { videoId: true }
  const [localTags, setLocalTags] = useState([]);          // newly created tags this session
  const [creating, setCreating] = useState(false);
  const menuRef = useRef(null);
  const filterRef = useRef(null);

  const isBulk = videoIds.length > 1;

  // Merge availableTags with any tags created this session
  const allTags = React.useMemo(() => {
    return [...new Set([...availableTags, ...localTags])];
  }, [availableTags, localTags]);

  // Fetch current tags + category for each video on open
  useEffect(() => {
    let cancelled = false;
    async function fetchAll() {
      setLoading(true);
      const tagResult = {};
      const catResult = {};
      await Promise.all(videoIds.map(async (id) => {
        try {
          const res = await api.get(`/videos/${id}`);
          tagResult[id] = res.data.incident_tags || [];
          catResult[id] = res.data.category || '';
        } catch {
          tagResult[id] = [];
          catResult[id] = '';
        }
      }));
      if (!cancelled) {
        setTagsByVideo(tagResult);
        setCategoryByVideo(catResult);
        setLoading(false);
      }
    }
    fetchAll();
    return () => { cancelled = true; };
  }, [videoIds]);

  // Focus filter input on mount (popover only — inline steals focus from other fields)
  useEffect(() => {
    if (!inline) filterRef.current?.focus();
  }, [loading, inline]);

  // Click outside to close (popover only)
  useEffect(() => {
    if (inline) return;
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose, inline]);

  // Escape to close (popover only)
  useEffect(() => {
    if (inline) return;
    const handler = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose, inline]);

  // Sort tags: most-used first (by tagCounts), then alphabetical
  const sortedTags = React.useMemo(() => {
    const countMap = {};
    (tagCounts || []).forEach(tc => { countMap[tc.tag] = tc.count; });
    return [...allTags].sort((a, b) => {
      const ca = countMap[a] || 0;
      const cb = countMap[b] || 0;
      if (cb !== ca) return cb - ca;
      return a.localeCompare(b);
    });
  }, [allTags, tagCounts]);

  const filteredTags = filter.trim()
    ? sortedTags.filter(t => t.toLowerCase().includes(filter.toLowerCase()))
    : sortedTags;

  // Does the current filter text exactly match an existing tag?
  const filterMatchesExisting = allTags.some(t => t.toLowerCase() === filter.trim().toLowerCase());

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
        // Revert on error — re-fetch
        api.get(`/videos/${id}`).then(res => {
          setTagsByVideo(p => ({ ...p, [id]: res.data.incident_tags || [] }));
        }).catch(() => {});
      }
    }));

    const unsaving = {};
    videoIds.forEach(id => { unsaving[id] = false; });
    setSaving(prev => ({ ...prev, ...unsaving }));
  };

  const setCategory = async (cat) => {
    // Toggle off if already selected (for single video)
    const newCat = (!isBulk && categoryByVideo[videoIds[0]] === cat) ? '' : cat;

    // Optimistic update
    const catUpdates = {};
    videoIds.forEach(id => { catUpdates[id] = newCat; });
    setCategoryByVideo(prev => ({ ...prev, ...catUpdates }));

    const savingState = {};
    videoIds.forEach(id => { savingState[id] = true; });
    setSaving(prev => ({ ...prev, ...savingState }));

    await Promise.all(videoIds.map(async (id) => {
      try {
        await api.put(`/videos/${id}/annotations/web`, { category: newCat });
        onCategoryChanged?.(id, newCat);
      } catch {
        api.get(`/videos/${id}`).then(res => {
          setCategoryByVideo(p => ({ ...p, [id]: res.data.category || '' }));
        }).catch(() => {});
      }
    }));

    const unsaving = {};
    videoIds.forEach(id => { unsaving[id] = false; });
    setSaving(prev => ({ ...prev, ...unsaving }));
  };

  const handleCreateTag = async () => {
    const tag = filter.trim().toLowerCase();
    if (!tag || filterMatchesExisting) return;

    setCreating(true);
    try {
      await api.post('/tags', { tag });
      setLocalTags(prev => [...prev, tag]);
      setFilter('');
      // Auto-toggle the new tag on for all selected videos
      await toggleTag(tag);
    } catch {
      // ignore — tag might already exist
    } finally {
      setCreating(false);
    }
  };

  const handleFilterKeyDown = (e) => {
    if (e.key === 'Enter' && filter.trim() && !filterMatchesExisting) {
      e.preventDefault();
      handleCreateTag();
    }
  };

  const anySaving = Object.values(saving).some(Boolean);

  // Category state for display
  const currentCategory = !isBulk ? (categoryByVideo[videoIds[0]] || '') : '';

  return (
    <div
      ref={menuRef}
      className={inline
        ? 'overflow-hidden'
        : 'w-80 bg-gray-800 border border-gray-600 rounded-lg shadow-2xl overflow-hidden'}
      onClick={e => e.stopPropagation()}
    >
      {/* Header (popover only) */}
      {!inline && (
        <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700">
          <span className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
            {isBulk ? `Annotate ${videoIds.length} videos` : 'Quick Annotate'}
          </span>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition">
            <X size={14} />
          </button>
        </div>
      )}

      {/* Category chips */}
      {!loading && (
        <div className={inline ? 'mb-3' : 'px-3 py-2 border-b border-gray-700'}>
          {!inline && <p className="text-[10px] text-gray-500 uppercase font-bold mb-1.5">Category</p>}
          <div className="flex flex-wrap gap-1.5">
            {CATEGORIES.map(cat => {
              const active = !isBulk && currentCategory === cat;
              return (
                <button
                  key={cat}
                  onClick={() => setCategory(cat)}
                  disabled={anySaving}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium transition border ${
                    active
                      ? 'bg-amber-600 border-amber-500 text-white'
                      : 'bg-gray-900 border-gray-600 text-gray-400 hover:border-gray-500 hover:text-gray-300'
                  } ${anySaving ? 'opacity-50 cursor-wait' : 'cursor-pointer'}`}
                >
                  {cat}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Filter / create */}
      <div className={inline ? 'mb-2' : 'px-3 py-2 border-b border-gray-700'}>
        {!inline && <p className="text-[10px] text-gray-500 uppercase font-bold mb-1.5">Tags</p>}
        <div className="flex gap-1">
          <input
            ref={filterRef}
            type="text"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            onKeyDown={handleFilterKeyDown}
            placeholder="Filter or create tag..."
            className="flex-1 px-2 py-1 bg-gray-900 border border-gray-700 rounded text-xs text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
          />
          {filter.trim() && !filterMatchesExisting && (
            <button
              onClick={handleCreateTag}
              disabled={creating || anySaving}
              className="px-2 py-1 bg-green-700 hover:bg-green-600 disabled:bg-green-900 text-white text-xs rounded transition flex items-center gap-1 shrink-0"
              title="Create new tag"
            >
              <Plus size={12} />
              Add
            </button>
          )}
        </div>
      </div>

      {/* Tag list */}
      <div className={inline ? '' : 'max-h-56 overflow-y-auto p-2'}>
        {loading ? (
          <div className="flex justify-center py-4">
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-500"></div>
          </div>
        ) : filteredTags.length === 0 && !filter.trim() ? (
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
            {filter.trim() && !filterMatchesExisting && filteredTags.length === 0 && (
              <p className="text-xs text-gray-500 py-1">Press Enter or click Add to create "{filter.trim().toLowerCase()}"</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
