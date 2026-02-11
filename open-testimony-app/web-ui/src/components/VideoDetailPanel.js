import React, { useState, useEffect, useCallback, useRef } from 'react';
import { format } from 'date-fns';
import { Video, Trash2, Save, Clock, User } from 'lucide-react';
import api from '../api';
import { useAuth } from '../auth';
import VerificationBadge from './VerificationBadge';
import SourceBadge from './SourceBadge';
import MediaTypeBadge from './MediaTypeBadge';
import TagInput from './TagInput';

const CATEGORIES = ['', 'interview', 'incident', 'documentation', 'other'];

export default function VideoDetailPanel({ video, onVideoDeleted, onVideoUpdated, initialTimestampMs, availableTags: availableTagsProp }) {
  const { user } = useAuth();
  const [detail, setDetail] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [auditLog, setAuditLog] = useState([]);
  const videoRef = useRef(null);

  // Editable fields
  const [category, setCategory] = useState('');
  const [locationDescription, setLocationDescription] = useState('');
  const [notes, setNotes] = useState('');
  const [tags, setTags] = useState([]);
  const [localAvailableTags, setLocalAvailableTags] = useState([]);
  const availableTags = (availableTagsProp && availableTagsProp.length > 0) ? availableTagsProp : localAvailableTags;

  const canEdit = user?.role === 'admin' || user?.role === 'staff';

  const syncFields = useCallback((d) => {
    setCategory(d.category || '');
    setLocationDescription(d.location_description || '');
    setNotes(d.notes || '');
    setTags(d.incident_tags || []);
  }, []);

  useEffect(() => {
    if (!video) return;
    setDetail(null);
    setVideoUrl(null);
    setAuditLog([]);
    setSaveError('');

    api.get(`/videos/${video.id}`).then(res => {
      setDetail(res.data);
      syncFields(res.data);
    }).catch(() => {});
    api.get(`/videos/${video.id}/url`).then(res => setVideoUrl(res.data.url)).catch(() => {});
    api.get(`/videos/${video.id}/audit`).then(res => setAuditLog(res.data.entries || [])).catch(() => {});
  }, [video?.id, syncFields]);

  useEffect(() => {
    if (!availableTagsProp || availableTagsProp.length === 0) {
      api.get('/tags').then(res => setLocalAvailableTags(res.data.all_tags || [])).catch(() => {});
    }
  }, [availableTagsProp]);

  // Seek to initialTimestampMs when the video is ready
  useEffect(() => {
    if (initialTimestampMs != null && videoRef.current) {
      const seekSec = initialTimestampMs / 1000;
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
    }
  }, [initialTimestampMs, videoUrl]);

  if (!video) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-8 bg-gray-900">
        <Video size={64} className="text-gray-700 mb-4" />
        <p className="text-gray-500">Select a video from the list to view details</p>
      </div>
    );
  }

  const d = detail || video;

  // Check if any editable field has changed
  const hasChanges = detail && (
    category !== (detail.category || '') ||
    locationDescription !== (detail.location_description || '') ||
    notes !== (detail.notes || '') ||
    JSON.stringify(tags) !== JSON.stringify(detail.incident_tags || [])
  );

  const handleSave = async () => {
    setSaving(true);
    setSaveError('');
    try {
      await api.put(`/videos/${video.id}/annotations/web`, {
        category,
        location_description: locationDescription,
        notes,
        incident_tags: tags,
      });
      const updated = {
        category: category || null,
        location_description: locationDescription || null,
        notes: notes || null,
        incident_tags: tags,
        annotations_updated_at: new Date().toISOString(),
      };
      setDetail(prev => ({ ...prev, ...updated }));
      onVideoUpdated?.(video.id);
      // Refresh audit log
      api.get(`/videos/${video.id}/audit`).then(res => setAuditLog(res.data.entries || [])).catch(() => {});
    } catch (err) {
      setSaveError(err.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Are you sure you want to delete this video? This action is logged.')) return;
    setDeleting(true);
    try {
      await api.delete(`/videos/${video.id}`);
      onVideoDeleted?.(video.id);
    } catch (err) {
      alert(err.response?.data?.detail || 'Delete failed');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto bg-gray-900 p-6">
      <div className="max-w-4xl mx-auto">
        {/* Video player */}
        <div className="aspect-video bg-black rounded-xl overflow-hidden mb-6">
          {videoUrl ? (
            d.media_type === 'photo' ? (
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

        {/* Header with badges and delete */}
        <div className="flex justify-between items-start mb-6">
          <div>
            <h2 className="text-xl font-bold text-white mb-2">
              {d.media_type === 'photo' ? 'Photo' : 'Video'} Testimony
            </h2>
            <div className="flex items-center gap-2 flex-wrap">
              <VerificationBadge status={d.verification_status} />
              <SourceBadge source={d.source} />
              <MediaTypeBadge mediaType={d.media_type} />
            </div>
          </div>
          {user?.role === 'admin' && (
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="flex items-center gap-1 px-3 py-1.5 bg-red-600 hover:bg-red-500 disabled:bg-red-800 text-white text-sm rounded-lg transition shrink-0"
            >
              <Trash2 size={14} />
              {deleting ? 'Deleting...' : 'Delete'}
            </button>
          )}
        </div>

        {/* Editable annotations — always visible for staff/admin */}
        {canEdit && detail && (
          <div className="mb-6 space-y-3">
            {saveError && (
              <div className="p-3 bg-red-900/30 border border-red-500/50 rounded-lg text-sm text-red-400">{saveError}</div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] text-gray-500 uppercase font-bold mb-1">Category</label>
                <select
                  value={category}
                  onChange={e => setCategory(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500"
                >
                  {CATEGORIES.map(c => (
                    <option key={c} value={c}>{c || '(none)'}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[10px] text-gray-500 uppercase font-bold mb-1">Location Description</label>
                <input
                  type="text"
                  value={locationDescription}
                  onChange={e => setLocationDescription(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500"
                  placeholder="e.g. Downtown near City Hall"
                />
              </div>
            </div>

            <div>
              <label className="block text-[10px] text-gray-500 uppercase font-bold mb-1">Notes</label>
              <textarea
                value={notes}
                onChange={e => setNotes(e.target.value)}
                rows={2}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500 resize-none"
                placeholder="Additional context or notes..."
              />
            </div>

            <div>
              <label className="block text-[10px] text-gray-500 uppercase font-bold mb-1">Incident Tags</label>
              <TagInput
                tags={tags}
                onChange={setTags}
                availableTags={availableTags}
                placeholder="e.g. protest, arrest, traffic-stop"
              />
            </div>

            {hasChanges && (
              <div className="flex justify-end">
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-white text-sm font-medium rounded-lg transition"
                >
                  <Save size={14} />
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Read-only annotations for non-editors */}
        {!canEdit && (
          <div className="mb-6">
            {d.incident_tags?.length > 0 && (
              <div className="mb-4">
                <p className="text-[10px] text-gray-500 uppercase font-bold mb-2">Incident Tags</p>
                <div className="flex flex-wrap gap-2">
                  {d.incident_tags.map(tag => (
                    <span key={tag} className="px-3 py-1 bg-blue-900/20 border border-blue-500/30 rounded-full text-xs text-blue-300">
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {detail?.category && <MetaCard label="Category" value={detail.category} />}
            {detail?.location_description && <MetaCard label="Location Description" value={detail.location_description} />}
            {detail?.notes && <MetaCard label="Notes" value={detail.notes} />}
          </div>
        )}

        {/* Technical metadata */}
        <div className="grid grid-cols-2 gap-3 mb-6">
          <MetaCard label="Timestamp" value={format(new Date(d.timestamp), 'PPpp')} />
          <MetaCard label="Uploaded At" value={format(new Date(d.uploaded_at), 'PPpp')} />
          <MetaCard label="Device ID" value={d.device_id} mono />
          <MetaCard label="Location" value={`${d.location?.lat?.toFixed(5)}, ${d.location?.lon?.toFixed(5)}`} />
          {detail?.file_hash && <MetaCard label="File Hash (SHA-256)" value={detail.file_hash} mono span2 />}
        </div>

        {/* EXIF metadata */}
        {detail?.exif_metadata && Object.keys(detail.exif_metadata).length > 0 && (
          <div className="mb-6">
            <p className="text-[10px] text-gray-500 uppercase font-bold mb-2">EXIF Metadata</p>
            <div className="bg-gray-800 rounded-lg border border-gray-700 p-4 text-sm font-mono text-gray-300">
              {Object.entries(detail.exif_metadata).map(([k, v]) => (
                <div key={k} className="flex gap-2 mb-1">
                  <span className="text-gray-500 shrink-0">{k}:</span>
                  <span className="truncate">{String(v)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

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
                    {entry.event_data?.user_id && (
                      <>
                        <User size={10} className="ml-1" />
                        <span>{entry.event_data.display_name || entry.event_data.username || 'System'}</span>
                      </>
                    )}
                  </div>
                  <span className="text-gray-300">{formatEventType(entry.event_type)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function formatEventType(type) {
  const labels = {
    'video_uploaded': 'Video uploaded',
    'video_verified': 'Signature verified',
    'video_verification_failed': 'Verification failed',
    'annotations_updated': 'Annotations updated',
    'annotations_updated_web': 'Annotations updated (web)',
    'video_deleted': 'Video deleted',
  };
  return labels[type] || type.replace(/_/g, ' ');
}

function MetaCard({ label, value, mono, span2 }) {
  return (
    <div className={`bg-gray-800/50 p-3 rounded-lg border border-gray-700 ${span2 ? 'col-span-2' : ''}`}>
      <p className="text-[10px] text-gray-500 uppercase font-bold mb-1">{label}</p>
      <p className={`text-sm text-gray-300 ${mono ? 'font-mono break-all' : ''}`}>{value}</p>
    </div>
  );
}
