import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getRace, getRaceOdds, placeBet } from '../services/api';
import { useAuth } from '../hooks/useAuth';
import CountryFlag from '../components/CountryFlag';

export default function BettingPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user, refreshUser } = useAuth();
  const [race, setRace] = useState(null);
  const [odds, setOdds] = useState([]);
  const [betType, setBetType] = useState('winner');
  const [selectedSkier, setSelectedSkier] = useState(null);
  const [amount, setAmount] = useState(100);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getRace(id), getRaceOdds(id)]).then(([r, o]) => {
      setRace(r.data);
      setOdds(o.data);
      setLoading(false);
    });
  }, [id]);

  const currentOdds = selectedSkier
    ? odds.find((o) => o.skier.id === selectedSkier)
    : null;
  const displayOdds = currentOdds
    ? (betType === 'winner' ? currentOdds.win_odds : currentOdds.podium_odds)
    : 0;
  const potentialPayout = displayOdds * amount;

  const handlePlaceBet = async () => {
    setError('');
    setSuccess('');
    if (!selectedSkier) return setError('Select a skier');
    if (amount <= 0) return setError('Enter a valid amount');
    if (amount > (user?.balance || 0)) return setError('Insufficient balance');

    try {
      const res = await placeBet({
        race_id: parseInt(id),
        bet_type: betType,
        skier_id: selectedSkier,
        amount,
      });
      setSuccess(`Bet placed! ${res.data.skier_name} to ${betType} at ${res.data.odds}x - potential payout: ${res.data.amount * res.data.odds} coins`);
      setSelectedSkier(null);
      refreshUser();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to place bet');
    }
  };

  if (loading) return <div className="text-center py-12 text-gray-500">Loading...</div>;

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-snow-900 mb-2">Place Your Bets</h1>
      <p className="text-gray-500 mb-6">{race?.name}</p>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">{error}</div>
      )}
      {success && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 text-green-700 rounded-lg text-sm">{success}</div>
      )}

      {/* Bet configuration */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6">
        <div className="grid md:grid-cols-3 gap-6">
          {/* Bet type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Bet Type</label>
            <div className="space-y-2">
              {[
                { value: 'winner', label: 'Win', desc: 'Skier finishes 1st' },
                { value: 'podium', label: 'Podium', desc: 'Skier finishes top 3' },
              ].map(({ value, label, desc }) => (
                <button
                  key={value}
                  onClick={() => setBetType(value)}
                  className={`w-full text-left px-4 py-3 rounded-lg border-2 transition-colors ${
                    betType === value
                      ? 'border-snow-600 bg-snow-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="font-medium text-sm">{label}</div>
                  <div className="text-xs text-gray-500">{desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Amount */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Amount</label>
            <input
              type="number"
              min="10"
              step="10"
              value={amount}
              onChange={(e) => setAmount(Math.max(0, parseInt(e.target.value) || 0))}
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-snow-500"
            />
            <div className="flex space-x-2 mt-2">
              {[50, 100, 500, 1000].map((v) => (
                <button
                  key={v}
                  onClick={() => setAmount(v)}
                  className="px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded-md"
                >
                  {v}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-2">
              Balance: {(user?.balance || 0).toLocaleString()} coins
            </p>
          </div>

          {/* Payout summary */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Bet Summary</label>
            <div className="bg-gray-50 rounded-lg p-4">
              {selectedSkier && currentOdds ? (
                <>
                  <div className="text-sm text-gray-600 mb-1">
                    <CountryFlag country={currentOdds.skier.country} className="mr-1" />
                    {currentOdds.skier.name}
                  </div>
                  <div className="text-sm text-gray-600 mb-1">
                    Type: <span className="font-medium capitalize">{betType}</span>
                  </div>
                  <div className="text-sm text-gray-600 mb-1">
                    Odds: <span className="font-medium">{displayOdds.toFixed(2)}x</span>
                  </div>
                  <div className="text-sm text-gray-600 mb-3">
                    Wager: <span className="font-medium">{amount} coins</span>
                  </div>
                  <div className="border-t border-gray-200 pt-2">
                    <div className="text-lg font-bold text-nordic-700">
                      Potential: {potentialPayout.toFixed(0)} coins
                    </div>
                  </div>
                  <button
                    onClick={handlePlaceBet}
                    className="mt-3 w-full py-2.5 bg-snow-700 text-white rounded-lg font-semibold hover:bg-snow-800 transition-colors"
                  >
                    Place Bet
                  </button>
                </>
              ) : (
                <p className="text-sm text-gray-400">Select a skier to see odds</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Odds table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-snow-900">Odds Board</h2>
        </div>
        <div className="divide-y divide-gray-100">
          {odds.map(({ skier, win_odds, podium_odds }) => (
            <div
              key={skier.id}
              onClick={() => setSelectedSkier(skier.id)}
              className={`flex items-center px-6 py-4 cursor-pointer transition-colors ${
                selectedSkier === skier.id
                  ? 'bg-snow-50 border-l-4 border-l-snow-600'
                  : 'hover:bg-gray-50'
              }`}
            >
              <div className="flex items-center flex-1">
                <CountryFlag country={skier.country} className="text-xl mr-3" />
                <div>
                  <div className="font-medium text-snow-900">{skier.name}</div>
                  <div className="text-xs text-gray-500 capitalize">{skier.specialty} | Rating: {skier.skill_rating}</div>
                </div>
              </div>
              <div className="flex items-center space-x-4">
                <div className="text-center">
                  <div className={`text-lg font-bold ${betType === 'winner' ? 'text-snow-700' : 'text-gray-400'}`}>
                    {win_odds.toFixed(2)}x
                  </div>
                  <div className="text-xs text-gray-400">Win</div>
                </div>
                <div className="text-center">
                  <div className={`text-lg font-bold ${betType === 'podium' ? 'text-snow-700' : 'text-gray-400'}`}>
                    {podium_odds.toFixed(2)}x
                  </div>
                  <div className="text-xs text-gray-400">Podium</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-4 text-center">
        <button
          onClick={() => navigate(`/races/${id}`)}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          Back to race details
        </button>
      </div>
    </div>
  );
}
