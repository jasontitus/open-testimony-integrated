import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getRace, getRaceEntries, createTeam } from '../services/api';
import CountryFlag from '../components/CountryFlag';

const MAX_TEAM_SIZE = 5;

export default function TeamBuilderPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [race, setRace] = useState(null);
  const [entries, setEntries] = useState([]);
  const [selected, setSelected] = useState([]);
  const [captainId, setCaptainId] = useState(null);
  const [teamName, setTeamName] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getRace(id), getRaceEntries(id)]).then(([r, e]) => {
      setRace(r.data);
      setEntries(e.data);
      setLoading(false);
    });
  }, [id]);

  const toggleSkier = (skierId) => {
    setSelected((prev) => {
      if (prev.includes(skierId)) {
        const next = prev.filter((s) => s !== skierId);
        if (captainId === skierId) setCaptainId(next[0] || null);
        return next;
      }
      if (prev.length >= MAX_TEAM_SIZE) return prev;
      if (!captainId) setCaptainId(skierId);
      return [...prev, skierId];
    });
  };

  const handleSubmit = async () => {
    setError('');
    if (!teamName.trim()) return setError('Enter a team name');
    if (selected.length === 0) return setError('Select at least one skier');
    if (!captainId) return setError('Select a captain');

    setSubmitting(true);
    try {
      await createTeam({
        race_id: parseInt(id),
        name: teamName.trim(),
        skier_ids: selected,
        captain_id: captainId,
      });
      navigate(`/races/${id}/dashboard`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create team');
    }
    setSubmitting(false);
  };

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>;

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-snow-900 mb-2">Build Your Team</h1>
      <p className="text-gray-500 mb-6">{race?.name} | Select up to {MAX_TEAM_SIZE} skiers</p>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          {error}
        </div>
      )}

      {/* Team name */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-1">Team Name</label>
        <input
          type="text"
          placeholder="e.g. Nordic Thunder"
          className="w-full max-w-md px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-snow-500 focus:border-transparent"
          value={teamName}
          onChange={(e) => setTeamName(e.target.value)}
        />
      </div>

      {/* Selected team summary */}
      {selected.length > 0 && (
        <div className="bg-snow-50 border border-snow-200 rounded-xl p-4 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-snow-900">Your Squad ({selected.length}/{MAX_TEAM_SIZE})</h3>
            <button
              onClick={handleSubmit}
              disabled={submitting}
              className="px-6 py-2 bg-nordic-700 text-white rounded-lg font-semibold hover:bg-nordic-900 disabled:opacity-50"
            >
              {submitting ? 'Creating...' : 'Confirm Team'}
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {selected.map((sid) => {
              const entry = entries.find((e) => e.skier.id === sid);
              if (!entry) return null;
              return (
                <div
                  key={sid}
                  className={`flex items-center space-x-2 px-3 py-2 rounded-lg border cursor-pointer ${
                    captainId === sid
                      ? 'bg-yellow-50 border-yellow-400'
                      : 'bg-white border-gray-200'
                  }`}
                  onClick={() => setCaptainId(sid)}
                  title="Click to make captain"
                >
                  <CountryFlag country={entry.skier.country} />
                  <span className="text-sm font-medium">{entry.skier.name}</span>
                  {captainId === sid && (
                    <span className="text-xs bg-yellow-400 text-yellow-900 px-1.5 py-0.5 rounded-full font-bold">
                      C
                    </span>
                  )}
                  <button
                    onClick={(e) => { e.stopPropagation(); toggleSkier(sid); }}
                    className="text-red-400 hover:text-red-600 text-xs"
                  >
                    x
                  </button>
                </div>
              );
            })}
          </div>
          <p className="text-xs text-gray-500 mt-2">Click a skier to make them captain (2x points)</p>
        </div>
      )}

      {/* Skier list */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-snow-900">Available Skiers</h2>
        </div>
        <div className="divide-y divide-gray-100">
          {entries.map((entry) => {
            const isSelected = selected.includes(entry.skier.id);
            const isFull = selected.length >= MAX_TEAM_SIZE && !isSelected;
            return (
              <div
                key={entry.id}
                onClick={() => !isFull && toggleSkier(entry.skier.id)}
                className={`flex items-center px-6 py-4 cursor-pointer transition-colors ${
                  isSelected
                    ? 'bg-snow-50 border-l-4 border-l-snow-600'
                    : isFull
                    ? 'opacity-40 cursor-not-allowed'
                    : 'hover:bg-gray-50'
                }`}
              >
                <div className="flex items-center flex-1 min-w-0">
                  <div className={`w-5 h-5 rounded border-2 mr-4 flex items-center justify-center ${
                    isSelected ? 'bg-snow-600 border-snow-600' : 'border-gray-300'
                  }`}>
                    {isSelected && (
                      <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </div>
                  <CountryFlag country={entry.skier.country} className="text-xl mr-3" />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-snow-900">{entry.skier.name}</div>
                    <div className="text-sm text-gray-500">
                      Bib #{entry.bib_number} | {entry.skier.specialty} | Rating: {entry.skier.skill_rating}
                    </div>
                  </div>
                </div>
                <div className="flex items-center">
                  <div className="w-24 bg-gray-200 rounded-full h-2 mr-2">
                    <div
                      className="bg-snow-600 h-2 rounded-full"
                      style={{ width: `${entry.skier.skill_rating}%` }}
                    />
                  </div>
                  <span className="text-sm font-mono text-gray-500 w-8">{entry.skier.skill_rating}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
