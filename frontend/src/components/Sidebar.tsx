import React, { useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  Activity,
  LayoutDashboard,
  Briefcase,
  Users,
  CheckSquare,
  AlertCircle,
  FileText,
  LogOut,
  BrainCircuit,
  Network,
  Bell,
  BarChart3,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import api from '../services/api';
import './Sidebar.css';

const Sidebar: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [unreadCount, setUnreadCount] = useState(0);

  // Poll unread notifications count
  useEffect(() => {
    const fetchUnread = async () => {
      try {
        const res = await api.get('/dashboard/notifications?unread_only=true');
        setUnreadCount(res.data.filter((n: any) => !n.is_read).length);
      } catch {
        // ignore
      }
    };
    fetchUnread();
    const interval = setInterval(fetchUnread, 60000); // refresh every minute
    return () => clearInterval(interval);
  }, []);

  const isManager = user?.role === 'project_manager' || user?.role === 'admin';

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <Activity className="logo-icon" size={28} />
        <h2>NexusAI</h2>
      </div>

      <nav className="sidebar-nav">
        <p className="nav-label">MAIN</p>
        <NavLink to="/dashboard" end className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <LayoutDashboard size={20} />
          <span>Dashboard</span>
        </NavLink>
        <NavLink to="/dashboard/projects" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <Briefcase size={20} />
          <span>Projects</span>
        </NavLink>
        <NavLink to="/dashboard/employees" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <Users size={20} />
          <span>Employees</span>
        </NavLink>
        <NavLink to="/dashboard/tasks" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <CheckSquare size={20} />
          <span>Tasks</span>
        </NavLink>
        <NavLink to="/dashboard/issues" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <AlertCircle size={20} />
          <span>Issues</span>
        </NavLink>

        <p className="nav-label mt-4">INTELLIGENCE</p>
        <NavLink to="/dashboard/documents" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <FileText size={20} />
          <span>Document AI</span>
        </NavLink>
        <NavLink to="/dashboard/recommendations" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <BrainCircuit size={20} />
          <span>AI Insights</span>
        </NavLink>
        {isManager && (
          <NavLink to="/dashboard/resource-optimization" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Network size={20} />
            <span>Optimization</span>
          </NavLink>
        )}
        {isManager && (
          <NavLink to="/dashboard/reports" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <BarChart3 size={20} />
            <span>Reports</span>
          </NavLink>
        )}

        <p className="nav-label mt-4">SYSTEM</p>
        <NavLink to="/dashboard/notifications" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
          <Bell size={20} />
          <span>Notifications</span>
          {unreadCount > 0 && (
            <span className="nav-badge">{unreadCount > 99 ? '99+' : unreadCount}</span>
          )}
        </NavLink>
      </nav>

      <div className="sidebar-footer">
        <div className="user-profile">
          <div className="avatar">{user?.name?.charAt(0) || 'U'}</div>
          <div className="user-info">
            <p className="user-name">{user?.name}</p>
            <p className="user-role">{user?.role?.replace(/_/g, ' ')}</p>
          </div>
        </div>
        <button onClick={logout} className="logout-button">
          <LogOut size={18} />
          <span>Logout</span>
        </button>
      </div>
    </div>
  );
};

export const Layout: React.FC = () => {
  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
};
