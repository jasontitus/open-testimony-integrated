import React, { useState, useEffect, useCallback, useRef } from 'react';
import { format } from 'date-fns';
import {
  CheckCircle, Flag, Clock, ChevronLeft, ChevronRight,
  ArrowUpDown, Tag, Filter, RotateCcw, User, AlertCircle,
  ArrowLeft,
} from 'lucide-react';
import api from '../api';
import { useAuth } from '../auth';
import VerificationBadge from './VerificationBadge';
import SourceBadge from './SourceBadge';
import MediaTypeBadge from './MediaTypeBadge';
import QuickTagMenu from './QuickTagMenu';
import AddressAutocomplete from './AddressAutocomplete';

const SORT_OPTIONS = [
  { value: 'oldest', label: 'Oldest First' },
  { value: 'newest', label: 'Newest First' },
  { value: 'tag', label: 'Least Tagged' },
];

const STATUS_TABS = [
  { value: 'pending', label: 'Pending', icon: Clock },
  { value: 'flagged', label: 'Flagged', icon: Flag },
  { value: 'reviewed', label: 'Reviewed', icon: CheckCircle },
];

export default function QueuePanel() {
  const { user } = useAuth();
  const [queue, setQueue] = useState([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState({ pending: 0, reviewed: 0, flagged: 0, total: 0 });
  const [loading, setLoading] = useState(true);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [sortOrder, setSortOrder] = useState('oldest');
  const [tagFilter, setTagFilter] = useState('');
  const [availableTags, setAvailableTags] = useState([]);
  const [tagCounts, setTagCounts] = useState([]);
  const [showTagFilter, setShowTagFilter] = useState(false);

  // Detail state for current item
  const [detail, setDetail] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [auditLog, setAuditLog] = useState([]);

  // Editable fields
  const [notes, setNotes] = useState('');
  const [locationDescription, setLocationDescription] = useState('');
  const [geocodedLocation, setGeocodedLocation] = useState(null);

  // Mobile: toggle between list view and detail view
  const [mobileShowDetail, setMobileShowDetail] = useState(false);

  const videoRef = useRef(null);
  const tagFilterRef = useRef(null);

  const currentVideo = queue[currentIndex] || null;

  // Fetch queue
  const fetchQueue = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        review_status: statusFilter,
        sort: sortOrder,
        limit: 200,
      };
      if (tagFilter) params.tags = tagFilter;
      const res = await api.get('/queue', { params });
      setQueue(res.data.videos);
      setTotal(res.data.total);
    } catch (err) {
      console.error('Error fetching queue:', err);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, sortOrder, tagFilter]);

  // Fetch stats
  const fetchStats = useCallback(async () => {
    try {
      const res = await api.get('/queue/stats');
      setStats(res.data);
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  }, []);

  // Fetch tags
  const fetchTags = useCallback(async () => {
    try {
      const [tagsRes, countsRes] = await Promise.all([
        api.get('/tags'),
        api.get('/tags/counts'),
      ]);
      setAvailableTags(tagsRes.data.all_tags || []);
      setTagCounts(countsRes.data.tags || []);
    } catch (err) {
      console.error('Error fetching tags:', err);
    }
  }, []);

  useEffect(() => { fetchQueue(); }, [fetchQueue]);
  useEffect(() => { fetchStats(); }, [fetchStats]);
  useEffect(() => { fetchTags(); }, [fetchTags]);

  // Reset index when queue changes
  useEffect(() => {
    setCurrentIndex(0);
  }, [statusFilter, sortOrder, tagFilter]);

  // Load detail for current video
  useEffect(() => {
    if (!currentVideo) {
      setDetail(null);
      setVideoUrl(null);
      setAuditLog([]);
      return;
    }

    setDetail(null);
    setVideoUrl(null);
    setAuditLog([]);
    setSaveError('');

    api.get(`/videos/${currentVideo.id}`).then(res => {
      setDetail(res.data);
      setNotes(res.data.notes || '');
      setLocationDescription(res.data.location_description || '');
      setGeocodedLocation(null);
    }).catch(() => {});

    api.get(`/videos/${currentVideo.id}/url`).then(res => {
      setVideoUrl(res.data.url);
    }).catch(() => {});

    api.get(`/videos/${currentVideo.id}/audit`).then(res => {
      setAuditLog(res.data.entries || []);
    }).catch(() => {});
  }, [currentVideo?.id]);

  const handleReview = async (status) => {
    if (!currentVideo) return;
    setSaving(true);
    try {
      await api.put(`/videos/${currentVideo.id}/review`, { review_status: status });
      // Update local queue item
      setQueue(prev => prev.map(v =>
        v.id === currentVideo.id
          ? { ...v, review_status: status, reviewed_by: user?.username, reviewed_at: new Date().toISOString() }
          : v
      ));
      fetchStats();
      // If viewing pending, auto-advance after marking reviewed
      if (statusFilter === 'pending' && status !== 'pending') {
        setQueue(prev => prev.filter(v => v.id !== currentVideo.id));
        setTotal(prev => prev - 1);
        // Index stays the same (next item slides in), but clamp
        setCurrentIndex(prev => Math.min(prev, queue.length - 2));
      }
      // Refresh audit log
      api.get(`/videos/${currentVideo.id}/audit`).then(res => {
        setAuditLog(res.data.entries || []);
      }).catch(() => {});
    } catch (err) {
      setSaveError(err.response?.data?.detail || 'Failed to update review status');
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAnnotations = async () => {
    if (!currentVideo) return;
    setSaving(true);
    setSaveError('');
    try {
      const payload = {
        notes,
        location_description: locationDescription,
      };
      if (geocodedLocation) {
        payload.latitude = geocodedLocation.lat;
        payload.longitude = geocodedLocation.lon;
      }
      await api.put(`/videos/${currentVideo.id}/annotations/web`, payload);
      setGeocodedLocation(null);
      setDetail(prev => prev ? {
        ...prev,
        notes: notes || null,
        location_description: locationDescription || null,
      } : prev);
      // Update queue item too
      setQueue(prev => prev.map(v =>
        v.id === currentVideo.id
          ? { ...v, notes: notes || null, location_description: locationDescription || null }
          : v
      ));
      // Refresh audit log
      api.get(`/videos/${currentVideo.id}/audit`).then(res => {
        setAuditLog(res.data.entries || []);
      }).catch(() => {});
    } catch (err) {
      setSaveError(err.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleVideoTagsChanged = useCallback((videoId, newTags) => {
    setQueue(prev => prev.map(v =>
      v.id === videoId ? { ...v, incident_tags: newTags } : v
    ));
    setDetail(prev => prev && prev.id === videoId ? { ...prev, incident_tags: newTags } : prev);
    fetchTags();
  }, [fetchTags]);

  const handleCategoryChanged = useCallback((videoId, newCat) => {
    setQueue(prev => prev.map(v =>
      v.id === videoId ? { ...v, category: newCat } : v
    ));
    setDetail(prev => prev && prev.id === videoId ? { ...prev, category: newCat } : prev);
  }, []);

  const goNext = () => setCurrentIndex(prev => Math.min(prev + 1, queue.length - 1));
  const goPrev = () => setCurrentIndex(prev => Math.max(prev - 1, 0));

  const hasAnnotationChanges = detail && (
    notes !== (detail.notes || '') ||
    locationDescription !== (detail.location_description || '') ||
    geocodedLocation !== null
  );

  // Keyboard navigation
  useEffect(() => {
    const handler = (e) => {
      // Don't intercept when typing in an input/textarea
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
      if (e.key === 'ArrowRight' || e.key === 'j') goNext();
      if (e.key === 'ArrowLeft' || e.key === 'k') goPrev();
      if (e.key === 'r') handleReview('reviewed');
      if (e.key === 'f') handleReview('flagged');
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  });

  // Progress percentage
  const progressPct = stats.total > 0 ? Math.round(((stats.reviewed + stats.flagged) / stats.total) * 100) : 0;

  return (
    <div className="flex flex-col h-full w-full overflow-hidden">
      {/* Queue Header */}
      <div className="shrink-0 bg-gray-800 border-b border-gray-700 px-4 py-3">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-bold text-gray-200 uppercase tracking-wider">Review Queue</h2>
            <span className="text-xs text-gray-500">
              {stats.reviewed + stats.flagged} / {stats.total} done
            </span>
          </div>
          <button
            onClick={() => { fetchQueue(); fetchStats(); fetchTags(); }}
            className="text-gray-500 hover:text-white transition p-1"
            title="Refresh"
          >
            <RotateCcw size={14} />
          </button>
        </div>

        {/* Progress bar */}
        <div className="w-full bg-gray-700 rounded-full h-2 mb-3">
          <div
            className="bg-green-500 h-2 rounded-full transition-all duration-500"
            style={{ width: `${progressPct}%` }}
          />
        </div>

        {/* Status tabs */}
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          {STATUS_TABS.map(tab => {
            const Icon = tab.icon;
            const count = stats[tab.value] || 0;
            const active = statusFilter === tab.value;
            return (
              <button
                key={tab.value}
                onClick={() => setStatusFilter(tab.value)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition border ${
                  active
                    ? tab.value === 'pending' ? 'bg-yellow-600/20 border-yellow-500/50 text-yellow-300'
                    : tab.value === 'flagged' ? 'bg-orange-600/20 border-orange-500/50 text-orange-300'
                    : 'bg-green-600/20 border-green-500/50 text-green-300'
                    : 'bg-gray-900 border-gray-700 text-gray-500 hover:text-gray-300 hover:border-gray-600'
                }`}
              >
                <Icon size={12} />
                {tab.label}
                <span className={`ml-0.5 px-1.5 py-0.5 rounded-full text-[10px] ${
                  active ? 'bg-white/10' : 'bg-gray-800'
                }`}>{count}</span>
              </button>
            );
          })}
        </div>

        {/* Sort and filter controls */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Sort */}
          <div className="flex items-center gap-1.5">
            <ArrowUpDown size={12} className="text-gray-500" />
            <select
              value={sortOrder}
              onChange={e => setSortOrder(e.target.value)}
              className="bg-gray-900 border border-gray-700 rounded-lg text-xs text-gray-300 px-2 py-1.5 focus:outline-none focus:border-blue-500"
            >
              {SORT_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          {/* Tag filter */}
          <div className="relative">
            <button
              onClick={() => setShowTagFilter(!showTagFilter)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition border ${
                tagFilter
                  ? 'bg-blue-600/20 border-blue-500/50 text-blue-300'
                  : 'bg-gray-900 border-gray-700 text-gray-500 hover:text-gray-300 hover:border-gray-600'
              }`}
            >
              <Filter size={12} />
              {tagFilter ? `Tag: ${tagFilter}` : 'Filter by Tag'}
            </button>
            {showTagFilter && (
              <TagFilterDropdown
                availableTags={availableTags}
                tagCounts={tagCounts}
                selected={tagFilter}
                onSelect={(tag) => { setTagFilter(tag); setShowTagFilter(false); }}
                onClose={() => setShowTagFilter(false)}
                inputRef={tagFilterRef}
              />
            )}
          </div>

          {tagFilter && (
            <button
              onClick={() => setTagFilter('')}
              className="text-xs text-gray-500 hover:text-white transition"
            >
              Clear filter
            </button>
          )}
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Queue list (sidebar) — full-width on mobile, hidden when viewing detail */}
        <div className={`w-full md:w-80 shrink-0 bg-gray-800 border-r border-gray-700 flex flex-col overflow-hidden ${
          mobileShowDetail ? 'hidden md:flex' : 'flex'
        }`}>
          <div className="px-3 py-2 border-b border-gray-700 text-xs text-gray-500">
            {total} item{total !== 1 ? 's' : ''} {statusFilter}
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="flex justify-center items-center h-32">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
              </div>
            ) : queue.length === 0 ? (
              <div className="p-6 text-center">
                <CheckCircle size={32} className="mx-auto text-green-500 mb-2" />
                <p className="text-sm text-gray-400">
                  {statusFilter === 'pending' ? 'All items reviewed!' : `No ${statusFilter} items`}
                </p>
              </div>
            ) : (
              queue.map((video, idx) => (
                <button
                  key={video.id}
                  onClick={() => {
                    setCurrentIndex(idx);
                    setMobileShowDetail(true);
                  }}
                  className={`w-full text-left p-3 border-b border-gray-700 transition hover:bg-gray-750 ${
                    idx === currentIndex ? 'bg-gray-700 border-l-4 border-l-blue-500' : ''
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-1.5">
                      <MediaTypeBadge mediaType={video.media_type} />
                      <span className="text-[10px] font-mono text-blue-400 truncate max-w-[100px]">
                        {video.device_id}
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <SourceBadge source={video.source} />
                      <VerificationBadge status={video.verification_status} />
                    </div>
                  </div>
                  <div className="flex items-center text-[11px] text-gray-400 mb-1">
                    <Clock size={10} className="mr-1 text-gray-600" />
                    {format(new Date(video.uploaded_at), 'MMM d, yyyy HH:mm')}
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {video.category && (
                      <span className="px-1.5 py-0.5 bg-indigo-900/30 border border-indigo-500/40 rounded-full text-[9px] text-indigo-300 uppercase">
                        {video.category}
                      </span>
                    )}
                    {(video.incident_tags || []).slice(0, 3).map(tag => (
                      <span key={tag} className="px-1.5 py-0.5 bg-gray-900 border border-gray-600 rounded-full text-[9px] text-gray-400 uppercase">
                        {tag}
                      </span>
                    ))}
                    {(video.incident_tags || []).length > 3 && (
                      <span className="text-[9px] text-gray-600">+{video.incident_tags.length - 3}</span>
                    )}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Detail pane — hidden on mobile unless viewing detail */}
        <div className={`flex-1 overflow-y-auto bg-gray-900 p-4 md:p-6 ${
          mobileShowDetail ? 'flex flex-col' : 'hidden md:block'
        }`}>
          {!currentVideo ? (
            <div className="h-full flex flex-col items-center justify-center">
              <CheckCircle size={48} className="text-gray-700 mb-3" />
              <p className="text-gray-500 text-sm">
                {statusFilter === 'pending' ? 'No pending items to review' : 'Select an item from the queue'}
              </p>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto w-full">
              {/* Navigation bar */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  {/* Back to list — mobile only */}
                  <button
                    onClick={() => setMobileShowDetail(false)}
                    className="md:hidden p-2 rounded-lg bg-gray-800 border border-gray-700 text-gray-400 hover:text-white hover:border-gray-600 transition"
                    title="Back to list"
                  >
                    <ArrowLeft size={16} />
                  </button>
                  <button
                    onClick={goPrev}
                    disabled={currentIndex === 0}
                    className="p-2 rounded-lg bg-gray-800 border border-gray-700 text-gray-400 hover:text-white hover:border-gray-600 disabled:opacity-30 disabled:cursor-not-allowed transition"
                    title="Previous (Left arrow or K)"
                  >
                    <ChevronLeft size={16} />
                  </button>
                  <span className="text-sm text-gray-400">
                    {currentIndex + 1} of {queue.length}
                  </span>
                  <button
                    onClick={goNext}
                    disabled={currentIndex >= queue.length - 1}
                    className="p-2 rounded-lg bg-gray-800 border border-gray-700 text-gray-400 hover:text-white hover:border-gray-600 disabled:opacity-30 disabled:cursor-not-allowed transition"
                    title="Next (Right arrow or J)"
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>

                {/* Review action buttons */}
                <div className="flex items-center gap-1 md:gap-2">
                  {currentVideo.review_status !== 'pending' && (
                    <button
                      onClick={() => handleReview('pending')}
                      disabled={saving}
                      className="flex items-center gap-1.5 px-2 md:px-3 py-2 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 text-gray-300 text-sm rounded-lg transition"
                    >
                      <RotateCcw size={14} />
                      <span className="hidden md:inline">Reset</span>
                    </button>
                  )}
                  <button
                    onClick={() => handleReview('flagged')}
                    disabled={saving || currentVideo.review_status === 'flagged'}
                    className={`flex items-center gap-1.5 px-2 md:px-3 py-2 text-sm rounded-lg transition ${
                      currentVideo.review_status === 'flagged'
                        ? 'bg-orange-600/30 border border-orange-500/50 text-orange-300 cursor-default'
                        : 'bg-orange-600 hover:bg-orange-500 disabled:bg-orange-800 text-white'
                    }`}
                    title="Flag for follow-up (F)"
                  >
                    <Flag size={14} />
                    <span className="hidden md:inline">{currentVideo.review_status === 'flagged' ? 'Flagged' : 'Flag'}</span>
                  </button>
                  <button
                    onClick={() => handleReview('reviewed')}
                    disabled={saving || currentVideo.review_status === 'reviewed'}
                    className={`flex items-center gap-1.5 px-2 md:px-3 py-2 text-sm rounded-lg transition ${
                      currentVideo.review_status === 'reviewed'
                        ? 'bg-green-600/30 border border-green-500/50 text-green-300 cursor-default'
                        : 'bg-green-600 hover:bg-green-500 disabled:bg-green-800 text-white'
                    }`}
                    title="Mark as reviewed (R)"
                  >
                    <CheckCircle size={14} />
                    <span className="hidden md:inline">{currentVideo.review_status === 'reviewed' ? 'Reviewed' : 'Mark Reviewed'}</span>
                  </button>
                </div>
              </div>

              {saveError && (
                <div className="mb-4 p-3 bg-red-900/30 border border-red-500/50 rounded-lg text-sm text-red-400 flex items-center gap-2">
                  <AlertCircle size={14} />
                  {saveError}
                </div>
              )}

              {/* Media player */}
              <div className="aspect-video bg-black rounded-xl overflow-hidden mb-4">
                {videoUrl ? (
                  detail?.media_type === 'photo' ? (
                    <img src={videoUrl} alt="Testimony" className="w-full h-full object-contain" />
                  ) : (
                    <video ref={videoRef} src={videoUrl} controls playsInline className="w-full h-full" />
                  )
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
                  </div>
                )}
              </div>

              {/* Badges */}
              <div className="flex items-center gap-2 flex-wrap mb-4">
                <VerificationBadge status={currentVideo.verification_status} />
                <SourceBadge source={currentVideo.source} />
                <MediaTypeBadge mediaType={currentVideo.media_type} />
                {currentVideo.reviewed_by && (
                  <span className="flex items-center gap-1 px-2 py-0.5 bg-gray-800 border border-gray-700 rounded-full text-[10px] text-gray-400">
                    <User size={10} />
                    {currentVideo.reviewed_by}
                  </span>
                )}
              </div>

              {/* Category & Tags */}
              {detail && (
                <div className="mb-4">
                  <label className="block text-[10px] text-gray-500 uppercase font-bold mb-1">Category & Tags</label>
                  <QuickTagMenu
                    inline
                    videoIds={[currentVideo.id]}
                    availableTags={availableTags}
                    tagCounts={tagCounts}
                    onClose={() => {}}
                    onTagsChanged={handleVideoTagsChanged}
                    onCategoryChanged={handleCategoryChanged}
                  />
                </div>
              )}

              {/* Location */}
              <div className="mb-4">
                <label className="block text-[10px] text-gray-500 uppercase font-bold mb-1">Location Description</label>
                {detail?.location && detail?.source === 'live' ? (
                  <div className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-400">
                    <p className="text-white">{locationDescription || 'No description'}</p>
                    <p className="mt-1 text-[10px] text-green-400">
                      Verified device location: {detail.location.lat.toFixed(5)}, {detail.location.lon.toFixed(5)}
                    </p>
                  </div>
                ) : (
                  <>
                    <AddressAutocomplete
                      value={locationDescription}
                      onChange={setLocationDescription}
                      onLocationSelect={(loc) => setGeocodedLocation({ lat: loc.lat, lon: loc.lon })}
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
              <div className="mb-4">
                <label className="block text-[10px] text-gray-500 uppercase font-bold mb-1">Notes</label>
                <textarea
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                  rows={2}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500 resize-none"
                  placeholder="Additional context or notes..."
                />
              </div>

              {/* Save annotations button */}
              {hasAnnotationChanges && (
                <div className="flex justify-end mb-4">
                  <button
                    onClick={handleSaveAnnotations}
                    disabled={saving}
                    className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-white text-sm font-medium rounded-lg transition"
                  >
                    {saving ? 'Saving...' : 'Save Changes'}
                  </button>
                </div>
              )}

              {/* Technical metadata */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
                <MetaCard label="Captured" value={format(new Date(currentVideo.timestamp), 'PPpp')} />
                <MetaCard label="Uploaded" value={format(new Date(currentVideo.uploaded_at), 'PPpp')} />
                <MetaCard label="Device ID" value={currentVideo.device_id} mono />
                <MetaCard label="Location" value={
                  currentVideo.location
                    ? `${currentVideo.location.lat.toFixed(5)}, ${currentVideo.location.lon.toFixed(5)}`
                    : 'Unknown'
                } />
              </div>

              {/* Audit log */}
              {auditLog.length > 0 && (
                <div>
                  <p className="text-[10px] text-gray-500 uppercase font-bold mb-2">Change Log</p>
                  <div className="space-y-2">
                    {auditLog.map(entry => (
                      <div key={entry.id} className="bg-gray-800/50 border border-gray-700 rounded-lg px-3 py-2 text-xs">
                        <div className="flex items-center gap-2 text-gray-400 mb-1">
                          <Clock size={10} />
                          <span>{format(new Date(entry.created_at), 'PPpp')}</span>
                          {entry.event_data?.reviewed_by && (
                            <>
                              <User size={10} className="ml-1" />
                              <span>{entry.event_data.reviewed_by}</span>
                            </>
                          )}
                          {entry.event_data?.updated_by && (
                            <>
                              <User size={10} className="ml-1" />
                              <span>{entry.event_data.updated_by}</span>
                            </>
                          )}
                          {entry.event_data?.user_id && !entry.event_data?.reviewed_by && !entry.event_data?.updated_by && (
                            <>
                              <User size={10} className="ml-1" />
                              <span>{entry.event_data.display_name || entry.event_data.username || 'User'}</span>
                            </>
                          )}
                        </div>
                        <span className="text-gray-300">{formatEventType(entry.event_type)}</span>
                        {entry.event_type === 'queue_review' && entry.event_data && (
                          <span className="ml-2 text-gray-500">
                            {entry.event_data.old_status} &rarr; {entry.event_data.new_status}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Keyboard shortcuts help — desktop only */}
              <div className="hidden md:flex mt-6 text-[10px] text-gray-600 items-center gap-4">
                <span><kbd className="px-1.5 py-0.5 bg-gray-800 border border-gray-700 rounded text-gray-500">&#8592;</kbd> / <kbd className="px-1.5 py-0.5 bg-gray-800 border border-gray-700 rounded text-gray-500">&#8594;</kbd> Navigate</span>
                <span><kbd className="px-1.5 py-0.5 bg-gray-800 border border-gray-700 rounded text-gray-500">R</kbd> Review</span>
                <span><kbd className="px-1.5 py-0.5 bg-gray-800 border border-gray-700 rounded text-gray-500">F</kbd> Flag</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TagFilterDropdown({ availableTags, tagCounts, selected, onSelect, onClose, inputRef }) {
  const [filter, setFilter] = useState('');
  const ref = useRef(null);

  useEffect(() => {
    inputRef?.current?.focus();
  }, [inputRef]);

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onClose();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  const countMap = {};
  (tagCounts || []).forEach(tc => { countMap[tc.tag] = tc.count; });

  const sorted = [...availableTags].sort((a, b) => (countMap[b] || 0) - (countMap[a] || 0));
  const filtered = filter.trim()
    ? sorted.filter(t => t.toLowerCase().includes(filter.toLowerCase()))
    : sorted;

  return (
    <div ref={ref} className="absolute top-full left-0 mt-1 w-64 bg-gray-800 border border-gray-600 rounded-lg shadow-2xl z-50 overflow-hidden">
      <div className="p-2 border-b border-gray-700">
        <input
          ref={inputRef}
          type="text"
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="Search tags..."
          className="w-full px-2 py-1.5 bg-gray-900 border border-gray-700 rounded text-xs text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
        />
      </div>
      <div className="max-h-48 overflow-y-auto">
        <button
          onClick={() => onSelect('')}
          className={`w-full text-left px-3 py-2 text-xs transition ${
            !selected ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-700'
          }`}
        >
          All tags
        </button>
        {filtered.map(tag => (
          <button
            key={tag}
            onClick={() => onSelect(tag)}
            className={`w-full text-left px-3 py-2 text-xs transition flex justify-between ${
              selected === tag ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-700'
            }`}
          >
            <span>{tag}</span>
            {countMap[tag] && <span className="text-gray-500">{countMap[tag]}</span>}
          </button>
        ))}
      </div>
    </div>
  );
}

function formatEventType(type) {
  const labels = {
    'upload': 'Uploaded',
    'bulk_upload': 'Bulk uploaded',
    'annotation_update': 'Annotations updated',
    'web_annotation_update': 'Annotations updated (web)',
    'queue_review': 'Review status changed',
    'video_deleted': 'Deleted',
    'device_register': 'Device registered',
  };
  return labels[type] || type.replace(/_/g, ' ');
}

function MetaCard({ label, value, mono }) {
  return (
    <div className="bg-gray-800/50 p-3 rounded-lg border border-gray-700">
      <p className="text-[10px] text-gray-500 uppercase font-bold mb-1">{label}</p>
      <p className={`text-sm text-gray-300 ${mono ? 'font-mono break-all' : ''}`}>{value}</p>
    </div>
  );
}
