import React, { useState, useEffect } from 'react';
import { getLeaderboard } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import PositionBadge from '../components/PositionBadge';

export default function LeaderboardPage() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const { user } = useAuth();

  useEffect(() => {
    getLeaderboard().then((res) => {
      setEntries(res.data);
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="text-center py-12 text-gray-500">Loading leaderboard...</div>;

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold text-snow-900 mb-6">Leaderboard</h1>

      {/* Top 3 podium */}
      {entries.length >= 3 && (
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[entries[1], entries[0], entries[2]].map((e, i) => {
            const pos = [2, 1, 3][i];
            const heights = ['h-28', 'h-36', 'h-24'];
            const colors = [
              'from-gray-300 to-gray-400',
              'from-yellow-300 to-yellow-500',
              'from-amber-500 to-amber-700',
            ];
            return (
              <div key={e.user_id} className="flex flex-col items-center justify-end">
                <div className={`text-center mb-2 ${user?.id === e.user_id ? 'font-bold' : ''}`}>
                  <div className="text-sm font-semibold text-snow-900">
                    {e.display_name || e.username}
                  </div>
                  <div className="text-lg font-bold text-nordic-700">
                    {e.total_points.toFixed(0)} pts
                  </div>
                </div>
                <div className={`w-full ${heights[i]} rounded-t-xl bg-gradient-to-t ${colors[i]} flex items-center justify-center`}>
                  <span className="text-2xl font-bold text-white">{pos}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Full leaderboard table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
              <th className="px-6 py-3 w-16">Rank</th>
              <th className="px-6 py-3">Player</th>
              <th className="px-6 py-3 text-right">Points</th>
              <th className="px-6 py-3 text-right">Teams</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {entries.map((e) => (
              <tr
                key={e.user_id}
                className={`${
                  user?.id === e.user_id ? 'bg-snow-50 font-semibold' : 'hover:bg-gray-50'
                }`}
              >
                <td className="px-6 py-3">
                  <PositionBadge position={e.rank} />
                </td>
                <td className="px-6 py-3">
                  <div className="text-snow-900">
                    {e.display_name || e.username}
                    {user?.id === e.user_id && (
                      <span className="ml-2 text-xs text-snow-500">(you)</span>
                    )}
                  </div>
                </td>
                <td className="px-6 py-3 text-right text-nordic-700 font-bold">
                  {e.total_points.toFixed(0)}
                </td>
                <td className="px-6 py-3 text-right text-gray-500">
                  {e.team_count}
                </td>
              </tr>
            ))}
            {entries.length === 0 && (
              <tr>
                <td colSpan="4" className="px-6 py-8 text-center text-gray-400">
                  No players yet. Be the first to join!
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
