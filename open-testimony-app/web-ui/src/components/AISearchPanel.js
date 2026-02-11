import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Search, Upload, Film, MessageSquare, Loader, X } from 'lucide-react';
import axios from 'axios';
import api from '../api';
import AISearchResultCard from './AISearchResultCard';

const SEARCH_MODES = [
  { id: 'visual_text', label: 'Visual (Text)', icon: Film, description: 'Describe what you see' },
  { id: 'visual_image', label: 'Visual (Image)', icon: Upload, description: 'Upload a reference image' },
  { id: 'transcript_semantic', label: 'Transcript (Semantic)', icon: MessageSquare, description: 'Search by meaning' },
  { id: 'transcript_exact', label: 'Transcript (Exact)', icon: Search, description: 'Search exact words' },
];

const aiApi = axios.create({
  baseURL: '/ai-search',
  withCredentials: true,
});

export default function AISearchPanel({ onResultClick }) {
  const [mode, setMode] = useState('visual_text');
  const [query, setQuery] = useState('');
  const [imageFile, setImageFile] = useState(null);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [stats, setStats] = useState(null);

  // Inline video player state
  const [activeResult, setActiveResult] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [videoLoading, setVideoLoading] = useState(false);
  const videoRef = useRef(null);

  const fetchStats = useCallback(async () => {
    try {
      const res = await aiApi.get('/indexing/status');
      setStats(res.data);
    } catch {
      // Bridge may not be running
    }
  }, []);

  React.useEffect(() => { fetchStats(); }, [fetchStats]);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (mode !== 'visual_image' && !query.trim()) return;
    if (mode === 'visual_image' && !imageFile) return;

    setLoading(true);
    setError('');
    setResults([]);
    setActiveResult(null);
    setVideoUrl(null);

    try {
      let res;
      if (mode === 'visual_text') {
        res = await aiApi.get('/search/visual', { params: { q: query, limit: 20 } });
      } else if (mode === 'visual_image') {
        const formData = new FormData();
        formData.append('image', imageFile);
        res = await aiApi.post('/search/visual', formData, { params: { limit: 20 } });
      } else if (mode === 'transcript_semantic') {
        res = await aiApi.get('/search/transcript', { params: { q: query, limit: 20 } });
      } else if (mode === 'transcript_exact') {
        res = await aiApi.get('/search/transcript/exact', { params: { q: query, limit: 20 } });
      }
      setResults(res.data.results || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Search failed. Is the bridge service running?');
    } finally {
      setLoading(false);
    }
  };

  // When a result is clicked, open inline player
  const handleResultClick = async (result) => {
    setActiveResult(result);
    setVideoUrl(null);
    setVideoLoading(true);
    try {
      const res = await api.get(`/videos/${result.video_id}/url`);
      setVideoUrl(res.data.url);
    } catch {
      setVideoUrl(null);
    } finally {
      setVideoLoading(false);
    }
  };

  // Seek to timestamp when video loads
  useEffect(() => {
    if (!activeResult || !videoRef.current || !videoUrl) return;
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

  return (
    <div className="h-full flex flex-col bg-gray-900 w-full">
      {/* Search mode selector + form */}
      <div className="p-4 border-b border-gray-700 shrink-0">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
          {SEARCH_MODES.map(m => {
            const Icon = m.icon;
            return (
              <button
                key={m.id}
                onClick={() => { setMode(m.id); setResults([]); setError(''); setActiveResult(null); }}
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

        <form onSubmit={handleSearch} className="flex gap-2">
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
                onChange={e => setImageFile(e.target.files[0] || null)}
              />
            </label>
          ) : (
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder={
                mode === 'visual_text' ? 'Describe what you\'re looking for...' :
                mode === 'transcript_semantic' ? 'Search by meaning...' :
                'Search exact words...'
              }
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
        {/* Inline video player (shown when a result is clicked) */}
        {activeResult && (
          <div className="md:w-1/2 lg:w-3/5 shrink-0 flex flex-col border-b md:border-b-0 md:border-r border-gray-700">
            <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
              <span className="text-xs text-gray-400 font-mono">
                {activeResult.video_id.slice(0, 8)}... @ {formatTimestamp(activeResult.timestamp_ms || activeResult.start_ms || 0)}
              </span>
              <button
                onClick={() => { setActiveResult(null); setVideoUrl(null); }}
                className="text-gray-500 hover:text-white transition"
              >
                <X size={16} />
              </button>
            </div>
            <div className="flex-1 bg-black flex items-center justify-center min-h-[200px]">
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
                <p className="text-sm text-gray-300">&ldquo;{activeResult.segment_text}&rdquo;</p>
              </div>
            )}
          </div>
        )}

        {/* Results list */}
        <div className="flex-1 overflow-y-auto p-4">
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
              <p className="text-xs text-gray-500 mb-3">{results.length} results</p>
              <div className="space-y-2">
                {results.map((result, i) => (
                  <AISearchResultCard
                    key={`${result.video_id}-${result.timestamp_ms || result.start_ms}-${i}`}
                    result={result}
                    mode={mode}
                    onClick={handleResultClick}
                  />
                ))}
              </div>
            </>
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
