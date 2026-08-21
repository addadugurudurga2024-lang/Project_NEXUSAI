import React, { useEffect, useState, useCallback } from 'react';
import { Activity, Briefcase, Users, CheckSquare, AlertCircle, TrendingUp, BarChart2, Shield, Clock } from 'lucide-react';
import api from '../services/api';
import './Dashboard.css';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Legend
} from 'recharts';

const RISK_COLORS = { HIGH: '#ef4444', MEDIUM: '#f59e0b', LOW: '#10b981', UNKNOWN: '#6b7280' };

const Dashboard: React.FC = () => {
  const [summary, setSummary] = useState<any>(null);
  const [velocityData, setVelocityData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchDashboard = useCallback(async () => {
    try {
      const [summaryRes, velocityRes] = await Promise.all([
        api.get('/dashboard/summary'),
        api.get('/dashboard/velocity'),
      ]);
      setSummary(summaryRes.data);
      setVelocityData(velocityRes.data || []);
    } catch (err: any) {
      console.error('Dashboard fetch failed', err);
      setError('Failed to load dashboard data. Is the backend running?');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  if (loading) {
    return (
      <div className="loading-state">
        <div className="loading-spinner" />
        Loading dashboard...
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-state">
        <AlertCircle size={32} />
        <p>{error}</p>
        <button className="primary-button" onClick={() => { setLoading(true); setError(''); fetchDashboard(); }}>
          Retry
        </button>
      </div>
    );
  }

  const projects = summary?.projects || {};
  const employees = summary?.employees || {};
  const issues = summary?.issues || {};
  const budget = summary?.budget || {};
  const tasks = summary?.tasks || {};

  // Risk distribution pie chart data
  const riskPieData = [
    { name: 'High Risk', value: projects.high_risk || 0, color: '#ef4444' },
    { name: 'Medium Risk', value: projects.medium_risk || 0, color: '#f59e0b' },
    { name: 'Low Risk', value: projects.low_risk || 0, color: '#10b981' },
  ].filter(d => d.value > 0);

  if (riskPieData.length === 0) {
    riskPieData.push({ name: 'No Data', value: 1, color: '#374151' });
  }

  const budgetUtil = budget.utilization_percent ? Math.round(budget.utilization_percent) : 0;

  return (
    <div className="dashboard">
      <div className="page-header">
        <h1>Command Center</h1>
        <p>Enterprise project intelligence overview — live from MongoDB</p>
      </div>

      {/* Stat Cards */}
      <div className="stats-grid">
        <div className="stat-card glass-panel">
          <div className="stat-icon" style={{ background: 'rgba(99, 102, 241, 0.2)', color: '#818cf8' }}>
            <Briefcase size={24} />
          </div>
          <div className="stat-content">
            <h3>Active Projects</h3>
            <p className="stat-value">{projects.active ?? 0}</p>
            <span className="stat-sub">{projects.total ?? 0} total · {projects.completed ?? 0} completed</span>
          </div>
        </div>

        <div className="stat-card glass-panel">
          <div className="stat-icon" style={{ background: 'rgba(16, 185, 129, 0.2)', color: '#34d399' }}>
            <Users size={24} />
          </div>
          <div className="stat-content">
            <h3>Team Members</h3>
            <p className="stat-value">{employees.total ?? 0}</p>
            <span className="stat-sub" style={{ color: employees.high_burnout_risk > 0 ? '#ef4444' : 'inherit' }}>
              {employees.high_burnout_risk ?? 0} high burnout risk
            </span>
          </div>
        </div>

        <div className="stat-card glass-panel">
          <div className="stat-icon" style={{ background: 'rgba(245, 158, 11, 0.2)', color: '#fbbf24' }}>
            <CheckSquare size={24} />
          </div>
          <div className="stat-content">
            <h3>Total Tasks</h3>
            <p className="stat-value">{tasks.total ?? 0}</p>
            <span className="stat-sub" style={{ color: tasks.overdue > 0 ? '#f87171' : 'inherit' }}>
              {tasks.overdue ?? 0} overdue
            </span>
          </div>
        </div>

        <div className="stat-card glass-panel">
          <div className="stat-icon" style={{ background: 'rgba(239, 68, 68, 0.2)', color: '#f87171' }}>
            <AlertCircle size={24} />
          </div>
          <div className="stat-content">
            <h3>Open Issues</h3>
            <p className="stat-value">{issues.open ?? 0}</p>
            <span className="stat-sub" style={{ color: issues.critical > 0 ? '#ef4444' : 'inherit' }}>
              {issues.critical ?? 0} critical
            </span>
          </div>
        </div>
      </div>

      {/* Budget bar */}
      <div className="budget-bar-card glass-panel">
        <div className="budget-bar-header">
          <div>
            <h3><BarChart2 size={16} style={{ display: 'inline', marginRight: 6 }} />Budget Utilization</h3>
            <p className="stat-sub">
              ${(budget.total_spent / 1000).toFixed(0)}k spent of ${(budget.total_allocated / 1000).toFixed(0)}k allocated
              · {budget.budget_risk_projects ?? 0} projects at risk
            </p>
          </div>
          <span className="stat-value" style={{ color: budgetUtil > 85 ? '#ef4444' : '#10b981' }}>
            {budgetUtil}%
          </span>
        </div>
        <div className="budget-progress-track">
          <div
            className="budget-progress-fill"
            style={{
              width: `${Math.min(budgetUtil, 100)}%`,
              background: budgetUtil > 85 ? 'linear-gradient(90deg, #f59e0b, #ef4444)' : 'linear-gradient(90deg, #6366f1, #10b981)'
            }}
          />
        </div>
      </div>

      {/* Charts */}
      <div className="charts-grid">
        <div className="chart-card glass-panel">
          <div className="chart-header">
            <h3>Project Risk Distribution</h3>
            <Shield size={18} className="text-muted" />
          </div>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={riskPieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} label={({ name, value }) => `${name}: ${value}`}>
                  {riskPieData.map((entry, idx) => (
                    <Cell key={idx} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ backgroundColor: 'rgba(25, 28, 41, 0.95)', borderColor: 'rgba(255,255,255,0.1)', color: '#fff' }} />
                <Legend formatter={(value) => <span style={{ color: '#9ba1b0' }}>{value}</span>} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card glass-panel">
          <div className="chart-header">
            <h3>Team Velocity Trend</h3>
            <TrendingUp size={18} className="text-muted" />
          </div>
          <div className="chart-container">
            {velocityData.length === 0 ? (
              <div className="chart-empty">
                <Clock size={32} style={{ opacity: 0.3 }} />
                <p>No sprint data yet. Create sprints and complete tasks to see velocity.</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={250}>
                <LineChart data={velocityData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                  <XAxis dataKey="sprint" stroke="#9ba1b0" tick={{ fontSize: 12 }} />
                  <YAxis stroke="#9ba1b0" tick={{ fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: 'rgba(25, 28, 41, 0.95)', borderColor: 'rgba(255,255,255,0.1)', color: '#fff' }}
                  />
                  <Line type="monotone" dataKey="points" stroke="#f59e0b" strokeWidth={3} dot={{ r: 5, fill: '#f59e0b' }} name="Story Points" />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* Recent Issues */}
      {summary?.recent_issues && summary.recent_issues.length > 0 && (
        <div className="recent-section glass-panel">
          <h3>Recent Open Issues</h3>
          <div className="recent-list">
            {summary.recent_issues.map((issue: any) => (
              <div key={issue.id} className="recent-item">
                <AlertCircle size={14} style={{ color: issue.severity === 'critical' ? '#ef4444' : '#f59e0b', flexShrink: 0 }} />
                <span className="recent-title">{issue.title}</span>
                <span className={`badge severity-${issue.severity}`}>{issue.severity}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
