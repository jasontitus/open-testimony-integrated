import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Users, ChevronDown, ChevronRight, Film, Clock, Play, X, Loader, Edit3, Check } from 'lucide-react';
import axios from 'axios';
import api from '../api';

const aiApi = axios.create({ baseURL: '/ai-search', withCredentials: true });

function formatTimestamp(ms) {
  if (ms == null || isNaN(ms)) return '0:00';
  const totalSec = Math.floor(ms / 1000);
  const min = Math.floor(totalSec / 60);
  const sec = totalSec % 60;
  return `${min}:${sec.toString().padStart(2, '0')}`;
}

function FaceThumbnail({ url, size = 'md', className = '' }) {
  const [error, setError] = useState(false);
  const sizeClass = size === 'lg' ? 'w-20 h-20' : size === 'sm' ? 'w-10 h-10' : 'w-14 h-14';
  return (
    <div className={`${sizeClass} rounded-full overflow-hidden bg-gray-700 shrink-0 ${className}`}>
      {url && !error ? (
        <img
          src={`/ai-search${url}`}
          alt="Face"
          className="w-full h-full object-cover"
          onError={() => setError(true)}
        />
      ) : (
        <div className="w-full h-full flex items-center justify-center">
          <Users size={size === 'lg' ? 24 : size === 'sm' ? 12 : 16} className="text-gray-600" />
        </div>
      )}
    </div>
  );
}

function ClusterCard({ cluster, onSelect, isSelected }) {
  return (
    <button
      onClick={() => onSelect(cluster)}
      className={`flex items-center gap-3 p-3 rounded-lg border transition text-left w-full ${
        isSelected
          ? 'bg-orange-600/20 border-orange-500/50'
          : 'bg-gray-800 border-gray-700 hover:border-orange-500/30'
      }`}
    >
      <FaceThumbnail url={cluster.representative_face?.thumbnail_url} size="lg" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-sm font-medium text-white truncate">
            {cluster.label || `Person #${cluster.cluster_id}`}
          </span>
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-400">
          <span className="flex items-center gap-1">
            <Film size={10} />
            {cluster.video_count} video{cluster.video_count !== 1 ? 's' : ''}
          </span>
          <span>{cluster.face_count} detection{cluster.face_count !== 1 ? 's' : ''}</span>
        </div>
      </div>
      <ChevronRight size={16} className="text-gray-500 shrink-0" />
    </button>
  );
}

