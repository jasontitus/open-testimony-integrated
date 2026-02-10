import React, { useState, useEffect, useCallback } from 'react';
import api from './api';
import { AuthProvider, useAuth } from './auth';
import LoginPage from './components/LoginPage';
import Header from './components/Header';
import VideoList from './components/VideoList';
import SearchFilterBar from './components/SearchFilterBar';
import MapView from './components/MapView';
import VideoDetailPanel from './components/VideoDetailPanel';
import AdminPanel from './components/AdminPanel';
import AISearchPanel from './components/AISearchPanel';

// Fix for Leaflet marker icons in React
import L from 'leaflet';
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
    iconUrl: icon,
    shadowUrl: iconShadow,
    iconSize: [25, 41],
    iconAnchor: [12, 41]
});

L.Marker.prototype.options.icon = DefaultIcon;

function App() {
  return (
    <AuthProvider>
      <AuthGate />
    </AuthProvider>
  );
}

function AuthGate() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (!user) return <LoginPage />;
  return <Dashboard />;
}

const emptyFilters = { search: '', tags: [], category: '', mediaType: '', source: '' };

function Dashboard() {
  const [videos, setVideos] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [initialTimestampMs, setInitialTimestampMs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState('map');
  const [showAdmin, setShowAdmin] = useState(false);
  const [filters, setFilters] = useState(emptyFilters);
  const [tagCounts, setTagCounts] = useState([]);
  const [categoryCounts, setCategoryCounts] = useState([]);

  const fetchCounts = useCallback(async () => {
    try {
      const [tagRes, catRes] = await Promise.all([
        api.get('/tags/counts'),
        api.get('/categories/counts'),
      ]);
      setTagCounts(tagRes.data.tags);
      setCategoryCounts(catRes.data.categories);
    } catch (error) {
      console.error("Error fetching counts:", error);
    }
  }, []);

  const fetchVideos = useCallback(async (f) => {
    const active = f || filters;
    try {
      setLoading(true);
      const params = {};
      if (active.search) params.search = active.search;
      if (active.tags.length) params.tags = active.tags.join(',');
      if (active.category) params.category = active.category;
      if (active.mediaType) params.media_type = active.mediaType;
      if (active.source) params.source = active.source;

      const response = await api.get('/videos', { params });
      setVideos(response.data.videos);
      setTotalCount(response.data.total);
    } catch (error) {
      console.error("Error fetching videos:", error);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { fetchVideos(); }, [fetchVideos]);
  useEffect(() => { fetchCounts(); }, [fetchCounts]);

  const handleFiltersChange = (newFilters) => {
    setFilters(newFilters);
    setSelectedVideo(null);
    setInitialTimestampMs(null);
    fetchVideos(newFilters);
  };

  const handleVideoClick = (video) => {
    setSelectedVideo(video);
    setInitialTimestampMs(null);
    setShowAdmin(false);
  };

  const handleVideoDeleted = (videoId) => {
    setVideos(prev => prev.filter(v => v.id !== videoId));
    setSelectedVideo(null);
    setInitialTimestampMs(null);
    fetchCounts();
  };

  const handleVideoUpdated = () => {
    fetchVideos();
    fetchCounts();
  };

  const handleTagClick = (tag) => {
    if (!filters.tags.includes(tag)) {
      handleFiltersChange({ ...filters, tags: [...filters.tags, tag] });
    }
  };

  const handleCategoryClick = (category) => {
    handleFiltersChange({ ...filters, category });
  };

  const handleAISearchResultClick = (result) => {
    // Navigate to the video at the matched timestamp
    const videoStub = { id: result.video_id };
    setSelectedVideo(videoStub);
    setInitialTimestampMs(result.timestamp_ms || result.start_ms || null);
    // Switch to list view to show the detail panel
    if (viewMode === 'ai-search') {
      setViewMode('list');
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-900 text-white font-sans">
      <Header
        viewMode={viewMode}
        setViewMode={(mode) => {
          setViewMode(mode);
          if (mode === 'ai-search') {
            setShowAdmin(false);
            setSelectedVideo(null);
            setInitialTimestampMs(null);
          }
        }}
        showAdmin={showAdmin}
        onToggleAdmin={() => {
          setShowAdmin(!showAdmin);
          if (!showAdmin) {
            setSelectedVideo(null);
            setInitialTimestampMs(null);
          }
        }}
      />

      <main className="flex-1 flex overflow-hidden">
        {showAdmin ? (
          <AdminPanel />
        ) : viewMode === 'ai-search' ? (
          <AISearchPanel onResultClick={handleAISearchResultClick} />
        ) : (
          <>
            {/* Sidebar */}
            <div className={`w-full md:w-96 bg-gray-800 border-r border-gray-700 flex flex-col ${viewMode === 'map' ? 'hidden md:flex' : 'flex'}`}>
              <SearchFilterBar
                filters={filters}
                onFiltersChange={handleFiltersChange}
                tagCounts={tagCounts}
                categoryCounts={categoryCounts}
                totalCount={totalCount}
                filteredCount={videos.length}
              />
              <VideoList
                videos={videos}
                selectedVideo={selectedVideo}
                onVideoClick={handleVideoClick}
                loading={loading}
                onRefresh={() => fetchVideos()}
                onTagClick={handleTagClick}
                onCategoryClick={handleCategoryClick}
              />
            </div>

            {/* Main content area */}
            <div className="flex-1 relative bg-black">
              {viewMode === 'map' ? (
                <div className="relative h-full w-full">
                  <MapView
                    videos={videos}
                    selectedVideo={selectedVideo}
                    onVideoClick={handleVideoClick}
                  />
                  {selectedVideo && (
                    <div className="fixed inset-0 z-[10000] md:absolute md:inset-auto md:top-0 md:right-0 md:bottom-0 md:w-[420px] md:z-[10000] flex flex-col bg-gray-900 md:border-l md:border-gray-700">
                      <button
                        onClick={() => { setSelectedVideo(null); setInitialTimestampMs(null); }}
                        className="flex items-center gap-2 px-4 py-3 text-gray-300 hover:text-white bg-gray-800 border-b border-gray-700 text-sm shrink-0"
                      >
                        <span className="text-lg">&larr;</span> Back to Map
                      </button>
                      <div className="flex-1 overflow-y-auto overflow-x-hidden">
                        <VideoDetailPanel
                          video={selectedVideo}
                          onVideoDeleted={handleVideoDeleted}
                          onVideoUpdated={handleVideoUpdated}
                          initialTimestampMs={initialTimestampMs}
                        />
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <VideoDetailPanel
                  video={selectedVideo}
                  onVideoDeleted={handleVideoDeleted}
                  onVideoUpdated={handleVideoUpdated}
                  initialTimestampMs={initialTimestampMs}
                />
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

export default App;
