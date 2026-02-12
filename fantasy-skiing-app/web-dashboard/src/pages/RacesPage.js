import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getRaces } from '../services/api';
import StatusBadge from '../components/StatusBadge';

const FILTERS = [
  { label: 'All', value: null },
  { label: 'Live', value: 'live' },
  { label: 'Upcoming', value: 'upcoming' },
  { label: 'Finished', value: 'finished' },
];

export default function RacesPage() {
  const [races, setRaces] = useState([]);
  const [filter, setFilter] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getRaces(filter).then((res) => {
      setRaces(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [filter]);

  const formatDate = (dateStr) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', {
      weekday: 'short', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-snow-900">Races</h1>
        <div className="flex space-x-2">
          {FILTERS.map(({ label, value }) => (
            <button
              key={label}
              onClick={() => setFilter(value)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
                filter === value
                  ? 'bg-snow-700 text-white'
                  : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading races...</div>
      ) : races.length === 0 ? (
        <div className="text-center py-12 text-gray-500">No races found</div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {races.map((race) => (
            <Link
              key={race.id}
              to={`/races/${race.id}`}
              className="bg-white rounded-xl shadow-sm border border-gray-100 hover:shadow-md hover:border-snow-200 transition-all p-5"
            >
              <div className="flex items-start justify-between mb-3">
                <StatusBadge status={race.status} />
                <span className="text-xs text-gray-400 uppercase font-semibold">
                  {race.technique}
                </span>
              </div>

              <h3 className="text-lg font-semibold text-snow-900 mb-1">{race.name}</h3>
              <p className="text-sm text-gray-500 mb-3">{race.location}</p>

              <div className="flex items-center justify-between text-sm">
                <div className="text-gray-600">
                  <span className="font-medium">{race.distance_km}km</span>
                  <span className="mx-1.5 text-gray-300">|</span>
                  <span>{race.race_type}</span>
                </div>
                <div className="text-gray-400">{race.entry_count} skiers</div>
              </div>

              <div className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-400">
                {formatDate(race.start_time)}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
