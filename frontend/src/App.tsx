import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Signup from './pages/Signup';
import { Layout } from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import Projects from './pages/Projects';
import Employees from './pages/Employees';
import Tasks from './pages/Tasks';
import Issues from './pages/Issues';
import DocumentAI from './pages/DocumentAI';
import Recommendations from './pages/Recommendations';
import ResourceOptimization from './pages/ResourceOptimization';
import Notifications from './pages/Notifications';
import Reports from './pages/Reports';
import Analytics from './pages/Analytics';
import AIAssistant from './pages/AIAssistant';
import TeamCapacity from './pages/TeamCapacity';

import Decisions from './pages/Decisions';
import WhatIfSimulation from './pages/WhatIfSimulation';

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', color: 'white', background: '#0f111a' }}>
      Loading NexusAI...
    </div>
  );
  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return <>{children}</>;
};

const PublicRoute = ({ children }: { children: React.ReactNode }) => {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return null;
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
};

// Blocks team_member from management-only pages
const ManagerRoute = ({ children }: { children: React.ReactNode }) => {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user?.role === 'team_member') return <Navigate to="/dashboard" replace />;
  return <>{children}</>;
};

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          {/* Public routes */}
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
          <Route path="/signup" element={<PublicRoute><Signup /></PublicRoute>} />

          {/* Protected app routes */}
          <Route path="/dashboard" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route index element={<Dashboard />} />
            <Route path="projects" element={<Projects />} />
            <Route path="employees" element={<Employees />} />
            <Route path="team-capacity" element={<TeamCapacity />} />
            <Route path="tasks" element={<Tasks />} />
            <Route path="issues" element={<Issues />} />
            <Route path="documents" element={<DocumentAI />} />
            <Route path="recommendations" element={<Recommendations />} />
            <Route path="resource-optimization" element={<ManagerRoute><ResourceOptimization /></ManagerRoute>} />
            <Route path="what-if-simulation" element={<ManagerRoute><WhatIfSimulation /></ManagerRoute>} />
            <Route path="decisions" element={<ManagerRoute><Decisions /></ManagerRoute>} />
            <Route path="notifications" element={<Notifications />} />
            <Route path="reports" element={<ManagerRoute><Reports /></ManagerRoute>} />
            <Route path="analytics" element={<ManagerRoute><Analytics /></ManagerRoute>} />
            <Route path="ai-assistant" element={<AIAssistant />} />
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
