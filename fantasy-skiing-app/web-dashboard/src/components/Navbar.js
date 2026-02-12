import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const NAV_ITEMS = [
  { path: '/races', label: 'Races' },
  { path: '/my-teams', label: 'My Teams' },
  { path: '/leaderboard', label: 'Leaderboard' },
];

export default function Navbar() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);

  if (!user) return null;

  return (
    <nav className="bg-snow-900 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/races" className="flex items-center space-x-2">
            <span className="text-2xl">⛷</span>
            <span className="text-xl font-bold tracking-tight">Fantasy XC Skiing</span>
          </Link>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center space-x-1">
            {NAV_ITEMS.map(({ path, label }) => (
              <Link
                key={path}
                to={path}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  location.pathname.startsWith(path)
                    ? 'bg-snow-700 text-white'
                    : 'text-snow-200 hover:bg-snow-800 hover:text-white'
                }`}
              >
                {label}
              </Link>
            ))}
          </div>

          {/* User info */}
          <div className="hidden md:flex items-center space-x-4">
            <div className="text-right">
              <div className="text-sm font-medium">{user.username || user.display_name}</div>
              <div className="text-xs text-snow-300">
                Balance: {(user.balance || 0).toLocaleString()} coins
              </div>
            </div>
            <button
              onClick={logout}
              className="px-3 py-1.5 text-sm bg-snow-700 hover:bg-snow-600 rounded-lg transition-colors"
            >
              Logout
            </button>
          </div>

          {/* Mobile menu button */}
          <button
            className="md:hidden p-2 rounded-lg hover:bg-snow-800"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {menuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile menu */}
        {menuOpen && (
          <div className="md:hidden pb-4 space-y-1">
            {NAV_ITEMS.map(({ path, label }) => (
              <Link
                key={path}
                to={path}
                onClick={() => setMenuOpen(false)}
                className={`block px-4 py-2 rounded-lg text-sm ${
                  location.pathname.startsWith(path) ? 'bg-snow-700' : 'hover:bg-snow-800'
                }`}
              >
                {label}
              </Link>
            ))}
            <div className="px-4 py-2 text-sm text-snow-300">
              {user.username} | {(user.balance || 0).toLocaleString()} coins
            </div>
            <button onClick={logout} className="block w-full text-left px-4 py-2 text-sm hover:bg-snow-800">
              Logout
            </button>
          </div>
        )}
      </div>
    </nav>
  );
}
