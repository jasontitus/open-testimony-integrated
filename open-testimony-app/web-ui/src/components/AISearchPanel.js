import React, { useState, useCallback } from 'react';
import { Search, Upload, Film, MessageSquare, Loader } from 'lucide-react';
import axios from 'axios';
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

  const fetchStats = useCallback(async () => {
    try {
      const res = await aiApi.get('/indexing/status');
      setStats(res.data);
    } catch {
      // Bridge may not be running
    }
  }, []);

  // Fetch stats on mount
  React.useEffect(() => { fetchStats(); }, [fetchStats]);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (mode !== 'visual_image' && !query.trim()) return;
    if (mode === 'visual_image' && !imageFile) return;

    setLoading(true);
    setError('');
    setResults([]);

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

  return (
    <div className="h-full flex flex-col bg-gray-900">
      {/* Search mode selector */}
      <div className="p-4 border-b border-gray-700">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
          {SEARCH_MODES.map(m => {
            const Icon = m.icon;
            return (
              <button
                key={m.id}
                onClick={() => { setMode(m.id); setResults([]); setError(''); }}
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

        {/* Search form */}
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

        {/* Indexing stats */}
        {stats && (
          <div className="flex gap-3 mt-3 text-[10px] uppercase tracking-wider text-gray-500">
            <span>{stats.completed || 0} indexed</span>
            <span>{stats.processing || 0} processing</span>
            <span>{stats.pending || 0} pending</span>
          </div>
        )}
      </div>

      {/* Results */}
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
            <div className="space-y-3">
              {results.map((result, i) => (
                <AISearchResultCard
                  key={`${result.video_id}-${result.timestamp_ms || result.start_ms}-${i}`}
                  result={result}
                  mode={mode}
                  onClick={onResultClick}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
