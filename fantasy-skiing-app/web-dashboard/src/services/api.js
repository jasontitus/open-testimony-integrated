import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8001';

const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Attach auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auth
export const register = (data) => api.post('/auth/register', data);
export const login = (data) => api.post('/auth/login', data);
export const getProfile = () => api.get('/auth/me');

// Skiers
export const getSkiers = () => api.get('/skiers');
export const getSkier = (id) => api.get(`/skiers/${id}`);

// Races
export const getRaces = (status) => api.get('/races', { params: status ? { status } : {} });
export const getRace = (id) => api.get(`/races/${id}`);
export const getRaceEntries = (id) => api.get(`/races/${id}/entries`);
export const getRaceOdds = (id) => api.get(`/races/${id}/odds`);
export const getRaceCheckpoints = (id, cpNum) =>
  api.get(`/races/${id}/checkpoints`, { params: cpNum ? { checkpoint_number: cpNum } : {} });
export const getRaceDashboard = (id) => api.get(`/races/${id}/dashboard`);

// Teams
export const createTeam = (data) => api.post('/teams', data);
export const getMyTeams = () => api.get('/teams');

// Bets
export const placeBet = (data) => api.post('/bets', data);
export const getMyBets = () => api.get('/bets');

// Leaderboard
export const getLeaderboard = () => api.get('/leaderboard');

// Admin
export const simulateCheckpoint = (raceId) => api.post(`/admin/simulate/${raceId}`);
export const simulateFullRace = (raceId) => api.post(`/admin/simulate/${raceId}/full`);

export default api;