function VideoAppearanceCard({ video, onPlay }) {
  const [expanded, setExpanded] = useState(false);
  const thumbUrl = video.faces[0]?.thumbnail_url;

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
      {/* Header */}
      <div
        className="flex items-center cursor-pointer hover:bg-gray-750"
        onClick={() => onPlay(video.video_id, video.first_timestamp_ms)}
      >
        <div className="w-28 h-20 bg-gray-900 shrink-0 relative">
          {thumbUrl ? (
            <img
              src={`/ai-search${thumbUrl}`}
              alt=""
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <Film size={20} className="text-gray-700" />
            </div>
          )}
          <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 hover:opacity-100 transition-opacity">
            <Play size={20} className="text-white" fill="white" />
          </div>
        </div>

        <div className="flex-1 px-3 py-2 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Film size={12} className="text-purple-400 shrink-0" />
            <span className="text-xs font-mono text-gray-400 truncate">
              {video.video_id.slice(0, 8)}...
            </span>
            <span className="px-1.5 py-0.5 bg-orange-900/30 border border-orange-500/30 rounded-full text-[10px] text-orange-300 font-medium shrink-0">
              {video.faces.length} appearance{video.faces.length !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="flex items-center gap-1 text-xs text-gray-300">
            <Clock size={10} className="text-gray-500" />
            <span>First seen at {formatTimestamp(video.first_timestamp_ms)}</span>
          </div>
        </div>

        <button
          onClick={(e) => { e.stopPropagation(); setExpanded(prev => !prev); }}
          className="px-3 py-2 shrink-0 text-gray-500 hover:text-white transition"
        >
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </button>
      </div>

      {/* Expanded face timeline */}
      {expanded && (
        <div className="border-t border-gray-700 bg-gray-850 p-3">
          <p className="text-[10px] text-gray-500 uppercase font-bold mb-2">
            Face detections (click to jump)
          </p>
          <div className="flex flex-wrap gap-2">
            {video.faces.map((face) => (
              <button
                key={face.face_id}
                onClick={() => onPlay(video.video_id, face.timestamp_ms)}
                className="flex items-center gap-2 px-2 py-1.5 bg-gray-900 rounded-lg hover:bg-gray-700 transition"
              >
                <FaceThumbnail url={face.thumbnail_url} size="sm" />
                <div className="text-left">
                  <div className="text-xs text-gray-300">{formatTimestamp(face.timestamp_ms)}</div>
                  <div className="text-[10px] text-gray-500">{Math.round(face.detection_score * 100)}% conf</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function FaceClusterPanel({ onVideoPlay }) {
  const [clusters, setClusters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCluster, setSelectedCluster] = useState(null);
  const [clusterDetail, setClusterDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [stats, setStats] = useState(null);

  // Inline video player
  const [activeVideoId, setActiveVideoId] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [videoLoading, setVideoLoading] = useState(false);
  const [seekTimestamp, setSeekTimestamp] = useState(null);
  const videoRef = useRef(null);

  // Label editing
  const [editingLabel, setEditingLabel] = useState(false);
  const [labelValue, setLabelValue] = useState('');

  const fetchClusters = useCallback(async () => {
    try {
      setLoading(true);
      const [clustersRes, statsRes] = await Promise.all([
        aiApi.get('/faces/clusters'),
        aiApi.get('/faces/stats'),
      ]);
      setClusters(clustersRes.data.clusters || []);
      setStats(statsRes.data);
    } catch (err) {
      console.error('Failed to load face clusters:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchClusters(); }, [fetchClusters]);

  const handleSelectCluster = async (cluster) => {
    setSelectedCluster(cluster);
    setClusterDetail(null);
    setDetailLoading(true);
    setActiveVideoId(null);
    setVideoUrl(null);
    setEditingLabel(false);
    setLabelValue(cluster.label || '');

    try {
      const res = await aiApi.get(`/faces/cluster/${cluster.cluster_id}`);
      setClusterDetail(res.data);
    } catch (err) {
      console.error('Failed to load cluster detail:', err);
    } finally {
      setDetailLoading(false);
    }
  };

  const handlePlayVideo = async (videoId, timestampMs) => {
    setActiveVideoId(videoId);
    setSeekTimestamp(timestampMs);
    setVideoUrl(null);
    setVideoLoading(true);

    try {
      const res = await api.get(`/videos/${videoId}/url`);
      setVideoUrl(res.data.url);
    } catch {
      setVideoUrl(null);
    } finally {
      setVideoLoading(false);
    }
  };

  // Seek video when loaded
  useEffect(() => {
    if (!videoRef.current || !videoUrl || seekTimestamp == null) return;
    const el = videoRef.current;
    const seekSec = seekTimestamp / 1000;
    const trySeek = () => {
      el.currentTime = seekSec;
      el.removeEventListener('loadedmetadata', trySeek);
    };
    if (el.readyState >= 1) {
      el.currentTime = seekSec;
    } else {
      el.addEventListener('loadedmetadata', trySeek);
    }
  }, [videoUrl, seekTimestamp]);

  const handleSaveLabel = async () => {
    if (!selectedCluster) return;
    try {
      await aiApi.put(`/faces/cluster/${selectedCluster.cluster_id}/label`, {
        label: labelValue.trim(),
      });
      setEditingLabel(false);
      // Update local state
      const newLabel = labelValue.trim() || null;
      setSelectedCluster(prev => ({ ...prev, label: newLabel }));
      setClusters(prev => prev.map(c =>
        c.cluster_id === selectedCluster.cluster_id ? { ...c, label: newLabel } : c
      ));
    } catch (err) {
      console.error('Failed to save label:', err);
    }
  };

  return (
    <div className="h-full flex flex-col bg-gray-900 w-full">
      {/* Header */}
      <div className="p-4 border-b border-gray-700 shrink-0">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Users size={20} className="text-orange-400" />
            <h2 className="text-lg font-bold text-white">Face Clusters</h2>
          </div>
          {stats && (
            <div className="flex gap-3 text-[10px] uppercase tracking-wider text-gray-500">
              <span>{stats.total_clusters} people</span>
              <span>{stats.total_faces} faces</span>
              <span>{stats.videos_with_faces} videos</span>
            </div>
          )}
        </div>
        <p className="text-xs text-gray-500">
          Click a person to see all videos they appear in. Videos autoplay from their first detection.
        </p>
      </div>

      <div className="flex-1 overflow-hidden flex flex-col md:flex-row">
        {/* Cluster list (left sidebar) */}
        <div className={`${selectedCluster ? 'hidden md:block' : 'block'} md:w-80 lg:w-96 border-r border-gray-700 overflow-y-auto p-3 space-y-2`}>
          {loading ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500"></div>
            </div>
          ) : clusters.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-500">
              <Users size={32} className="mb-2 text-gray-700" />
              <p className="text-sm">No face clusters yet</p>
              <p className="text-xs text-gray-600 mt-1">Enable face clustering and index videos to detect faces</p>
            </div>
          ) : (
            clusters.map((cluster) => (
              <ClusterCard
                key={cluster.cluster_id}
                cluster={cluster}
                onSelect={handleSelectCluster}
                isSelected={selectedCluster?.cluster_id === cluster.cluster_id}
              />
            ))
          )}
        </div>

        {/* Cluster detail (right panel) */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {/* Video player (top) */}
          {activeVideoId && (
            <div className="shrink-0 border-b border-gray-700">
              <div className="flex items-center justify-between px-4 py-2 bg-gray-800">
                <span className="text-xs text-gray-400 font-mono">
                  {activeVideoId.slice(0, 8)}... @ {formatTimestamp(seekTimestamp || 0)}
                </span>
                <button
                  onClick={() => { setActiveVideoId(null); setVideoUrl(null); }}
                  className="text-gray-500 hover:text-white transition"
                >
                  <X size={16} />
                </button>
              </div>
              <div className="bg-black flex items-center justify-center min-h-[200px] max-h-[50vh]">
                {videoLoading ? (
                  <Loader size={24} className="animate-spin text-blue-500" />
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
            </div>
          )}

          {/* Video appearances list */}
          <div className="flex-1 overflow-y-auto p-4">
            {!selectedCluster ? (
              <div className="flex flex-col items-center justify-center h-full text-gray-500">
                <Users size={48} className="mb-3 text-gray-700" />
                <p className="text-sm">Select a person to see their video appearances</p>
              </div>
            ) : detailLoading ? (
              <div className="flex justify-center py-12">
                <Loader size={24} className="animate-spin text-orange-500" />
              </div>
            ) : clusterDetail ? (
              <>
                {/* Cluster header with label editing */}
                <div className="flex items-center gap-3 mb-4">
                  <FaceThumbnail
                    url={selectedCluster.representative_face?.thumbnail_url}
                    size="lg"
                  />
                  <div className="flex-1">
                    {editingLabel ? (
                      <div className="flex items-center gap-2">
                        <input
                          autoFocus
                          value={labelValue}
                          onChange={(e) => setLabelValue(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleSaveLabel();
                            if (e.key === 'Escape') setEditingLabel(false);
                          }}
                          placeholder="Enter name or label..."
                          className="px-2 py-1 bg-gray-800 border border-gray-600 rounded text-sm text-white focus:outline-none focus:border-orange-500"
                        />
                        <button onClick={handleSaveLabel} className="text-green-400 hover:text-green-300">
                          <Check size={16} />
                        </button>
                        <button onClick={() => setEditingLabel(false)} className="text-gray-500 hover:text-gray-300">
                          <X size={16} />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <h3 className="text-lg font-bold text-white">
                          {selectedCluster.label || `Person #${selectedCluster.cluster_id}`}
                        </h3>
                        <button
                          onClick={() => { setEditingLabel(true); setLabelValue(selectedCluster.label || ''); }}
                          className="text-gray-500 hover:text-orange-400 transition"
                          title="Edit label"
                        >
                          <Edit3 size={14} />
                        </button>
                      </div>
                    )}
                    <p className="text-xs text-gray-400 mt-0.5">
                      {clusterDetail.face_count} detections across {clusterDetail.video_count} video{clusterDetail.video_count !== 1 ? 's' : ''}
                    </p>
                  </div>
                  {/* Back button (mobile) */}
                  <button
                    onClick={() => { setSelectedCluster(null); setClusterDetail(null); setActiveVideoId(null); }}
                    className="md:hidden px-3 py-1.5 text-sm text-gray-400 hover:text-white bg-gray-800 rounded-lg"
                  >
                    Back
                  </button>
                </div>

                {/* Video appearances */}
                <div className="space-y-2">
                  {clusterDetail.videos.map((video) => (
                    <VideoAppearanceCard
                      key={video.video_id}
                      video={video}
                      onPlay={handlePlayVideo}
                    />
                  ))}
                </div>
              </>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
