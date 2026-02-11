import React, { useState, useEffect } from 'react';
import { X, Save } from 'lucide-react';
import api from '../api';
import TagInput from './TagInput';
import AddressAutocomplete from './AddressAutocomplete';

const CATEGORIES = ['', 'interview', 'incident', 'documentation', 'other'];

export default function EditAnnotations({ video, onSaved, onCancel }) {
  const [category, setCategory] = useState(video.category || '');
  const [locationDescription, setLocationDescription] = useState(video.location_description || '');
  const [geocodedLocation, setGeocodedLocation] = useState(null);
  const [notes, setNotes] = useState(video.notes || '');
  const [tags, setTags] = useState(video.incident_tags || []);
  const [availableTags, setAvailableTags] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/tags').then(res => setAvailableTags(res.data.all_tags || [])).catch(() => {});
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      const payload = {
        category,
        location_description: locationDescription,
        notes,
        incident_tags: tags,
      };
      if (geocodedLocation) {
        payload.latitude = geocodedLocation.lat;
        payload.longitude = geocodedLocation.lon;
      }
      await api.put(`/videos/${video.id}/annotations/web`, payload);
      const result = {
        category: category || null,
        location_description: locationDescription || null,
        notes: notes || null,
        incident_tags: tags,
        annotations_updated_at: new Date().toISOString(),
      };
      if (geocodedLocation) {
        result.location = { lat: geocodedLocation.lat, lon: geocodedLocation.lon };
      }
      onSaved(result);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-sm font-bold text-gray-300 uppercase tracking-wider">Edit Annotations</h3>
        <button onClick={onCancel} className="text-gray-500 hover:text-white">
          <X size={18} />
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-900/30 border border-red-500/50 rounded-lg text-sm text-red-400">{error}</div>
      )}

      <div className="space-y-4">
        <div>
          <label className="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-1.5">Category</label>
          <select
            value={category}
            onChange={e => setCategory(e.target.value)}
            className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
          >
            {CATEGORIES.map(c => (
              <option key={c} value={c}>{c || '(none)'}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-1.5">Location Description</label>
          <AddressAutocomplete
            value={locationDescription}
            onChange={setLocationDescription}
            onLocationSelect={(loc) => setGeocodedLocation({ lat: loc.lat, lon: loc.lon })}
            placeholder="Search address or type location..."
          />
          {geocodedLocation && (
            <p className="mt-1 text-[10px] text-green-400">
              Coordinates: {geocodedLocation.lat.toFixed(5)}, {geocodedLocation.lon.toFixed(5)}
            </p>
          )}
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-1.5">Notes</label>
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            rows={3}
            className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 resize-none"
            placeholder="Additional context or notes..."
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-1.5">Incident Tags</label>
          <TagInput
            tags={tags}
            onChange={setTags}
            availableTags={availableTags}
            placeholder="e.g. protest, arrest, traffic-stop"
          />
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-gray-400 hover:text-white text-sm rounded-lg transition"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-white text-sm font-medium rounded-lg transition"
          >
            <Save size={14} />
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
