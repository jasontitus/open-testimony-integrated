import React, { useState, useEffect, useCallback } from 'react';
import { format } from 'date-fns';
import { UserPlus, Key, Shield, AlertCircle, Tag, Trash2, RefreshCw, Database, Upload, CheckCircle, XCircle, FileVideo, Image, Plus, ScrollText, Download, ChevronDown, ChevronRight, Filter } from 'lucide-react';
import axios from 'axios';
import api from '../api';

const aiApi = axios.create({ baseURL: '/ai-search', withCredentials: true });

export default function AdminPanel() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const fetchUsers = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.get('/auth/users');
      setUsers(res.data.users);
    } catch (err) {
      console.error('Failed to load users:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  return (
    <div className="flex-1 overflow-y-auto p-6 bg-gray-900">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <div className="flex items-center gap-2">
            <Shield size={20} className="text-red-400" />
            <h2 className="text-xl font-bold text-white">User Management</h2>
          </div>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition"
          >
            <UserPlus size={16} />
            {showCreate ? 'Cancel' : 'Create User'}
          </button>
        </div>

        {showCreate && (
          <CreateUserForm onCreated={() => { setShowCreate(false); fetchUsers(); }} />
        )}

        {loading ? (
          <div className="flex justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          </div>
        ) : (
          <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-700">
                  <th className="text-left px-4 py-3 text-[10px] text-gray-500 uppercase font-bold tracking-wider">Username</th>
                  <th className="text-left px-4 py-3 text-[10px] text-gray-500 uppercase font-bold tracking-wider">Display Name</th>
                  <th className="text-left px-4 py-3 text-[10px] text-gray-500 uppercase font-bold tracking-wider">Role</th>
                  <th className="text-left px-4 py-3 text-[10px] text-gray-500 uppercase font-bold tracking-wider">Status</th>
                  <th className="text-left px-4 py-3 text-[10px] text-gray-500 uppercase font-bold tracking-wider">Last Login</th>
                  <th className="text-left px-4 py-3 text-[10px] text-gray-500 uppercase font-bold tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <UserRow key={u.id} user={u} onUpdated={fetchUsers} />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Bulk Upload */}
        <BulkUpload />

        {/* Tag Management */}
        <TagManagement />

        {/* Indexing Management */}
        <IndexingManagement />

        {/* Audit Log */}
        <AuditLogViewer />
      </div>
    </div>
  );
}

function UserRow({ user, onUpdated }) {
  const [resettingPassword, setResettingPassword] = useState(false);
  const [newPassword, setNewPassword] = useState('');

  const toggleActive = async () => {
    try {
      await api.put(`/auth/users/${user.id}`, { is_active: !user.is_active });
      onUpdated();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to update');
    }
  };

  const toggleRole = async () => {
    const newRole = user.role === 'admin' ? 'staff' : 'admin';
    try {
      await api.put(`/auth/users/${user.id}`, { role: newRole });
      onUpdated();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to update');
    }
  };

  const resetPassword = async () => {
    if (!newPassword) return;
    try {
      await api.put(`/auth/users/${user.id}/password`, { password: newPassword });
      setResettingPassword(false);
      setNewPassword('');
      alert('Password reset successfully');
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to reset password');
    }
  };

  const roleBadgeClass = user.role === 'admin'
    ? 'bg-red-900/30 border-red-500/50 text-red-400'
    : 'bg-blue-900/30 border-blue-500/50 text-blue-400';

  return (
    <>
      <tr className="border-b border-gray-700/50 hover:bg-gray-750">
        <td className="px-4 py-3 text-sm font-mono text-blue-400">{user.username}</td>
        <td className="px-4 py-3 text-sm text-gray-300">{user.display_name}</td>
        <td className="px-4 py-3">
          <button onClick={toggleRole} className={`px-1.5 py-0.5 border rounded text-[10px] font-bold uppercase tracking-wider cursor-pointer hover:opacity-80 ${roleBadgeClass}`}>
            {user.role}
          </button>
        </td>
        <td className="px-4 py-3">
          <button
            onClick={toggleActive}
            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider cursor-pointer ${
              user.is_active
                ? 'bg-green-900/30 text-green-400 border border-green-500/50'
                : 'bg-gray-700 text-gray-500 border border-gray-600'
            }`}
          >
            {user.is_active ? 'Active' : 'Disabled'}
          </button>
        </td>
        <td className="px-4 py-3 text-xs text-gray-500">
          {user.last_login_at ? format(new Date(user.last_login_at), 'MMM d, HH:mm') : 'Never'}
        </td>
        <td className="px-4 py-3">
          <button
            onClick={() => setResettingPassword(!resettingPassword)}
            className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition"
          >
            <Key size={12} />
            Reset Password
          </button>
        </td>
      </tr>
      {resettingPassword && (
        <tr className="border-b border-gray-700/50">
          <td colSpan={6} className="px-4 py-3">
            <div className="flex items-center gap-2 max-w-md">
              <input
                type="password"
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                placeholder="New password"
                className="flex-1 px-3 py-1.5 bg-gray-900 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:border-blue-500"
              />
              <button
                onClick={resetPassword}
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg"
              >
                Save
              </button>
              <button
                onClick={() => { setResettingPassword(false); setNewPassword(''); }}
                className="px-3 py-1.5 text-gray-400 hover:text-white text-sm"
              >
                Cancel
              </button>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function CreateUserForm({ onCreated }) {
  const [username, setUsername] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('staff');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      await api.post('/auth/users', { username, display_name: displayName || username, password, role });
      onCreated();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create user');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-gray-800 rounded-xl border border-gray-700 p-5 mb-6">
      <h3 className="text-sm font-bold text-gray-300 uppercase tracking-wider mb-4">Create New User</h3>

      {error && (
        <div className="mb-4 p-3 bg-red-900/30 border border-red-500/50 rounded-lg flex items-center gap-2 text-sm text-red-400">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-1.5">Username</label>
          <input
            type="text"
            value={username}
            onChange={e => setUsername(e.target.value)}
            required
            className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-1.5">Display Name</label>
          <input
            type="text"
            value={displayName}
            onChange={e => setDisplayName(e.target.value)}
            className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
            placeholder="(defaults to username)"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-1.5">Password</label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-400 uppercase tracking-wider mb-1.5">Role</label>
          <select
            value={role}
            onChange={e => setRole(e.target.value)}
            className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
          >
            <option value="staff">Staff</option>
            <option value="admin">Admin</option>
          </select>
        </div>
      </div>

      <div className="flex justify-end mt-4">
        <button
          type="submit"
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-white text-sm font-medium rounded-lg transition"
        >
          <UserPlus size={14} />
          {saving ? 'Creating...' : 'Create User'}
        </button>
      </div>
    </form>
  );
}

function BulkUpload() {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState(null);

  const fileInputRef = React.useRef(null);

  const handleFilesSelected = (e) => {
    const selected = Array.from(e.target.files || []);
    setFiles(selected);
    setResults(null);
  };

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    setUploading(true);
    setProgress(0);
    setResults(null);

    const allResults = [];
    let succeeded = 0;
    let failed = 0;

    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      const formData = new FormData();
      formData.append('files', f);

      try {
        const res = await api.post('/bulk-upload', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        const fileResult = res.data.results?.[0] || { filename: f.name, status: 'success' };
        allResults.push(fileResult);
        succeeded++;
      } catch (err) {
        allResults.push({ filename: f.name, status: 'error', detail: err.response?.data?.detail || err.message });
        failed++;
      }

      setProgress(Math.round(((i + 1) / files.length) * 100));
    }

    setResults({
      status: failed === 0 ? 'success' : succeeded === 0 ? 'error' : 'partial',
      total: files.length,
      succeeded,
      failed,
      results: allResults,
    });
    setFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = '';
    setUploading(false);
  };

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);
  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  };

  return (
    <div className="mt-8">
      <div className="flex items-center gap-2 mb-4">
        <Upload size={20} className="text-green-400" />
        <h2 className="text-xl font-bold text-white">Bulk Upload</h2>
        <span className="text-xs text-gray-500 ml-2">Videos &amp; Photos</span>
      </div>

      <div className="bg-gray-800 rounded-xl border border-gray-700 p-5">
        {/* Drop zone / file picker */}
        <div
          className="border-2 border-dashed border-gray-600 rounded-lg p-8 text-center cursor-pointer hover:border-green-500/50 transition"
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const dropped = Array.from(e.dataTransfer.files);
            setFiles(prev => [...prev, ...dropped]);
            setResults(null);
          }}
        >
          <Upload size={32} className="mx-auto text-gray-500 mb-3" />
          <p className="text-sm text-gray-400">Click or drag files here to add videos and photos</p>
          <p className="text-xs text-gray-600 mt-1">All uploads will be marked as unverified. EXIF data will be imported when available.</p>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="video/*,image/*"
            onChange={handleFilesSelected}
            className="hidden"
          />
        </div>

        {/* File list */}
        {files.length > 0 && (
          <div className="mt-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-gray-400">{files.length} file{files.length !== 1 ? 's' : ''} selected ({formatSize(totalSize)})</span>
              <button
                onClick={() => { setFiles([]); if (fileInputRef.current) fileInputRef.current.value = ''; }}
                className="text-xs text-gray-500 hover:text-white transition"
              >
                Clear all
              </button>
            </div>
            <div className="max-h-48 overflow-y-auto space-y-1">
              {files.map((f, i) => (
                <div key={i} className="flex items-center gap-2 px-3 py-1.5 bg-gray-900 rounded-lg text-sm">
                  {f.type.startsWith('video/') ? (
                    <FileVideo size={14} className="text-blue-400 flex-shrink-0" />
                  ) : (
                    <Image size={14} className="text-green-400 flex-shrink-0" />
                  )}
                  <span className="text-gray-300 truncate flex-1">{f.name}</span>
                  <span className="text-xs text-gray-600 flex-shrink-0">{formatSize(f.size)}</span>
                  <button onClick={() => removeFile(i)} className="text-gray-600 hover:text-red-400 transition flex-shrink-0">
                    <XCircle size={14} />
                  </button>
                </div>
              ))}
            </div>

            {/* Upload button */}
            <div className="flex items-center gap-3 mt-4">
              <button
                onClick={handleUpload}
                disabled={uploading || files.length === 0}
                className="flex items-center gap-1.5 px-5 py-2 bg-green-600 hover:bg-green-500 disabled:bg-green-800 text-white text-sm font-medium rounded-lg transition"
              >
                <Upload size={14} />
                {uploading ? 'Uploading...' : `Upload ${files.length} File${files.length !== 1 ? 's' : ''}`}
              </button>

              {uploading && (
                <div className="flex-1">
                  <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-green-500 rounded-full transition-all duration-300"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  <span className="text-xs text-gray-500 mt-1">{progress}%</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Results */}
        {results && (
          <div className="mt-4">
            <div className={`p-3 rounded-lg flex items-center gap-2 text-sm mb-3 ${
              results.status === 'success'
                ? 'bg-green-900/30 border border-green-500/50 text-green-400'
                : results.status === 'partial'
                ? 'bg-yellow-900/30 border border-yellow-500/50 text-yellow-400'
                : 'bg-red-900/30 border border-red-500/50 text-red-400'
            }`}>
              {results.status === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
              {results.succeeded} of {results.total} file{results.total !== 1 ? 's' : ''} uploaded successfully
              {results.failed > 0 && `, ${results.failed} failed`}
            </div>

            <div className="max-h-48 overflow-y-auto space-y-1">
              {results.results.map((r, i) => (
                <div key={i} className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm ${
                  r.status === 'success' ? 'bg-green-900/10' : 'bg-red-900/10'
                }`}>
                  {r.status === 'success' ? (
                    <CheckCircle size={14} className="text-green-400 flex-shrink-0" />
                  ) : (
                    <XCircle size={14} className="text-red-400 flex-shrink-0" />
                  )}
                  <span className="text-gray-300 truncate flex-1">{r.filename}</span>
                  {r.status === 'success' ? (
                    <span className="text-xs text-gray-500 flex-shrink-0">
                      {r.media_type} {r.has_exif ? '· EXIF' : ''} · unverified
                    </span>
                  ) : (
                    <span className="text-xs text-red-400 flex-shrink-0 truncate max-w-[200px]">{r.detail}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <p className="text-[10px] text-gray-600 mt-3">
          Bulk uploaded files are marked as unverified. EXIF metadata (GPS location, timestamp) is extracted automatically. All files are queued for AI indexing.
        </p>
      </div>
    </div>
  );
}

function TagManagement() {
  const [allTags, setAllTags] = useState([]);
  const [defaultTags, setDefaultTags] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(null);
  const [adding, setAdding] = useState(false);
  const [newTag, setNewTag] = useState('');

  const fetchTags = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.get('/tags');
      setAllTags(res.data.all_tags || []);
      setDefaultTags(res.data.default_tags || []);
    } catch (err) {
      console.error('Failed to load tags:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchTags(); }, [fetchTags]);

  const handleDelete = async (tag) => {
    if (!window.confirm(`Delete tag "${tag}" from all videos?`)) return;
    setDeleting(tag);
    try {
      await api.delete('/tags', { data: { tag } });
      fetchTags();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to delete tag');
    } finally {
      setDeleting(null);
    }
  };

  const handleAddTag = async () => {
    const tag = newTag.trim().toLowerCase();
    if (!tag) return;
    try {
      await api.post('/tags', { tag });
      setNewTag('');
      setAdding(false);
      fetchTags();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create tag');
    }
  };

  const isDefault = (tag) => defaultTags.includes(tag);

  return (
    <div className="mt-8">
      <div className="flex items-center gap-2 mb-4">
        <Tag size={20} className="text-blue-400" />
        <h2 className="text-xl font-bold text-white">Tag Management</h2>
        <span className="text-xs text-gray-500 ml-2">({allTags.length} tags)</span>
      </div>

      {loading ? (
        <div className="flex justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      ) : allTags.length === 0 ? (
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 text-center text-gray-500">
          No tags in use yet
        </div>
      ) : (
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-4">
          <div className="flex flex-wrap gap-2">
            {allTags.map(tag => (
              <span
                key={tag}
                className={`group flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs border ${
                  isDefault(tag)
                    ? 'bg-blue-900/20 border-blue-500/30 text-blue-300'
                    : 'bg-gray-700/50 border-gray-600 text-gray-300'
                }`}
              >
                {tag}
                {isDefault(tag) && (
                  <span className="text-[9px] text-blue-500/60 uppercase font-bold">default</span>
                )}
                <button
                  onClick={() => handleDelete(tag)}
                  disabled={deleting === tag}
                  className="opacity-0 group-hover:opacity-100 ml-0.5 text-red-400 hover:text-red-300 transition-opacity"
                  title={`Remove "${tag}" from all videos`}
                >
                  {deleting === tag ? (
                    <div className="animate-spin rounded-full h-3 w-3 border-b border-red-400"></div>
                  ) : (
                    <Trash2 size={10} />
                  )}
                </button>
              </span>
            ))}
            {adding ? (
              <span className="flex items-center gap-1 px-2 py-1 rounded-full border border-green-500/50 bg-green-900/20">
                <input
                  autoFocus
                  value={newTag}
                  onChange={(e) => setNewTag(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleAddTag();
                    if (e.key === 'Escape') { setAdding(false); setNewTag(''); }
                  }}
                  placeholder="new tag"
                  className="bg-transparent text-xs text-white outline-none w-24"
                />
                <button onClick={handleAddTag} className="text-green-400 hover:text-green-300">
                  <CheckCircle size={12} />
                </button>
                <button onClick={() => { setAdding(false); setNewTag(''); }} className="text-gray-500 hover:text-gray-300">
                  <XCircle size={12} />
                </button>
              </span>
            ) : (
              <button
                onClick={() => setAdding(true)}
                className="flex items-center gap-1 px-3 py-1.5 rounded-full text-xs border border-dashed border-gray-600 text-gray-500 hover:border-green-500/50 hover:text-green-400 transition"
              >
                <Plus size={12} />
                Add tag
              </button>
            )}
          </div>
          <p className="text-[10px] text-gray-600 mt-3">
            Hover over a tag and click the trash icon to remove it from all videos. Default tags will remain in the autocomplete list.
          </p>
        </div>
      )}
    </div>
  );
}

function IndexingManagement() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [reindexing, setReindexing] = useState(false);
  const [message, setMessage] = useState(null);

  const fetchStats = useCallback(async () => {
    try {
      const res = await aiApi.get('/indexing/status');
      setStats(res.data);
    } catch (err) {
      console.error('Failed to load indexing stats:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 5000);
    return () => clearInterval(interval);
  }, [fetchStats]);

  const handleReindexAll = async () => {
    if (!window.confirm('Re-index all videos? This will clear existing embeddings and re-process everything.')) return;
    setReindexing(true);
    setMessage(null);
    try {
      const res = await aiApi.post('/indexing/reindex-all');
      setMessage({ type: 'success', text: `Queued ${res.data.count} videos for re-indexing` });
      fetchStats();
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to trigger reindex' });
    } finally {
      setReindexing(false);
    }
  };

  const statusItems = stats ? [
    { label: 'Completed', value: stats.completed ?? 0, color: 'text-green-400' },
    { label: 'Processing', value: stats.processing ?? 0, color: 'text-yellow-400' },
    { label: 'Pending', value: stats.pending ?? 0, color: 'text-blue-400' },
    { label: 'Failed', value: stats.failed ?? 0, color: 'text-red-400' },
  ] : [];

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Database size={20} className="text-purple-400" />
          <h2 className="text-xl font-bold text-white">AI Indexing</h2>
        </div>
        <button
          onClick={handleReindexAll}
          disabled={reindexing}
          className="flex items-center gap-1.5 px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-purple-800 text-white text-sm font-medium rounded-lg transition"
        >
          <RefreshCw size={14} className={reindexing ? 'animate-spin' : ''} />
          {reindexing ? 'Queuing...' : 'Re-index All Videos'}
        </button>
      </div>

      {message && (
        <div className={`mb-4 p-3 rounded-lg flex items-center gap-2 text-sm ${
          message.type === 'success'
            ? 'bg-green-900/30 border border-green-500/50 text-green-400'
            : 'bg-red-900/30 border border-red-500/50 text-red-400'
        }`}>
          {message.type === 'error' && <AlertCircle size={16} />}
          {message.text}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500"></div>
        </div>
      ) : stats ? (
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-4">
          <div className="grid grid-cols-4 gap-4">
            {statusItems.map(s => (
              <div key={s.label} className="text-center">
                <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
                <div className="text-xs text-gray-500 uppercase tracking-wider mt-1">{s.label}</div>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-gray-600 mt-3">
            The bridge service polls for pending jobs every 10 seconds. Re-indexing clears all embeddings and re-queues every video.
          </p>
        </div>
      ) : (
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 text-center text-gray-500">
          Could not load indexing status
        </div>
      )}
    </div>
  );
}

const EVENT_TYPES = [
  'upload', 'bulk_upload', 'device_register', 'annotation_update',
  'web_annotation_update', 'video_deleted', 'tag_deleted',
  'user_created', 'user_updated', 'password_reset',
];

const EVENT_BADGE_COLORS = {
  upload: 'bg-green-900/30 border-green-500/50 text-green-400',
  bulk_upload: 'bg-green-900/30 border-green-500/50 text-green-400',
  device_register: 'bg-purple-900/30 border-purple-500/50 text-purple-400',
  annotation_update: 'bg-blue-900/30 border-blue-500/50 text-blue-400',
  web_annotation_update: 'bg-blue-900/30 border-blue-500/50 text-blue-400',
  video_deleted: 'bg-red-900/30 border-red-500/50 text-red-400',
  tag_deleted: 'bg-red-900/30 border-red-500/50 text-red-400',
  user_created: 'bg-amber-900/30 border-amber-500/50 text-amber-400',
  user_updated: 'bg-amber-900/30 border-amber-500/50 text-amber-400',
  password_reset: 'bg-amber-900/30 border-amber-500/50 text-amber-400',
};

const PAGE_SIZE = 25;

function AuditLogViewer() {
  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [eventFilter, setEventFilter] = useState('');
  const [expandedId, setExpandedId] = useState(null);

  const [chainStatus, setChainStatus] = useState(null);
  const [chainLoading, setChainLoading] = useState(true);

  const [exporting, setExporting] = useState(false);

  const fetchEntries = useCallback(async () => {
    try {
      setLoading(true);
      const params = { limit: PAGE_SIZE, offset };
      if (eventFilter) params.event_type = eventFilter;
      const res = await api.get('/audit-log', { params });
      setEntries(res.data.entries);
      setTotal(res.data.total);
    } catch (err) {
      console.error('Failed to load audit log:', err);
    } finally {
      setLoading(false);
    }
  }, [offset, eventFilter]);

  const fetchChainStatus = useCallback(async () => {
    try {
      setChainLoading(true);
      const res = await api.get('/audit-log/verify');
      setChainStatus(res.data);
    } catch (err) {
      console.error('Failed to verify chain:', err);
    } finally {
      setChainLoading(false);
    }
  }, []);

  useEffect(() => { fetchChainStatus(); }, [fetchChainStatus]);
  useEffect(() => { fetchEntries(); }, [fetchEntries]);

  // Reset to page 1 when filter changes
  const handleFilterChange = (val) => {
    setEventFilter(val);
    setOffset(0);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await api.get('/export/integrity-report');
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `integrity-report-${format(new Date(), 'yyyy-MM-dd')}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to generate integrity report');
    } finally {
      setExporting(false);
    }
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div className="mt-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <ScrollText size={20} className="text-cyan-400" />
          <h2 className="text-xl font-bold text-white">Audit Log</h2>
          {chainLoading ? (
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-cyan-500 ml-2"></div>
          ) : chainStatus ? (
            <span className={`ml-2 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${
              chainStatus.valid
                ? 'bg-green-900/30 border-green-500/50 text-green-400'
                : 'bg-red-900/30 border-red-500/50 text-red-400'
            }`}>
              {chainStatus.valid ? 'Chain Valid' : 'Chain Broken'}
            </span>
          ) : null}
          {chainStatus && (
            <span className="text-xs text-gray-500 ml-1">
              ({chainStatus.entries_checked} entries)
            </span>
          )}
        </div>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="flex items-center gap-1.5 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-cyan-800 text-white text-sm font-medium rounded-lg transition"
        >
          {exporting ? (
            <RefreshCw size={14} className="animate-spin" />
          ) : (
            <Download size={14} />
          )}
          {exporting ? 'Generating...' : 'Export Report'}
        </button>
      </div>

      {/* Filter row */}
      <div className="flex items-center gap-2 mb-3">
        <Filter size={14} className="text-gray-500" />
        <select
          value={eventFilter}
          onChange={(e) => handleFilterChange(e.target.value)}
          className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-300 focus:outline-none focus:border-cyan-500"
        >
          <option value="">All Events</option>
          {EVENT_TYPES.map(t => (
            <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
          ))}
        </select>
        <span className="text-xs text-gray-500">{total} total entries</span>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-500"></div>
        </div>
      ) : entries.length === 0 ? (
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-6 text-center text-gray-500">
          No audit log entries found
        </div>
      ) : (
        <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="w-8 px-2 py-3"></th>
                <th className="text-left px-3 py-3 text-[10px] text-gray-500 uppercase font-bold tracking-wider">Seq</th>
                <th className="text-left px-3 py-3 text-[10px] text-gray-500 uppercase font-bold tracking-wider">Timestamp</th>
                <th className="text-left px-3 py-3 text-[10px] text-gray-500 uppercase font-bold tracking-wider">Event Type</th>
                <th className="text-left px-3 py-3 text-[10px] text-gray-500 uppercase font-bold tracking-wider">Video ID</th>
                <th className="text-left px-3 py-3 text-[10px] text-gray-500 uppercase font-bold tracking-wider">User / Device</th>
                <th className="text-left px-3 py-3 text-[10px] text-gray-500 uppercase font-bold tracking-wider">Entry Hash</th>
              </tr>
            </thead>
            <tbody>
              {entries.map(e => (
                <React.Fragment key={e.id}>
                  <tr
                    className="border-b border-gray-700/50 hover:bg-gray-750 cursor-pointer"
                    onClick={() => setExpandedId(expandedId === e.id ? null : e.id)}
                  >
                    <td className="px-2 py-3 text-gray-500">
                      {expandedId === e.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </td>
                    <td className="px-3 py-3 text-sm font-mono text-gray-400">#{e.sequence_number}</td>
                    <td className="px-3 py-3 text-xs text-gray-400">
                      {format(new Date(e.created_at), 'MMM d, yyyy HH:mm:ss')}
                    </td>
                    <td className="px-3 py-3">
                      <span className={`px-1.5 py-0.5 border rounded text-[10px] font-bold uppercase tracking-wider ${
                        EVENT_BADGE_COLORS[e.event_type] || 'bg-gray-700 border-gray-600 text-gray-400'
                      }`}>
                        {e.event_type.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-xs font-mono text-blue-400">
                      {e.video_id ? e.video_id.substring(0, 8) + '...' : '-'}
                    </td>
                    <td className="px-3 py-3 text-xs text-gray-400 truncate max-w-[120px]">
                      {e.device_id || e.event_data?.user_id?.substring(0, 8) || '-'}
                    </td>
                    <td className="px-3 py-3 text-xs font-mono text-gray-600">
                      {e.entry_hash.substring(0, 12)}...
                    </td>
                  </tr>
                  {expandedId === e.id && (
                    <tr className="border-b border-gray-700/50">
                      <td colSpan={7} className="px-4 py-3 bg-gray-900/50">
                        <div className="text-[10px] text-gray-500 uppercase font-bold tracking-wider mb-1">Event Data</div>
                        <pre className="text-xs text-gray-300 bg-gray-900 rounded-lg p-3 overflow-x-auto max-h-64 overflow-y-auto">
                          {JSON.stringify(e.event_data, null, 2)}
                        </pre>
                        <div className="flex gap-4 mt-2 text-[10px] text-gray-600">
                          <span>Full hash: {e.entry_hash}</span>
                          <span>Previous: {e.previous_hash.substring(0, 16)}...</span>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-700">
              <button
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                disabled={offset === 0}
                className="px-3 py-1.5 text-sm text-gray-400 hover:text-white disabled:text-gray-700 disabled:cursor-not-allowed transition"
              >
                Previous
              </button>
              <span className="text-xs text-gray-500">
                Page {currentPage} of {totalPages}
              </span>
              <button
                onClick={() => setOffset(offset + PAGE_SIZE)}
                disabled={offset + PAGE_SIZE >= total}
                className="px-3 py-1.5 text-sm text-gray-400 hover:text-white disabled:text-gray-700 disabled:cursor-not-allowed transition"
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
