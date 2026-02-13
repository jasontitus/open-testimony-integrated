import React from 'react';
import { useAuth } from '../auth';
import { Map as MapIcon, List, LogOut, Users, Search, ClipboardList, ScanFace } from 'lucide-react';

export default function Header({ viewMode, setViewMode, showAdmin, onToggleAdmin, facesEnabled }) {
  const { user, logout } = useAuth();

  const roleBadgeClass = user?.role === 'admin'
    ? 'bg-red-900/30 border-red-500/50 text-red-400'
    : 'bg-blue-900/30 border-blue-500/50 text-blue-400';

  return (
    <header className="bg-gray-800 border-b border-gray-700 p-4 flex justify-between items-center shrink-0">
      <div className="flex items-center space-x-3">
        <img src="/app-logo.png" alt="Open Testimony Logo" className="w-10 h-10 object-contain" />
        <h1 className="hidden sm:block text-xl font-bold tracking-tight">Open Testimony</h1>
      </div>

      <div className="flex items-center gap-3">
        {!showAdmin && (
          <div className="flex bg-gray-700 rounded-lg p-1">
            <button
              onClick={() => setViewMode('map')}
              className={`flex items-center space-x-2 px-4 py-1.5 rounded-md transition ${viewMode === 'map' ? 'bg-blue-600 text-white shadow-lg' : 'text-gray-400 hover:text-white'}`}
            >
              <MapIcon size={18} />
              <span className="hidden sm:inline">Map</span>
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`flex items-center space-x-2 px-4 py-1.5 rounded-md transition ${viewMode === 'list' ? 'bg-blue-600 text-white shadow-lg' : 'text-gray-400 hover:text-white'}`}
            >
              <List size={18} />
              <span className="hidden sm:inline">List</span>
            </button>
            <button
              onClick={() => setViewMode('ai-search')}
              className={`flex items-center space-x-2 px-4 py-1.5 rounded-md transition ${viewMode === 'ai-search' ? 'bg-purple-600 text-white shadow-lg' : 'text-gray-400 hover:text-white'}`}
            >
              <Search size={18} />
              <span className="hidden sm:inline">AI Search</span>
            </button>
            <button
              onClick={() => setViewMode('queue')}
              className={`flex items-center space-x-2 px-4 py-1.5 rounded-md transition ${viewMode === 'queue' ? 'bg-amber-600 text-white shadow-lg' : 'text-gray-400 hover:text-white'}`}
            >
              <ClipboardList size={18} />
              <span className="hidden sm:inline">Queue</span>
            </button>
            {facesEnabled && (
              <button
                onClick={() => setViewMode('faces')}
                className={`flex items-center space-x-2 px-4 py-1.5 rounded-md transition ${viewMode === 'faces' ? 'bg-orange-600 text-white shadow-lg' : 'text-gray-400 hover:text-white'}`}
              >
                <ScanFace size={18} />
                <span className="hidden sm:inline">Faces</span>
              </button>
            )}
          </div>
        )}

        {user?.role === 'admin' && (
          <button
            onClick={onToggleAdmin}
            className={`flex items-center space-x-2 px-3 py-1.5 rounded-md transition ${showAdmin ? 'bg-red-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-700'}`}
          >
            <Users size={18} />
            <span className="hidden md:inline">{showAdmin ? 'Dashboard' : 'Admin'}</span>
          </button>
        )}

        <div className="flex items-center gap-2 pl-2 border-l border-gray-700">
          <div className="hidden md:flex items-center gap-2">
            <span className="text-sm text-gray-300">{user?.display_name || user?.username}</span>
            <span className={`px-1.5 py-0.5 border rounded text-[10px] font-bold uppercase tracking-wider ${roleBadgeClass}`}>
              {user?.role}
            </span>
          </div>
          <button
            onClick={logout}
            className="flex items-center space-x-1 px-2 py-1.5 rounded-md text-gray-400 hover:text-white hover:bg-gray-700 transition"
            title="Sign out"
          >
            <LogOut size={18} />
          </button>
        </div>
      </div>
    </header>
  );
}
