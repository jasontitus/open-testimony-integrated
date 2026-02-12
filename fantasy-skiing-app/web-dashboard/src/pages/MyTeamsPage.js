import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getMyTeams, getMyBets } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import CountryFlag from '../components/CountryFlag';
import StatusBadge from '../components/StatusBadge';

export default function MyTeamsPage() {
  const { user } = useAuth();
  const [teams, setTeams] = useState([]);
  const [bets, setBets] = useState([]);
  const [tab, setTab] = useState('teams');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getMyTeams(), getMyBets()]).then(([t, b]) => {
      setTeams(t.data);
      setBets(b.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-snow-900">My Portfolio</h1>
        <div className="text-sm text-gray-500">
          Balance: <span className="font-bold text-snow-700">{(user?.balance || 0).toLocaleString()} coins</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex space-x-1 bg-gray-100 rounded-lg p-1 mb-6 max-w-xs">
        {[
          { id: 'teams', label: `Teams (${teams.length})` },
          { id: 'bets', label: `Bets (${bets.length})` },
        ].map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex-1 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              tab === id ? 'bg-white text-snow-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Teams tab */}
      {tab === 'teams' && (
        <div className="space-y-4">
          {teams.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              No teams yet. <Link to="/races" className="text-snow-600 hover:underline">Browse races</Link> to build your first team!
            </div>
          ) : (
            teams.map((team) => (
              <div key={team.id} className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="text-lg font-semibold text-snow-900">{team.name}</h3>
                    <Link to={`/races/${team.race_id}`} className="text-sm text-snow-600 hover:underline">
                      Race #{team.race_id}
                    </Link>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold text-nordic-700">{team.total_points.toFixed(0)}</div>
                    <div className="text-xs text-gray-400">points</div>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {team.members.map((m) => (
                    <div
                      key={m.id}
                      className={`flex items-center px-3 py-1.5 rounded-lg text-sm ${
                        m.is_captain
                          ? 'bg-yellow-50 border border-yellow-300'
                          : 'bg-gray-50 border border-gray-200'
                      }`}
                    >
                      <CountryFlag country={m.skier.country} className="mr-1.5" />
                      <span className="font-medium">{m.skier.name}</span>
                      {m.is_captain && <span className="ml-1 text-xs text-yellow-600 font-bold">(C)</span>}
                      <span className="ml-2 text-gray-500">{m.points_earned.toFixed(0)}pts</span>
                    </div>
                  ))}
                </div>
                <div className="mt-3 pt-3 border-t border-gray-100">
                  <Link
                    to={`/races/${team.race_id}/dashboard`}
                    className="text-sm text-snow-600 hover:text-snow-800 font-medium"
                  >
                    View Dashboard
                  </Link>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Bets tab */}
      {tab === 'bets' && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          {bets.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              No bets placed yet. <Link to="/races" className="text-snow-600 hover:underline">Browse races</Link> to start betting!
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  <th className="px-6 py-3">Race</th>
                  <th className="px-6 py-3">Skier</th>
                  <th className="px-6 py-3">Type</th>
                  <th className="px-6 py-3 text-right">Wager</th>
                  <th className="px-6 py-3 text-right">Odds</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3 text-right">Payout</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {bets.map((bet) => (
                  <tr key={bet.id} className="hover:bg-gray-50">
                    <td className="px-6 py-3">
                      <Link to={`/races/${bet.race_id}`} className="text-sm text-snow-600 hover:underline">
                        Race #{bet.race_id}
                      </Link>
                    </td>
                    <td className="px-6 py-3 font-medium text-snow-900">{bet.skier_name}</td>
                    <td className="px-6 py-3 text-sm capitalize">{bet.bet_type}</td>
                    <td className="px-6 py-3 text-right text-sm">{bet.amount}</td>
                    <td className="px-6 py-3 text-right text-sm font-mono">{bet.odds.toFixed(2)}x</td>
                    <td className="px-6 py-3"><StatusBadge status={bet.status} /></td>
                    <td className="px-6 py-3 text-right text-sm font-bold">
                      {bet.status === 'won' ? (
                        <span className="text-green-600">+{bet.payout.toFixed(0)}</span>
                      ) : bet.status === 'lost' ? (
                        <span className="text-red-500">-{bet.amount}</span>
                      ) : (
                        <span className="text-gray-400">--</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
