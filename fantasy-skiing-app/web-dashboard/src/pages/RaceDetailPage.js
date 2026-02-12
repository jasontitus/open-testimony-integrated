import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getRace, getRaceEntries, simulateCheckpoint } from '../services/api';
import StatusBadge from '../components/StatusBadge';
import CountryFlag from '../components/CountryFlag';
import PositionBadge from '../components/PositionBadge';

export default function RaceDetailPage() {
  const { id } = useParams();
  const [race, setRace] = useState(null);
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getRace(id), getRaceEntries(id)]).then(([raceRes, entriesRes]) => {
      setRace(raceRes.data);
      setEntries(entriesRes.data);
      setLoading(false);
    });
  }, [id]);

  const handleSimulate = async () => {
    await simulateCheckpoint(id);
    const [raceRes, entriesRes] = await Promise.all([getRace(id), getRaceEntries(id)]);
    setRace(raceRes.data);
    setEntries(entriesRes.data);
  };

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>;
  if (!race) return <div className="text-center py-12 text-red-500">Race not found</div>;

  // Sort entries: finished races by position, otherwise by bib
  const sorted = [...entries].sort((a, b) => {
    if (a.final_position && b.final_position) return a.final_position - b.final_position;
    return a.bib_number - b.bib_number;
  });

  return (
    <div>
      {/* Race header */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <StatusBadge status={race.status} />
            <h1 className="text-2xl font-bold text-snow-900 mt-2">{race.name}</h1>
            <p className="text-gray-500 mt-1">{race.location}</p>
            <div className="flex items-center space-x-4 mt-3 text-sm text-gray-600">
              <span>{race.distance_km}km</span>
              <span>{race.technique}</span>
              <span>{race.entry_count} skiers</span>
              <span>{race.num_checkpoints} checkpoints</span>
            </div>
          </div>

          <div className="flex flex-col space-y-2">
            {race.status !== 'finished' && (
              <>
                <Link
                  to={`/races/${id}/team`}
                  className="px-4 py-2 bg-nordic-700 text-white rounded-lg text-sm font-medium hover:bg-nordic-900 transition-colors text-center"
                >
                  Build Team
                </Link>
                <Link
                  to={`/races/${id}/bet`}
                  className="px-4 py-2 bg-snow-700 text-white rounded-lg text-sm font-medium hover:bg-snow-800 transition-colors text-center"
                >
                  Place Bets
                </Link>
              </>
            )}
            {(race.status === 'live' || race.status === 'finished') && (
              <Link
                to={`/races/${id}/dashboard`}
                className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 transition-colors text-center"
              >
                Live Dashboard
              </Link>
            )}
            {race.status !== 'finished' && (
              <button
                onClick={handleSimulate}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-300 transition-colors"
              >
                Simulate CP
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Entries table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-snow-900">
            {race.status === 'finished' ? 'Final Results' : 'Start List'}
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                <th className="px-6 py-3">{race.status === 'finished' ? 'Pos' : 'Bib'}</th>
                <th className="px-6 py-3">Skier</th>
                <th className="px-6 py-3">Country</th>
                <th className="px-6 py-3">Specialty</th>
                <th className="px-6 py-3">Rating</th>
                {race.status === 'finished' && (
                  <>
                    <th className="px-6 py-3">Time</th>
                    <th className="px-6 py-3">Points</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {sorted.map((entry) => (
                <tr key={entry.id} className={`hover:bg-gray-50 ${entry.dnf ? 'opacity-50' : ''}`}>
                  <td className="px-6 py-3">
                    {entry.final_position ? (
                      <PositionBadge position={entry.final_position} />
                    ) : (
                      <span className="text-gray-500 font-mono">{entry.bib_number}</span>
                    )}
                  </td>
                  <td className="px-6 py-3 font-medium text-snow-900">{entry.skier.name}</td>
                  <td className="px-6 py-3">
                    <CountryFlag country={entry.skier.country} />
                    <span className="ml-1 text-sm text-gray-500">{entry.skier.country}</span>
                  </td>
                  <td className="px-6 py-3 text-sm text-gray-600 capitalize">{entry.skier.specialty}</td>
                  <td className="px-6 py-3">
                    <div className="flex items-center">
                      <div className="w-16 bg-gray-200 rounded-full h-2 mr-2">
                        <div
                          className="bg-snow-600 h-2 rounded-full"
                          style={{ width: `${entry.skier.skill_rating}%` }}
                        />
                      </div>
                      <span className="text-sm text-gray-600">{entry.skier.skill_rating}</span>
                    </div>
                  </td>
                  {race.status === 'finished' && (
                    <>
                      <td className="px-6 py-3 text-sm font-mono text-gray-600">
                        {entry.dnf ? 'DNF' : formatTime(entry.final_time_seconds)}
                      </td>
                      <td className="px-6 py-3 text-sm font-semibold text-nordic-700">
                        {entry.points_earned}
                      </td>
                    </>
                  )}
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
