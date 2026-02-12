import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { getRaceDashboard, simulateCheckpoint } from '../services/api';
import StatusBadge from '../components/StatusBadge';
import CountryFlag from '../components/CountryFlag';
import PositionBadge from '../components/PositionBadge';

export default function DashboardPage() {
  const { id } = useParams();
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const intervalRef = useRef(null);

  const loadDashboard = useCallback(async () => {
    try {
      const res = await getRaceDashboard(id);
      setDashboard(res.data);
    } catch (err) {
      console.error('Failed to load dashboard:', err);
    }
    setLoading(false);
  }, [id]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    if (autoRefresh && dashboard?.race?.status === 'live') {
      intervalRef.current = setInterval(loadDashboard, 5000);
    }
    return () => clearInterval(intervalRef.current);
  }, [autoRefresh, dashboard?.race?.status, loadDashboard]);

  const handleSimulate = async () => {
    await simulateCheckpoint(id);
    await loadDashboard();
  };

  if (loading) return <div className="text-center py-12 text-gray-500">Loading dashboard...</div>;
  if (!dashboard) return <div className="text-center py-12 text-red-500">Dashboard not available</div>;

  const { race, standings, team, team_total_points } = dashboard;
  const maxCheckpoint = standings.length > 0 ? standings[0].current_checkpoint : 0;
  const progressPct = race.num_checkpoints > 0
    ? Math.round((maxCheckpoint / race.num_checkpoints) * 100) : 0;

  return (
    <div>
      {/* Race header with live indicator */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center space-x-3">
              <StatusBadge status={race.status} />
              {race.status === 'live' && (
                <span className="text-xs text-gray-400">
                  Auto-refresh {autoRefresh ? 'on' : 'off'}
                </span>
              )}
            </div>
            <h1 className="text-2xl font-bold text-snow-900 mt-2">{race.name}</h1>
            <p className="text-gray-500">{race.location} | {race.distance_km}km {race.technique}</p>
          </div>
          <div className="flex space-x-2">
            {race.status === 'live' && (
              <button
                onClick={() => setAutoRefresh(!autoRefresh)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
                  autoRefresh ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
                }`}
              >
                {autoRefresh ? 'Auto' : 'Manual'}
              </button>
            )}
            {race.status !== 'finished' && (
              <button
                onClick={handleSimulate}
                className="px-4 py-1.5 bg-snow-700 text-white rounded-lg text-sm font-medium hover:bg-snow-800"
              >
                Advance Race
              </button>
            )}
          </div>
        </div>

        {/* Race progress bar */}
        <div className="mt-4">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Checkpoint {maxCheckpoint} of {race.num_checkpoints}</span>
            <span>{progressPct}% complete</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3">
            <div
              className="bg-gradient-to-r from-snow-500 to-nordic-500 h-3 rounded-full transition-all duration-500"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      </div>

      {/* Team summary card */}
      {team && (
        <div className="bg-gradient-to-r from-snow-800 to-snow-900 text-white rounded-xl shadow-lg p-6 mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">{team.name}</h2>
              <p className="text-snow-300 text-sm">{team.members.length} skiers drafted</p>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold">{team_total_points.toFixed(0)}</div>
              <div className="text-snow-300 text-sm">team points</div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {team.members.map((m) => (
              <div
                key={m.id}
                className={`px-3 py-1.5 rounded-lg text-sm ${
                  m.is_captain
                    ? 'bg-yellow-500 text-yellow-900 font-bold'
                    : 'bg-snow-700 text-snow-100'
                }`}
              >
                <CountryFlag country={m.skier.country} className="mr-1" />
                {m.skier.name}
                {m.is_captain && ' (C)'}
                <span className="ml-2 opacity-75">{m.points_earned.toFixed(0)}pts</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Live standings table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-snow-900">
            {race.status === 'finished' ? 'Final Standings' : 'Live Standings'}
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                <th className="px-6 py-3 w-16">Pos</th>
                <th className="px-6 py-3">Skier</th>
                <th className="px-6 py-3 w-20">Bib</th>
                <th className="px-6 py-3">Time</th>
                <th className="px-6 py-3">Gap</th>
                <th className="px-6 py-3">Speed</th>
                <th className="px-6 py-3">Fantasy Pts</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {standings.map((s) => (
                <tr
                  key={s.skier_id}
                  className={`transition-colors ${
                    s.is_on_team
                      ? s.is_captain
                        ? 'bg-yellow-50 hover:bg-yellow-100'
                        : 'bg-snow-50 hover:bg-snow-100'
                      : 'hover:bg-gray-50'
                  }`}
                >
                  <td className="px-6 py-3">
                    <PositionBadge position={s.current_position} />
                  </td>
                  <td className="px-6 py-3">
                    <div className="flex items-center">
                      <CountryFlag country={s.country} className="mr-2 text-lg" />
                      <div>
                        <div className="font-medium text-snow-900">
                          {s.skier_name}
                          {s.is_captain && (
                            <span className="ml-1.5 text-xs bg-yellow-400 text-yellow-900 px-1.5 py-0.5 rounded-full font-bold">
                              C
                            </span>
                          )}
                          {s.is_on_team && !s.is_captain && (
                            <span className="ml-1.5 text-xs bg-snow-200 text-snow-700 px-1.5 py-0.5 rounded-full">
                              Team
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-3 text-sm font-mono text-gray-500">{s.bib_number}</td>
                  <td className="px-6 py-3 text-sm font-mono text-gray-700">
                    {s.last_time_seconds > 0 ? formatTime(s.last_time_seconds) : '--'}
                  </td>
                  <td className="px-6 py-3 text-sm font-mono">
                    {s.gap_to_leader > 0 ? (
                      <span className="text-red-600">+{s.gap_to_leader.toFixed(1)}s</span>
                    ) : (
                      <span className="text-green-600 font-bold">Leader</span>
                    )}
                  </td>
                  <td className="px-6 py-3 text-sm text-gray-600">
                    {s.speed_kmh ? `${s.speed_kmh.toFixed(1)} km/h` : '--'}
                  </td>
                  <td className="px-6 py-3">
                    {s.fantasy_points > 0 ? (
                      <span className="text-sm font-bold text-nordic-700">{s.fantasy_points.toFixed(0)}</span>
                    ) : (
                      <span className="text-gray-300">--</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function formatTime(seconds) {
  if (!seconds) return '--';
  const mins = Math.floor(seconds / 60);
  const secs = (seconds % 60).toFixed(1);
  return `${mins}:${secs.padStart(4, '0')}`;
}
