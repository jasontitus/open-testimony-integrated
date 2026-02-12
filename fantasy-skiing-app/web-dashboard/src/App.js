import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './hooks/useAuth';
import Navbar from './components/Navbar';
import LoginPage from './pages/LoginPage';
import RacesPage from './pages/RacesPage';
import RaceDetailPage from './pages/RaceDetailPage';
import DashboardPage from './pages/DashboardPage';
import TeamBuilderPage from './pages/TeamBuilderPage';
import BettingPage from './pages/BettingPage';
import LeaderboardPage from './pages/LeaderboardPage';
import MyTeamsPage from './pages/MyTeamsPage';

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center h-screen">Loading...</div>;
  if (!user) return <Navigate to="/login" />;
  return children;
}

function AppRoutes() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-snow-50 via-white to-nordic-50">
      <Navbar />
      <main className="max-w-7xl mx-auto px-4 py-6">
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/races" element={<ProtectedRoute><RacesPage /></ProtectedRoute>} />
          <Route path="/races/:id" element={<ProtectedRoute><RaceDetailPage /></ProtectedRoute>} />
          <Route path="/races/:id/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="/races/:id/team" element={<ProtectedRoute><TeamBuilderPage /></ProtectedRoute>} />
          <Route path="/races/:id/bet" element={<ProtectedRoute><BettingPage /></ProtectedRoute>} />
          <Route path="/my-teams" element={<ProtectedRoute><MyTeamsPage /></ProtectedRoute>} />
          <Route path="/leaderboard" element={<ProtectedRoute><LeaderboardPage /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/races" />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}
