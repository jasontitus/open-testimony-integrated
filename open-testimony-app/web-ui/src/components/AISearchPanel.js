import React, { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { Search, Upload, Film, MessageSquare, Loader, X, CheckSquare, Tag, ChevronDown, ChevronRight, Square, Save, MapPin, FileText, Eye } from 'lucide-react';
import axios from 'axios';
import api from '../api';
import { useAuth } from '../auth';
import AISearchResultCard from './AISearchResultCard';
import QuickTagMenu from './QuickTagMenu';
import AddressAutocomplete from './AddressAutocomplete';

const SEARCH_MODES = [
  { id: 'combined', label: 'Visual', icon: Eye, description: 'Visual + scene descriptions' },
  { id: 'visual_text', label: 'Embedding', icon: Film, description: 'Describe what you see' },
  { id: 'visual_image', label: 'Search by Image', icon: Upload, description: 'Upload a reference image' },
  { id: 'caption_exact', label: 'Caption (Exact)', icon: Search, description: 'Search exact caption phrases' },
  { id: 'transcript_semantic', label: 'Transcript (Semantic)', icon: MessageSquare, description: 'Search by meaning' },
  { id: 'transcript_exact', label: 'Transcript (Exact)', icon: Search, description: 'Search exact words' },
];

const aiApi = axios.create({
  baseURL: '/ai-search',
  withCredentials: true,
});

function SearchForm({ mode, loading, onSearch, onImageChange, imageFile, initialQuery }) {
  const [inputValue, setInputValue] = useState(initialQuery || '');
  const searchInputRef = useRef(null);

  useEffect(() => {
    if (searchInputRef.current) searchInputRef.current.focus();
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    onSearch(inputValue);
  };

  const placeholder =
    mode === 'visual_text' ? 'Describe what you\'re looking for...' :
    mode === 'combined' ? 'Search visual + scene descriptions...' :
    mode === 'transcript_semantic' ? 'Search by meaning...' :
    mode === 'caption_exact' ? 'Search exact caption phrases...' :
    'Search exact words...';

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      {mode === 'visual_image' ? (
        <label className="flex-1 flex items-center gap-2 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg cursor-pointer hover:border-gray-600">
          <Upload size={16} className="text-gray-500 shrink-0" />
          <span className="text-sm text-gray-400 truncate">
            {imageFile ? imageFile.name : 'Choose an image...'}
          </span>
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={e => onImageChange(e.target.files[0] || null)}
          />
        </label>
      ) : (
        <input
          ref={searchInputRef}
          type="text"
          value={inputValue}
          onChange={e => setInputValue(e.target.value)}
          placeholder={placeholder}
          className="flex-1 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500"
        />
      )}
      <button
        type="submit"
        disabled={loading}
        className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-white text-sm font-medium rounded-lg transition shrink-0"
      >
        {loading ? <Loader size={16} className="animate-spin" /> : <Search size={16} />}
        Search
      </button>
    </form>
  );
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

// --- Inline component: collapsible group of results for one video ---
function VideoResultGroup({
  group, mode, onResultClick, onVideoClick, availableTags, tagCounts, onVideoTagsChanged,
  canEdit, selectMode, selectedResults, onToggleSelect, isResultSelected, searchTiming, searchQuery,
}) {
  const [expanded, setExpanded] = useState(false);
  const best = group.results.reduce((max, r) => (r.score > max.score) ? r : max, group.results[0]);
  const count = group.results.length;
  const scorePercent = group.bestScore != null ? Math.round(group.bestScore * 100) : null;
  const isVisual = mode === 'visual_text' || mode === 'visual_image' || mode === 'combined' || mode === 'caption_semantic' || mode === 'caption_exact';

  const thumbnailUrl = best.thumbnail_url ? `/ai-search${best.thumbnail_url}` : null;
  const [imgError, setImgError] = useState(false);

  const displayTags = best.incident_tags || [];
  const displayCategory = best.category || null;

  // Source badge for combined mode
  const bestSource = best.source;

  // Check if all results in this group are selected
  const allSelected = group.results.every(r => isResultSelected(r));
  const someSelected = !allSelected && group.results.some(r => isResultSelected(r));

  const handleGroupCheckbox = (e) => {
    e.stopPropagation();
    if (allSelected) {
      group.results.forEach(r => {
        if (isResultSelected(r)) onToggleSelect(r);
      });
    } else {
      group.results.forEach(r => {
        if (!isResultSelected(r)) onToggleSelect(r);
      });
    }
  };

  // Open the video-level player + annotation panel (no specific timestamp)
  const handleHeaderClick = () => {
    onVideoClick(group.video_id, best);
  };

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
      {/* Group header row — clicking opens player + annotations for the whole video */}
      <div className="flex items-center cursor-pointer hover:bg-gray-750" onClick={handleHeaderClick}>
        {/* Checkbox for bulk select */}
        {selectMode && (
          <button
            onClick={handleGroupCheckbox}
            className="flex items-center justify-center w-8 shrink-0 bg-gray-900/50 hover:bg-gray-700 transition"
          >
            {allSelected ? (
              <CheckSquare size={16} className="text-blue-400" />
            ) : someSelected ? (
              <CheckSquare size={16} className="text-blue-400/50" />
            ) : (
              <Square size={16} className="text-gray-600" />
            )}
          </button>
        )}

        {/* Thumbnail */}
        <div className="w-28 h-20 bg-gray-900 shrink-0 relative">
          {thumbnailUrl && !imgError ? (
            <img src={thumbnailUrl} alt="" className="w-full h-full object-cover" onError={() => setImgError(true)} />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Film size={20} className="text-gray-700" />
            </div>
          )}
          <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 hover:opacity-100 transition-opacity">
            <Film size={20} className="text-white" />
          </div>
        </div>

        {/* Info */}
        <div className="flex-1 px-3 py-2 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            {isVisual ? (
              <Film size={12} className="text-purple-400 shrink-0" />
            ) : (
              <MessageSquare size={12} className="text-green-400 shrink-0" />
            )}
            <span className="text-xs font-mono text-gray-400 truncate">
              {group.video_id.slice(0, 8)}...
            </span>
            <span className="px-1.5 py-0.5 bg-blue-900/30 border border-blue-500/30 rounded-full text-[10px] text-blue-300 font-medium shrink-0">
              {count} match{count !== 1 ? 'es' : ''}
            </span>
            {bestSource && (
              <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium shrink-0 ${
                bestSource === 'visual'
                  ? 'bg-purple-900/30 border border-purple-500/30 text-purple-300'
                  : bestSource === 'both'
                    ? 'bg-blue-900/30 border border-blue-500/30 text-blue-300'
                    : 'bg-teal-900/30 border border-teal-500/30 text-teal-300'
              }`}>
                {bestSource === 'visual' ? 'Visual' : bestSource === 'both' ? 'Both' : 'Caption'}
              </span>
            )}
          </div>

          {/* Score bar */}
          {scorePercent != null && (
            <div className="flex items-center gap-2 mb-1">
              <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
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

          {/* Category + Tags */}
          {(displayCategory || displayTags.length > 0) && (
            <div className="flex flex-wrap gap-1">
              {displayCategory && (
                <span className="px-1.5 py-0.5 bg-amber-900/20 border border-amber-500/30 rounded-full text-[10px] text-amber-300">
                  {displayCategory}
                </span>
              )}
              {displayTags.slice(0, 3).map(tag => (
                <span key={tag} className="px-1.5 py-0.5 bg-blue-900/20 border border-blue-500/30 rounded-full text-[10px] text-blue-300">
                  {tag}
                </span>
              ))}
              {displayTags.length > 3 && (
                <span className="text-[10px] text-gray-500">+{displayTags.length - 3}</span>
              )}
            </div>
          )}
        </div>

        {/* Expand chevron — separate click target */}
        <button
          onClick={(e) => { e.stopPropagation(); setExpanded(prev => !prev); }}
          className="px-3 py-2 shrink-0 text-gray-500 hover:text-white transition"
          title={expanded ? 'Collapse matches' : 'Expand matches'}
        >
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </button>
      </div>

      {/* Expanded: individual result cards (for jumping to specific timestamps) */}
      {expanded && (
        <div className="border-t border-gray-700 bg-gray-850 space-y-1 p-2">
          <p className="text-[10px] text-gray-500 uppercase font-bold px-1 mb-1">Individual matches (click to jump to timestamp)</p>
          {group.results.map((result, i) => (
            <AISearchResultCard
              key={`${result.video_id}-${result.timestamp_ms || result.start_ms}-${i}`}
              result={result}
              mode={mode}
              onClick={onResultClick}
              availableTags={availableTags}
              tagCounts={tagCounts}
              onVideoTagsChanged={onVideoTagsChanged}
              selectable={selectMode}
              selected={isResultSelected(result)}
              onToggleSelect={onToggleSelect}
              searchTiming={searchTiming}
              searchQuery={searchQuery}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function AISearchPanel({ onResultClick, availableTags, tagCounts, onVideoTagsChanged }) {
  const { user, logout } = useAuth();
  const [mode, setMode] = useState('combined');
  const [imageFile, setImageFile] = useState(null);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [stats, setStats] = useState(null);
  const [searchTiming, setSearchTiming] = useState(null);
  const [searchMode, setSearchMode] = useState('combined');
  const [searchQuery, setSearchQuery] = useState('');

  // Inline video player state
  const [activeResult, setActiveResult] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [videoLoading, setVideoLoading] = useState(false);
  const videoRef = useRef(null);

  // Annotation panel state
  const canEdit = user?.role === 'admin' || user?.role === 'staff';
  const [videoDetail, setVideoDetail] = useState(null);
  const [annotationNotes, setAnnotationNotes] = useState('');
  const [annotationLocation, setAnnotationLocation] = useState('');
  const [geocodedLocation, setGeocodedLocation] = useState(null);
  const [annotationSaving, setAnnotationSaving] = useState(false);
  const [annotationSaveError, setAnnotationSaveError] = useState('');
  const [annotationSaved, setAnnotationSaved] = useState(false);

  // Bulk selection state
  const [selectMode, setSelectMode] = useState(false);
  const [selectedResults, setSelectedResults] = useState([]); // array of result objects
  const [showBulkTagMenu, setShowBulkTagMenu] = useState(false);

  const fetchStats = useCallback(async () => {
    try {
      const res = await aiApi.get('/indexing/status');
      setStats(res.data);
    } catch {
      // Bridge may not be running
    }
  }, []);

  React.useEffect(() => { fetchStats(); }, [fetchStats]);

  // Group results by video_id
  const groupedResults = useMemo(() => {
    const groups = [];
    const seen = new Map();
    for (const r of results) {
      if (!seen.has(r.video_id)) {
        const group = { video_id: r.video_id, results: [r], bestScore: r.score ?? null };
        seen.set(r.video_id, group);
        groups.push(group);
      } else {
        const group = seen.get(r.video_id);
        group.results.push(r);
        if (r.score != null && (group.bestScore == null || r.score > group.bestScore)) group.bestScore = r.score;
      }
    }
    return groups;
  }, [results]);

  const handleSearch = async (query, overrideMode) => {
    const effectiveMode = overrideMode || mode;
    if (effectiveMode !== 'visual_image' && !query.trim()) return;
    if (effectiveMode === 'visual_image' && !imageFile) return;

    setLoading(true);
    setError('');
    setResults([]);
    setActiveResult(null);
    setVideoUrl(null);
    setVideoDetail(null);
    setSelectedResults([]);
    setSearchQuery(query);

    try {
      let res;
      if (effectiveMode === 'visual_text') {
        res = await aiApi.get('/search/visual', { params: { q: query, limit: 20 } });
      } else if (effectiveMode === 'visual_image') {
        const formData = new FormData();
        formData.append('image', imageFile);
        res = await aiApi.post('/search/visual', formData, { params: { limit: 20 } });
      } else if (effectiveMode === 'combined') {
        res = await aiApi.get('/search/combined', { params: { q: query, limit: 20 } });
      } else if (effectiveMode === 'transcript_semantic') {
        res = await aiApi.get('/search/transcript', { params: { q: query, limit: 20 } });
      } else if (effectiveMode === 'transcript_exact') {
        res = await aiApi.get('/search/transcript/exact', { params: { q: query, limit: 20 } });
      } else if (effectiveMode === 'caption_exact') {
        res = await aiApi.get('/search/captions/exact', { params: { q: query, limit: 20 } });
      }
      const rawResults = res.data.results || [];
      setResults(rawResults);
      setSearchTiming(res.data.timing || null);
      setSearchMode(effectiveMode);

      // Enrich results with existing tags + category from the API
      const uniqueIds = [...new Set(rawResults.map(r => r.video_id))];
      const detailMap = {};
      await Promise.all(uniqueIds.map(async (id) => {
        try {
          const vRes = await api.get(`/videos/${id}`);
          detailMap[id] = { incident_tags: vRes.data.incident_tags || [], category: vRes.data.category || null };
        } catch {
          detailMap[id] = { incident_tags: [], category: null };
        }
      }));
      setResults(prev => prev.map(r => ({
        ...r,
        incident_tags: detailMap[r.video_id]?.incident_tags || [],
        category: detailMap[r.video_id]?.category || null,
      })));
    } catch (err) {
      if (err.response?.status === 401) {
        logout();
        return;
      }
      const detail = err.response?.data?.detail;
      if (err.response?.status === 502 || err.response?.status === 504 || !err.response) {
        setError('Cannot reach the AI search service. Is the bridge running?');
      } else {
        setError(detail || `Search failed (${err.response?.status || 'network error'}).`);
      }
    } finally {
      setLoading(false);
    }
  };

  // Open a video (from group header click) — seeks to best match
  const handleVideoClick = async (videoId, bestResult) => {
    if (selectMode) return;
    setActiveResult(bestResult);
    setVideoUrl(null);
    setVideoLoading(true);
    setVideoDetail(null);
    setAnnotationNotes('');
    setAnnotationLocation('');
    setAnnotationSaveError('');
    setAnnotationSaved(false);

    try {
      const [urlRes, detailRes] = await Promise.all([
        api.get(`/videos/${videoId}/url`),
        api.get(`/videos/${videoId}`),
      ]);
      setVideoUrl(urlRes.data.url);
      setVideoDetail(detailRes.data);
      setAnnotationNotes(detailRes.data.notes || '');
      setAnnotationLocation(detailRes.data.location_description || '');
    } catch {
      setVideoUrl(null);
    } finally {
      setVideoLoading(false);
    }
  };

  // When a specific result is clicked (from expanded list), seek to its timestamp
  const handleResultClick = async (result) => {
    if (selectMode) return;
    setActiveResult(result);
    setVideoUrl(null);
    setVideoLoading(true);
    setVideoDetail(null);
    setAnnotationNotes('');
    setAnnotationLocation('');
    setAnnotationSaveError('');
    setAnnotationSaved(false);

    try {
      const [urlRes, detailRes] = await Promise.all([
        api.get(`/videos/${result.video_id}/url`),
        api.get(`/videos/${result.video_id}`),
      ]);
      setVideoUrl(urlRes.data.url);
      setVideoDetail(detailRes.data);
      setAnnotationNotes(detailRes.data.notes || '');
      setAnnotationLocation(detailRes.data.location_description || '');
    } catch {
      setVideoUrl(null);
    } finally {
      setVideoLoading(false);
    }
  };

  // Save annotations (notes + location_description)
  const handleAnnotationSave = async () => {
    if (!activeResult || !videoDetail) return;
    setAnnotationSaving(true);
    setAnnotationSaveError('');
    setAnnotationSaved(false);
    try {
      const payload = {
        notes: annotationNotes || null,
        location_description: annotationLocation || null,
      };
      if (geocodedLocation) {
        payload.latitude = geocodedLocation.lat;
        payload.longitude = geocodedLocation.lon;
      }
      await api.put(`/videos/${activeResult.video_id}/annotations/web`, payload);
      setGeocodedLocation(null);
      setAnnotationSaved(true);
      setTimeout(() => setAnnotationSaved(false), 2000);
      onVideoTagsChanged?.(activeResult.video_id);
    } catch (err) {
      setAnnotationSaveError(err.response?.data?.detail || 'Failed to save');
    } finally {
      setAnnotationSaving(false);
    }
  };

  // Seek to timestamp when video loads (skip for video-level clicks)
  useEffect(() => {
    if (!activeResult || !videoRef.current || !videoUrl) return;
    if (activeResult._noSeek) return; // Video-level click — play from start
    const seekMs = activeResult.timestamp_ms || activeResult.start_ms || 0;
    const seekSec = seekMs / 1000;
    const el = videoRef.current;
    const trySeek = () => {
      el.currentTime = seekSec;
      el.removeEventListener('loadedmetadata', trySeek);
    };
    if (el.readyState >= 1) {
      el.currentTime = seekSec;
    } else {
      el.addEventListener('loadedmetadata', trySeek);
    }
  }, [activeResult, videoUrl]);

  // Bulk selection helpers
  const toggleSelectResult = (result) => {
    setSelectedResults(prev => {
      const exists = prev.find(r => r.video_id === result.video_id && (r.timestamp_ms || r.start_ms) === (result.timestamp_ms || result.start_ms));
      if (exists) return prev.filter(r => !(r.video_id === result.video_id && (r.timestamp_ms || r.start_ms) === (result.timestamp_ms || result.start_ms)));
      return [...prev, result];
    });
  };

  const isResultSelected = (result) => {
    return selectedResults.some(r => r.video_id === result.video_id && (r.timestamp_ms || r.start_ms) === (result.timestamp_ms || result.start_ms));
  };

  // Deduplicated video IDs for bulk tagging
  const selectedVideoIds = [...new Set(selectedResults.map(r => r.video_id))];

  const exitSelectMode = () => {
    setSelectMode(false);
    setSelectedResults([]);
    setShowBulkTagMenu(false);
  };

  return (
    <div className="h-full flex flex-col bg-gray-900 w-full">
      {/* Search mode selector + form */}
      <div className="p-4 border-b border-gray-700 shrink-0">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mb-4">
          {SEARCH_MODES.map(m => {
            const Icon = m.icon;
            return (
              <button
                key={m.id}
                onClick={() => { setMode(m.id); setError(''); setActiveResult(null); if (searchQuery && m.id !== 'visual_image') { handleSearch(searchQuery, m.id); } else { setResults([]); setSelectedResults([]); } }}
                className={`flex flex-col items-center gap-1 px-3 py-2 rounded-lg border text-xs transition ${
                  mode === m.id
                    ? 'bg-blue-600 border-blue-500 text-white'
                    : 'bg-gray-800 border-gray-700 text-gray-400 hover:text-white hover:border-gray-600'
                }`}
              >
                <Icon size={16} />
                <span className="font-medium">{m.label}</span>
              </button>
            );
          })}
        </div>

        <SearchForm
          mode={mode}
          loading={loading}
          onSearch={handleSearch}
          onImageChange={setImageFile}
          imageFile={imageFile}
          initialQuery={searchQuery}
        />

        {stats && (
          <div className="flex gap-3 mt-3 text-[10px] uppercase tracking-wider text-gray-500">
            <span>{stats.completed || 0} indexed</span>
            <span>{stats.processing || 0} processing</span>
            <span>{stats.pending || 0} pending</span>
          </div>
        )}
      </div>

      {/* Main content: player + results */}
      <div className="flex-1 overflow-hidden flex flex-col md:flex-row">
        {/* Inline video player + annotation panel (shown when a result is clicked) */}
        {activeResult && !selectMode && (
          <div className="max-h-[70vh] md:max-h-none md:w-1/2 lg:w-3/5 shrink-0 flex flex-col border-b md:border-b-0 md:border-r border-gray-700 overflow-y-auto">
            <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
              <span className="text-xs text-gray-400 font-mono">
                {activeResult.video_id.slice(0, 8)}...
                {activeResult._noSeek ? '' : ` @ ${formatTimestamp(activeResult.timestamp_ms || activeResult.start_ms || 0)}`}
              </span>
              <button
                onClick={() => { setActiveResult(null); setVideoUrl(null); setVideoDetail(null); }}
                className="text-gray-500 hover:text-white transition"
              >
                <X size={16} />
              </button>
            </div>
            <div className="bg-black flex items-center justify-center min-h-[200px]">
              {videoLoading ? (
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500"></div>
              ) : videoUrl ? (
                <video
                  ref={videoRef}
                  src={videoUrl}
                  controls
                  autoPlay
                  playsInline
                  className="w-full h-full max-h-[50vh] object-contain"
                />
              ) : (
                <p className="text-gray-500 text-sm">Video not available</p>
              )}
            </div>
            {activeResult.segment_text && (
              <div className="px-4 py-2 bg-gray-800 border-t border-gray-700">
                <p className="text-sm text-gray-300">&ldquo;<HighlightText text={activeResult.segment_text} query={searchQuery} />&rdquo;</p>
              </div>
            )}
            {activeResult.caption_text && (
              <div className="px-4 py-2 bg-gray-800 border-t border-gray-700">
                <p className="text-[10px] text-teal-400 uppercase font-bold mb-1">AI Scene Description</p>
                <p className="text-sm text-gray-300"><HighlightText text={activeResult.caption_text} query={searchQuery} /></p>
              </div>
            )}

            {/* Annotation panel */}
            {canEdit && videoDetail && (
              <div className="border-t-2 border-blue-500 bg-gray-800 px-4 py-3 space-y-3">
                <p className="text-[10px] text-blue-400 uppercase font-bold tracking-wider flex items-center gap-1.5">
                  <Tag size={10} />
                  Annotations
                </p>

                {/* QuickTagMenu inline */}
                <QuickTagMenu
                  videoIds={[activeResult.video_id]}
                  availableTags={availableTags || []}
                  tagCounts={tagCounts}
                  onClose={() => {}}
                  onTagsChanged={(videoId, newTags) => {
                    // Update tags in results list too
                    setResults(prev => prev.map(r =>
                      r.video_id === videoId ? { ...r, incident_tags: newTags } : r
                    ));
                    onVideoTagsChanged?.(videoId, newTags);
                  }}
                  onCategoryChanged={(videoId, newCat) => {
                    setResults(prev => prev.map(r =>
                      r.video_id === videoId ? { ...r, category: newCat } : r
                    ));
                  }}
                  inline
                />

                {/* Location description */}
                <div>
                  <label className="flex items-center gap-1.5 text-[10px] text-gray-500 uppercase font-bold mb-1">
                    <MapPin size={10} />
                    Location
                  </label>
                  {videoDetail.location && videoDetail.source === 'live' ? (
                    <div className="px-2 py-1.5 bg-gray-900 border border-gray-700 rounded text-xs text-gray-400">
                      <p className="text-white">{annotationLocation || 'No description'}</p>
                      <p className="mt-1 text-[10px] text-green-400">
                        Verified device location: {videoDetail.location.lat.toFixed(5)}, {videoDetail.location.lon.toFixed(5)}
                      </p>
                    </div>
                  ) : (
                    <>
                      <AddressAutocomplete
                        value={annotationLocation}
                        onChange={(val) => { setAnnotationLocation(val); setAnnotationSaved(false); }}
                        onLocationSelect={(loc) => { setGeocodedLocation({ lat: loc.lat, lon: loc.lon }); setAnnotationSaved(false); }}
                        placeholder="Search address or type location..."
                      />
                      {geocodedLocation && (
                        <p className="mt-1 text-[10px] text-green-400">
                          Coordinates: {geocodedLocation.lat.toFixed(5)}, {geocodedLocation.lon.toFixed(5)} (save to apply)
                        </p>
                      )}
                    </>
                  )}
                </div>

                {/* Notes */}
                <div>
                  <label className="flex items-center gap-1.5 text-[10px] text-gray-500 uppercase font-bold mb-1">
                    <FileText size={10} />
                    Notes
                  </label>
                  <textarea
                    value={annotationNotes}
                    onChange={e => { setAnnotationNotes(e.target.value); setAnnotationSaved(false); }}
                    placeholder="Add notes about this video..."
                    rows={2}
                    className="w-full px-2 py-1.5 bg-gray-900 border border-gray-700 rounded text-xs text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 resize-y"
                  />
                </div>

                {/* Save button + error */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleAnnotationSave}
                    disabled={annotationSaving}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-white text-xs font-medium rounded-lg transition"
                  >
                    {annotationSaving ? (
                      <Loader size={12} className="animate-spin" />
                    ) : (
                      <Save size={12} />
                    )}
                    {annotationSaving ? 'Saving...' : 'Save'}
                  </button>
                  {annotationSaved && (
                    <span className="text-xs text-green-400">Saved</span>
                  )}
                  {annotationSaveError && (
                    <span className="text-xs text-red-400">{annotationSaveError}</span>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Results list */}
        <div className="flex-1 overflow-y-auto p-4 relative">
          {error && (
            <div className="p-3 bg-red-900/30 border border-red-500/50 rounded-lg text-sm text-red-400 mb-4">
              {error}
            </div>
          )}

          {loading && (
            <div className="flex justify-center items-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            </div>
          )}

          {!loading && results.length === 0 && !error && (
            <div className="flex flex-col items-center justify-center h-32 text-gray-500">
              <Search size={32} className="mb-2 text-gray-700" />
              <p className="text-sm">Search across all indexed videos using AI</p>
            </div>
          )}

          {results.length > 0 && (
            <>
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs text-gray-500">
                  {results.length} result{results.length !== 1 ? 's' : ''} across {groupedResults.length} video{groupedResults.length !== 1 ? 's' : ''}
                </p>
                {canEdit && (
                  <button
                    onClick={() => selectMode ? exitSelectMode() : setSelectMode(true)}
                    className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium transition ${
                      selectMode
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-800 border border-gray-700 text-gray-400 hover:text-white hover:border-gray-600'
                    }`}
                  >
                    <CheckSquare size={12} />
                    {selectMode ? 'Cancel' : 'Select'}
                  </button>
                )}
              </div>
              <div className="space-y-2 pb-16">
                {groupedResults.map((group) => (
                  <VideoResultGroup
                    key={group.video_id}
                    group={group}
                    mode={mode}
                    onVideoClick={handleVideoClick}
                    onResultClick={handleResultClick}
                    availableTags={availableTags}
                    tagCounts={tagCounts}
                    onVideoTagsChanged={onVideoTagsChanged}
                    canEdit={canEdit}
                    selectMode={selectMode}
                    selectedResults={selectedResults}
                    onToggleSelect={toggleSelectResult}
                    isResultSelected={isResultSelected}
                    searchTiming={searchTiming}
                    searchQuery={searchQuery}
                  />
                ))}
              </div>
            </>
          )}

          {/* Bulk selection sticky bar */}
          {selectMode && selectedResults.length > 0 && (
            <div className="sticky bottom-0 left-0 right-0 bg-gray-800 border-t border-gray-600 rounded-t-lg p-3 flex items-center justify-between shadow-2xl">
              <span className="text-sm text-gray-300">
                {selectedVideoIds.length} video{selectedVideoIds.length !== 1 ? 's' : ''} selected
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
                  onClick={() => setSelectedResults([])}
                  className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs font-medium rounded-lg transition"
                >
                  Clear
                </button>
                {showBulkTagMenu && (
                  <div className="absolute bottom-full right-0 mb-2">
                    <QuickTagMenu
                      videoIds={selectedVideoIds}
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
      </div>
    </div>
  );
}

function formatTimestamp(ms) {
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min}:${sec.toString().padStart(2, '0')}`;
}
