import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Briefcase, Users, CheckSquare, AlertCircle, TrendingUp, BarChart2, Shield, Clock, XCircle, ArrowRight, UserCheck, Scale } from 'lucide-react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
import './Dashboard.css';
import {
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Legend
} from 'recharts';

const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const [summary, setSummary] = useState<any>(null);
  const [velocityData, setVelocityData] = useState<any[]>([]);
  const [memberStatus, setMemberStatus] = useState<any>(null);
  const [decisionStats, setDecisionStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchDashboard = useCallback(async () => {
    try {
      const calls: Promise<any>[] = [
        api.get('/dashboard/summary'),
        api.get('/dashboard/velocity'),
      ];
      if (user?.role === 'team_member') {
        calls.push(api.get('/team-capacity/my-status').catch(() => ({ data: null })));
      } else if (user?.role === 'project_manager' || user?.role === 'admin') {
        calls.push(api.get('/decisions/stats').catch(() => ({ data: null })));
      }
      const results = await Promise.all(calls);
      setSummary(results[0].data);
      setVelocityData(results[1].data || []);
      if (user?.role === 'team_member' && results[2]?.data) {
        setMemberStatus(results[2].data);
      } else if ((user?.role === 'project_manager' || user?.role === 'admin') && results[2]?.data) {
        setDecisionStats(results[2].data);
      }
    } catch (err: any) {
      console.error('Dashboard fetch failed', err);
      setError('Failed to load dashboard data. Is the backend running?');
    } finally {
      setLoading(false);
    }
  }, [user]);

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

      {/* Team Member Placement Status Banner */}
      {user?.role === 'team_member' && memberStatus && (
        <div className={`dash-placement-banner glass-panel status-${memberStatus.status || 'none'}`}>
          <div className="dash-placement-left">
            <div className="dash-placement-icon">
              {memberStatus.status === 'active' ? (
                <UserCheck size={24} className="text-success" />
              ) : memberStatus.status === 'pending' ? (
                <Clock size={24} className="text-warning" />
              ) : memberStatus.status === 'rejected' ? (
                <XCircle size={24} className="text-error" />
              ) : (
                <Users size={24} className="text-muted" />
              )}
            </div>
            <div>
              <div className="dash-placement-top">
                <span className="dash-placement-title">Team Placement Status</span>
                <span className={`tc-status-pill ${memberStatus.status || 'none'}`}>
                  {memberStatus.status === 'active'
                    ? '✓ Active Member'
                    : memberStatus.status === 'pending'
                      ? '● Pending Review'
                      : memberStatus.status === 'rejected'
                        ? '✕ Request Rejected'
                        : 'No PM Assignment'}
                </span>
              </div>
              <p className="dash-placement-desc">
                {memberStatus.status === 'active' ? (
                  <>Assigned to <strong>{memberStatus.pm_name}</strong>'s direct team {memberStatus.pm_specialization ? `(${memberStatus.pm_specialization})` : ''}.</>
                ) : memberStatus.status === 'pending' ? (
                  <>Onboarding request sent to <strong>{memberStatus.pm_name}</strong> is awaiting PM review.</>
                ) : memberStatus.status === 'rejected' ? (
                  <>Request to join <strong>{memberStatus.pm_name}</strong>'s team was not approved. {memberStatus.rejection_reason ? `Reason: ${memberStatus.rejection_reason}` : ''}</>
                ) : (
                  <>You are not currently assigned to a Project Manager's team.</>
                )}
              </p>
            </div>
          </div>
          <Link to="/dashboard/team-capacity" className="dash-placement-link">
            <span>View Details</span>
            <ArrowRight size={14} />
          </Link>
        </div>
      )}

      {/* Manager Decision Intelligence Overview Banner */}
      {(user?.role === 'project_manager' || user?.role === 'admin') && decisionStats && (
        <div className="glass-panel" style={{
          padding: '1rem 1.25rem',
          marginBottom: '1.5rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
          borderLeft: '4px solid #6366f1',
          background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.08) 0%, rgba(30, 41, 59, 0.4) 100%)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
            <div style={{
              width: 38,
              height: 38,
              borderRadius: 10,
              background: 'rgba(99, 102, 241, 0.2)',
              color: '#818cf8',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0
            }}>
              <Scale size={20} />
            </div>
            <div>
              <h4 style={{ margin: 0, fontSize: '0.95rem', color: '#f8fafc', fontWeight: 600 }}>Decision Intelligence &amp; Audit Log</h4>
              <p style={{ margin: '2px 0 0', fontSize: '0.82rem', color: '#94a3b8' }}>
                <strong style={{ color: '#f8fafc' }}>{decisionStats.total || 0}</strong> formal management decisions recorded ·{' '}
                <strong style={{ color: decisionStats.pending > 0 ? '#f59e0b' : '#94a3b8' }}>{decisionStats.pending || 0}</strong> awaiting action ·{' '}
                <strong style={{ color: '#10b981' }}>{decisionStats.approved || 0}</strong> approved
              </p>
            </div>
          </div>
          <Link
            to="/dashboard/decisions"
            className="secondary-button"
            style={{
              padding: '0.45rem 0.9rem',
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              textDecoration: 'none'
            }}
          >
            <span>Review Decision Log</span>
            <ArrowRight size={14} />
          </Link>
        </div>
      )}

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
