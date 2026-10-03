import React, { useEffect, useState, useCallback } from 'react';
import {
  TrendingUp, Briefcase, Users, CheckSquare, AlertCircle,
  Shield, DollarSign, Clock, Zap, ChevronRight, Activity,
  BarChart2, AlertTriangle, Info
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Legend
} from 'recharts';
import api from '../services/api';
import './Analytics.css';

// ─── Tab definition ─────────────────────────────────────────────────────────
const TABS = [
  { id: 'overview',  label: 'Overview',         icon: BarChart2 },
  { id: 'projects',  label: 'Project Analytics', icon: Briefcase },
  { id: 'team',      label: 'Team Analytics',    icon: Users },
  { id: 'risks',     label: 'Risk & Predictions', icon: Shield },
  { id: 'trends',    label: 'Trends',            icon: TrendingUp },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────
const RISK_COLOR: Record<string, string> = { HIGH: '#ef4444', MEDIUM: '#f59e0b', LOW: '#10b981', UNKNOWN: '#6b7280' };
const INSIGHT_COLOR: Record<string, string> = { critical: '#ef4444', warning: '#f59e0b', info: '#818cf8' };
const fmt$ = (v: number) => v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v.toFixed(0)}`;

const tooltipStyle = {
  contentStyle: { backgroundColor: 'rgba(15,17,26,0.97)', borderColor: 'rgba(255,255,255,0.1)', color: '#fff', fontSize: 12 }
};

// ─── Reusable mini-components ────────────────────────────────────────────────
const StatCard: React.FC<{ icon: React.ReactNode; label: string; value: string | number; sub?: string; color?: string }> = ({ icon, label, value, sub, color }) => (
  <div className="an-stat-card glass-panel">
    <div className="an-stat-icon" style={{ background: `${color || '#6366f1'}22`, color: color || '#818cf8' }}>{icon}</div>
    <div className="an-stat-body">
      <div className="an-stat-label">{label}</div>
      <div className="an-stat-value">{value}</div>
      {sub && <div className="an-stat-sub">{sub}</div>}
    </div>
  </div>
);

const EmptyChart: React.FC<{ message: string }> = ({ message }) => (
  <div className="an-empty-chart">
    <Clock size={28} style={{ opacity: 0.3 }} />
    <p>{message}</p>
  </div>
);

const SectionTitle: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="an-section-title">{children}</div>
);

// ─── Main Component ───────────────────────────────────────────────────────────
const Analytics: React.FC = () => {
  const [activeTab, setActiveTab] = useState('overview');

  // Data states
  const [executive, setExecutive] = useState<any>(null);
  const [projects, setProjects] = useState<any[]>([]);
  const [team, setTeam] = useState<any>(null);
  const [risks, setRisks] = useState<any>(null);
  const [trends, setTrends] = useState<any>(null);
  const [insights, setInsights] = useState<any[]>([]);

  // Loading per tab
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<Record<string, string>>({});

  const setTab = (id: string) => {
    setActiveTab(id);
    if (id === 'overview' && !executive) loadOverview();
    if (id === 'projects' && projects.length === 0) loadProjects();
    if (id === 'team' && !team) loadTeam();
    if (id === 'risks' && !risks) loadRisks();
    if (id === 'trends' && !trends) loadTrends();
  };

  const load = async (key: string, fn: () => Promise<void>) => {
    setLoading(l => ({ ...l, [key]: true }));
    setError(e => ({ ...e, [key]: '' }));
    try { await fn(); }
    catch (err: any) { setError(e => ({ ...e, [key]: err?.response?.data?.detail || 'Failed to load.' })); }
    finally { setLoading(l => ({ ...l, [key]: false })); }
  };

  const loadOverview = useCallback(() => load('overview', async () => {
    const [execRes, insRes] = await Promise.all([
      api.get('/analytics/executive'),
      api.get('/analytics/insights'),
    ]);
    setExecutive(execRes.data);
    setInsights(insRes.data?.insights || []);
  }), []);

  const loadProjects = useCallback(() => load('projects', async () => {
    const res = await api.get('/analytics/projects');
    setProjects(res.data || []);
  }), []);

  const loadTeam = useCallback(() => load('team', async () => {
    const res = await api.get('/analytics/team');
    setTeam(res.data);
  }), []);

  const loadRisks = useCallback(() => load('risks', async () => {
    const res = await api.get('/analytics/risks');
    setRisks(res.data);
  }), []);

  const loadTrends = useCallback(() => load('trends', async () => {
    const res = await api.get('/analytics/trends?days=30');
    setTrends(res.data);
  }), []);

  // Initial load
  useEffect(() => { loadOverview(); }, [loadOverview]);

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="analytics-page">
      <div className="page-header">
        <h1>Executive Analytics</h1>
        <p>Advanced analytics &amp; executive intelligence — live from your data</p>
      </div>

      {/* Tab bar */}
      <div className="an-tabs">
        {TABS.map(t => (
          <button
            key={t.id}
            id={`analytics-tab-${t.id}`}
            className={`an-tab ${activeTab === t.id ? 'active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            <t.icon size={15} />
            {t.label}
          </button>
        ))}
      </div>

      {/* ── OVERVIEW ─────────────────────────────────────────────────────── */}
      {activeTab === 'overview' && (
        <div className="an-tab-body">
          {loading.overview && <div className="loading-state"><div className="loading-spinner" /> Loading analytics…</div>}
          {error.overview && (
            <div className="an-error" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.75rem 1rem' }}>
              <span>{error.overview}</span>
              <button onClick={loadOverview} className="primary-button" style={{ padding: '0.35rem 0.8rem', fontSize: '0.8rem' }}>Retry</button>
            </div>
          )}
          {executive && (
            <>
              {/* KPI grid */}
              <div className="an-stats-grid">
                <StatCard icon={<Briefcase size={20} />} label="Total Projects" value={executive.projects.total} sub={`${executive.projects.active} active · ${executive.projects.completed} completed`} color="#6366f1" />
                <StatCard icon={<AlertTriangle size={20} />} label="Overdue Projects" value={executive.projects.overdue} sub={`${executive.projects.high_risk} high risk`} color="#ef4444" />
                <StatCard icon={<CheckSquare size={20} />} label="Total Tasks" value={executive.tasks.total} sub={`${executive.tasks.completed} completed · ${executive.tasks.overdue} overdue`} color="#f59e0b" />
                <StatCard icon={<AlertCircle size={20} />} label="Open Issues" value={executive.issues.open} sub={`${executive.issues.critical} critical`} color="#ef4444" />
                <StatCard icon={<Users size={20} />} label="Team Members" value={executive.employees.total} sub={`${executive.employees.high_burnout_risk} high burnout risk`} color="#10b981" />
                <StatCard icon={<TrendingUp size={20} />} label="Avg. Progress" value={`${executive.projects.avg_progress}%`} sub={`${executive.projects.total} projects`} color="#10b981" />
                <StatCard icon={<DollarSign size={20} />} label="Budget Utilization" value={`${executive.budget.utilization_percent}%`} sub={`${fmt$(executive.budget.total_spent)} of ${fmt$(executive.budget.total_allocated)}`} color={executive.budget.utilization_percent > 85 ? '#ef4444' : '#10b981'} />
                <StatCard icon={<Shield size={20} />} label="High-Risk Projects" value={executive.projects.high_risk} sub={`${executive.projects.medium_risk} medium risk`} color="#f59e0b" />
              </div>

              {/* Risk distribution */}
              <div className="an-row-2">
                <div className="glass-panel an-chart-card">
                  <SectionTitle><Shield size={15} /> Project Risk Distribution</SectionTitle>
                  {executive.projects.total === 0 ? (
                    <EmptyChart message="No accessible projects found in your scope." />
                  ) : executive.projects.high_risk + executive.projects.medium_risk + executive.projects.low_risk === 0 ? (
                    <EmptyChart message="Prediction unavailable. Run AI analysis on projects first." />
                  ) : (
                    <ResponsiveContainer width="100%" height={220}>
                      <PieChart>
                        <Pie data={[
                          { name: 'High', value: executive.projects.high_risk, color: '#ef4444' },
                          { name: 'Medium', value: executive.projects.medium_risk, color: '#f59e0b' },
                          { name: 'Low', value: executive.projects.low_risk, color: '#10b981' },
                        ].filter(d => d.value > 0)} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name}: ${value}`}>
                          {[{ color: '#ef4444' }, { color: '#f59e0b' }, { color: '#10b981' }].map((c, i) => <Cell key={i} fill={c.color} />)}
                        </Pie>
                        <Tooltip {...tooltipStyle} />
                        <Legend formatter={v => <span style={{ color: '#9ba1b0', fontSize: 12 }}>{v}</span>} />
                      </PieChart>
                    </ResponsiveContainer>
                  )}
                </div>

                <div className="glass-panel an-chart-card">
                  <SectionTitle><Zap size={15} /> Executive Insights</SectionTitle>
                  <div className="an-insights-list">
                    {insights.length === 0 && <div className="an-empty-chart"><Info size={22} style={{ opacity: 0.3 }} /><p>No insights computed yet.</p></div>}
                    {insights.map((ins, i) => (
                      <div key={i} className="an-insight-item" style={{ borderLeftColor: INSIGHT_COLOR[ins.level] || '#6366f1' }}>
                        <span className="an-insight-dot" style={{ background: INSIGHT_COLOR[ins.level] }} />
                        <span className="an-insight-text">{ins.text}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* ── PROJECT ANALYTICS ────────────────────────────────────────────── */}
      {activeTab === 'projects' && (
        <div className="an-tab-body">
          {loading.projects && <div className="loading-state"><div className="loading-spinner" /> Loading project analytics…</div>}
          {error.projects && (
            <div className="an-error" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.75rem 1rem' }}>
              <span>{error.projects}</span>
              <button onClick={loadProjects} className="primary-button" style={{ padding: '0.35rem 0.8rem', fontSize: '0.8rem' }}>Retry</button>
            </div>
          )}
          {!loading.projects && projects.length === 0 && (
            <div className="an-empty-state glass-panel"><Briefcase size={40} style={{ opacity: 0.3 }} /><p>No projects found in your scope.</p></div>
          )}

          {/* Project progress bar chart */}
          {projects.length > 0 && (
            <>
              <div className="glass-panel an-chart-card an-wide">
                <SectionTitle><TrendingUp size={15} /> Project Progress Overview</SectionTitle>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={projects.map(p => ({ name: p.name.length > 16 ? p.name.slice(0, 16) + '…' : p.name, progress: p.progress, completion: p.tasks.completion_rate }))} margin={{ left: -10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
                    <XAxis dataKey="name" stroke="#9ba1b0" tick={{ fontSize: 11 }} />
                    <YAxis stroke="#9ba1b0" tick={{ fontSize: 11 }} domain={[0, 100]} unit="%" />
                    <Tooltip {...tooltipStyle} />
                    <Legend formatter={v => <span style={{ color: '#9ba1b0', fontSize: 12 }}>{v}</span>} />
                    <Bar dataKey="progress" name="Project Progress %" fill="#6366f1" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="completion" name="Task Completion %" fill="#10b981" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Project data table */}
              <div className="glass-panel an-table-card">
                <SectionTitle><Briefcase size={15} /> Per-Project Performance</SectionTitle>
                <div className="an-table-wrap">
                  <table className="an-table">
                    <thead>
                      <tr>
                        <th>Project</th>
                        <th>Status</th>
                        <th>Progress</th>
                        <th>Tasks (Done/Total)</th>
                        <th>Overdue</th>
                        <th>Issues</th>
                        <th>Budget Util.</th>
                        <th>Risk</th>
                        <th>Delay (days)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {projects.map(p => (
                        <tr key={p.project_id}>
                          <td className="an-td-name">{p.name}</td>
                          <td><span className={`hist-badge ${p.status}`}>{p.status.replace('_', ' ')}</span></td>
                          <td>
                            <div className="an-prog-wrap">
                              <div className="an-prog-bar"><div className="an-prog-fill" style={{ width: `${p.progress}%` }} /></div>
                              <span>{p.progress}%</span>
                            </div>
                          </td>
                          <td>{p.tasks.completed}/{p.tasks.total} <span className="an-sub">({p.tasks.completion_rate}%)</span></td>
                          <td style={{ color: p.tasks.overdue > 0 ? '#f87171' : 'inherit' }}>{p.tasks.overdue}</td>
                          <td>{p.issues.open} open · {p.issues.resolved} resolved</td>
                          <td style={{ color: p.budget.utilization_percent > 85 ? '#f59e0b' : 'inherit' }}>
                            {p.budget.utilization_percent}%
                          </td>
                          <td>
                            {p.ml?.risk_class ? (
                              <span className="an-risk-badge" style={{ color: RISK_COLOR[p.ml.risk_class] }}>{p.ml.risk_class}</span>
                            ) : <span className="an-sub">Prediction unavailable</span>}
                          </td>
                          <td>
                            {p.ml?.delay_days != null
                              ? <span style={{ color: p.ml.delay_days > 0 ? '#f59e0b' : '#10b981' }}>{p.ml.delay_days > 0 ? `+${p.ml.delay_days}d` : 'On Time'}</span>
                              : <span className="an-sub">Prediction unavailable</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* ── TEAM ANALYTICS ───────────────────────────────────────────────── */}
      {activeTab === 'team' && (
        <div className="an-tab-body">
          {loading.team && <div className="loading-state"><div className="loading-spinner" /> Loading team analytics…</div>}
          {error.team && (
            <div className="an-error" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.75rem 1rem' }}>
              <span>{error.team}</span>
              <button onClick={loadTeam} className="primary-button" style={{ padding: '0.35rem 0.8rem', fontSize: '0.8rem' }}>Retry</button>
            </div>
          )}
          {team && (
            <>
              {/* Summary cards */}
              <div className="an-stats-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
                <StatCard icon={<Users size={20} />} label="Team Members" value={team.summary.total} color="#6366f1" />
                <StatCard icon={<AlertTriangle size={20} />} label="Above Capacity" value={team.summary.above_capacity} sub="Need workload relief" color="#ef4444" />
                <StatCard icon={<Activity size={20} />} label="High Burnout Risk" value={team.summary.high_risk} color="#f59e0b" />
                <StatCard icon={<TrendingUp size={20} />} label="Avg Workload" value={`${team.summary.avg_workload_ratio}%`} sub="of weekly capacity" color="#10b981" />
              </div>

              {/* Workload bar chart */}
              {team.employees.length > 0 && (
                <div className="glass-panel an-chart-card an-wide">
                  <SectionTitle><Users size={15} /> Team Workload Distribution</SectionTitle>
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={team.employees.map((e: any) => {
                      const isDup = team.employees.filter((x: any) => x.name === e.name).length > 1;
                      const label = isDup && e.email ? `${e.name.split(' ')[0]} (${e.email.split('@')[0].slice(-4)})` : e.name.split(' ')[0];
                      return {
                        name: label,
                        workload: e.workload_ratio,
                        capacity: 100,
                      };
                    })} margin={{ left: -10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
                      <XAxis dataKey="name" stroke="#9ba1b0" tick={{ fontSize: 11 }} />
                      <YAxis stroke="#9ba1b0" tick={{ fontSize: 11 }} unit="%" />
                      <Tooltip {...tooltipStyle} />
                      <Legend formatter={v => <span style={{ color: '#9ba1b0', fontSize: 12 }}>{v}</span>} />
                      <Bar dataKey="workload" name="Workload %" fill="#6366f1" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="capacity" name="100% Capacity" fill="rgba(255,255,255,0.08)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Employee table */}
              <div className="glass-panel an-table-card">
                <SectionTitle><Users size={15} /> Team Member Details</SectionTitle>
                <div className="an-table-wrap">
                  <table className="an-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Role</th>
                        <th>Workload</th>
                        <th>Assigned Hours</th>
                        <th>Capacity</th>
                        <th>Tasks</th>
                        <th>Overdue</th>
                        <th>Completion</th>
                        <th>Burnout Risk</th>
                      </tr>
                    </thead>
                    <tbody>
                      {team.employees.map((e: any) => {
                        const isDup = team.employees.filter((x: any) => x.name === e.name).length > 1;
                        return (
                          <tr key={e.employee_id}>
                            <td className="an-td-name">
                              <div>{e.name}</div>
                              {isDup && e.email && (
                                <div style={{ fontSize: '0.72rem', color: '#9ba1b0', fontWeight: 'normal' }}>
                                  {e.email}
                                </div>
                              )}
                            </td>
                            <td className="an-sub">{e.role}</td>
                            <td>
                              <div className="an-prog-wrap">
                                <div className="an-prog-bar">
                                  <div className="an-prog-fill" style={{ width: `${Math.min(e.workload_ratio, 100)}%`, background: e.workload_ratio > 100 ? '#ef4444' : e.workload_ratio > 80 ? '#f59e0b' : '#10b981' }} />
                                </div>
                                <span style={{ color: e.workload_ratio > 100 ? '#ef4444' : 'inherit', fontWeight: e.workload_ratio > 100 ? 700 : 'normal' }}>
                                  {e.workload_ratio}% {e.workload_ratio > 100 ? ' (OVERLOADED)' : ''}
                                </span>
                              </div>
                            </td>
                            <td>{e.assigned_hours}h</td>
                            <td>{e.weekly_capacity_hours}h/wk</td>
                            <td>{e.tasks.total}</td>
                            <td style={{ color: e.tasks.overdue > 0 ? '#f87171' : 'inherit' }}>{e.tasks.overdue}</td>
                            <td>{e.tasks.completion_rate}%</td>
                            <td>
                              {e.burnout?.risk_level ? (
                                <span className="an-risk-badge" style={{ color: RISK_COLOR[e.burnout.risk_level] }}>
                                  {e.burnout.risk_level}
                                  {e.burnout.risk_probability != null && ` (${(e.burnout.risk_probability * 100).toFixed(0)}%)`}
                                </span>
                              ) : <span className="an-sub">No data</span>}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
          {team && team.employees.length === 0 && (
            <div className="an-empty-state glass-panel"><Users size={40} style={{ opacity: 0.3 }} /><p>No team members found in your scope.</p></div>
          )}
        </div>
      )}

      {/* ── RISK & PREDICTIONS ───────────────────────────────────────────── */}
      {activeTab === 'risks' && (
        <div className="an-tab-body">
          {loading.risks && <div className="loading-state"><div className="loading-spinner" /> Loading risk analytics…</div>}
          {error.risks && <div className="an-error">{error.risks}</div>}
          {risks && (
            <>
              <div className="an-row-2">
                {/* Project risk pie */}
                <div className="glass-panel an-chart-card">
                  <SectionTitle><Shield size={15} /> Project Risk Distribution</SectionTitle>
                  {risks.project_risk.high + risks.project_risk.medium + risks.project_risk.low === 0 ? (
                    <EmptyChart message="No ML predictions yet. Run analysis on projects." />
                  ) : (
                    <ResponsiveContainer width="100%" height={220}>
                      <PieChart>
                        <Pie data={risks.project_risk.distribution.filter((d: any) => d.value > 0)}
                          dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name}: ${value}`}>
                          {risks.project_risk.distribution.map((d: any, i: number) => <Cell key={i} fill={d.color} />)}
                        </Pie>
                        <Tooltip {...tooltipStyle} />
                        <Legend formatter={v => <span style={{ color: '#9ba1b0', fontSize: 12 }}>{v}</span>} />
                      </PieChart>
                    </ResponsiveContainer>
                  )}
                </div>

                {/* Employee burnout pie */}
                <div className="glass-panel an-chart-card">
                  <SectionTitle><Activity size={15} /> Employee Burnout Risk Distribution</SectionTitle>
                  {risks.employee_burnout.high + risks.employee_burnout.medium + risks.employee_burnout.low === 0 ? (
                    <EmptyChart message="No burnout predictions yet. Run workload analysis on employees." />
                  ) : (
                    <ResponsiveContainer width="100%" height={220}>
                      <PieChart>
                        <Pie data={risks.employee_burnout.distribution.filter((d: any) => d.value > 0)}
                          dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${name}: ${value}`}>
                          {risks.employee_burnout.distribution.map((d: any, i: number) => <Cell key={i} fill={d.color} />)}
                        </Pie>
                        <Tooltip {...tooltipStyle} />
                        <Legend formatter={v => <span style={{ color: '#9ba1b0', fontSize: 12 }}>{v}</span>} />
                      </PieChart>
                    </ResponsiveContainer>
                  )}
                </div>
              </div>

              {/* Deadline summary */}
              <div className="an-row-2">
                <div className="glass-panel an-risk-summary-card">
                  <SectionTitle><Clock size={15} /> Deadline Delay Predictions</SectionTitle>
                  <div className="an-risk-stats">
                    <div className="an-risk-stat">
                      <span className="an-risk-stat-v" style={{ color: risks.deadline.projects_with_delay > 0 ? '#f59e0b' : '#10b981' }}>{risks.deadline.projects_with_delay}</span>
                      <span className="an-risk-stat-l">Projects with delay</span>
                    </div>
                    <div className="an-risk-stat">
                      <span className="an-risk-stat-v">{risks.deadline.avg_delay_days}d</span>
                      <span className="an-risk-stat-l">Avg predicted delay</span>
                    </div>
                    <div className="an-risk-stat">
                      <span className="an-risk-stat-v" style={{ color: risks.deadline.max_delay_days > 0 ? '#ef4444' : 'inherit' }}>{risks.deadline.max_delay_days}d</span>
                      <span className="an-risk-stat-l">Max delay</span>
                    </div>
                  </div>
                  {risks.deadline.details.length > 0 ? (
                    <table className="an-table an-table-sm">
                      <thead><tr><th>Project</th><th>Delay (days)</th><th>Probability</th></tr></thead>
                      <tbody>
                        {risks.deadline.details.map((d: any) => (
                          <tr key={d.project_id}>
                            <td>{d.name}</td>
                            <td style={{ color: '#f59e0b' }}>+{d.delay_days}d</td>
                            <td>{d.delay_probability != null ? `${(d.delay_probability * 100).toFixed(0)}%` : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : <div className="an-empty-chart" style={{ height: 60 }}><p>No deadline delays predicted.</p></div>}
                </div>

                {/* Budget overrun summary */}
                <div className="glass-panel an-risk-summary-card">
                  <SectionTitle><DollarSign size={15} /> Budget Overrun Predictions</SectionTitle>
                  <div className="an-risk-stats">
                    <div className="an-risk-stat">
                      <span className="an-risk-stat-v" style={{ color: risks.budget_overrun.projects_at_risk > 0 ? '#ef4444' : '#10b981' }}>{risks.budget_overrun.projects_at_risk}</span>
                      <span className="an-risk-stat-l">Projects at risk</span>
                    </div>
                    <div className="an-risk-stat">
                      <span className="an-risk-stat-v">{fmt$(risks.budget_overrun.avg_overrun_amount)}</span>
                      <span className="an-risk-stat-l">Avg overrun</span>
                    </div>
                    <div className="an-risk-stat">
                      <span className="an-risk-stat-v" style={{ color: risks.budget_overrun.max_overrun_amount > 0 ? '#ef4444' : 'inherit' }}>{fmt$(risks.budget_overrun.max_overrun_amount)}</span>
                      <span className="an-risk-stat-l">Max overrun</span>
                    </div>
                  </div>
                  {risks.budget_overrun.details.length > 0 ? (
                    <table className="an-table an-table-sm">
                      <thead><tr><th>Project</th><th>Risk Level</th><th>Est. Overrun</th></tr></thead>
                      <tbody>
                        {risks.budget_overrun.details.map((d: any) => (
                          <tr key={d.project_id}>
                            <td>{d.name}</td>
                            <td><span className="an-risk-badge" style={{ color: RISK_COLOR[d.overrun_risk] }}>{d.overrun_risk}</span></td>
                            <td style={{ color: d.overrun_amount > 0 ? '#f87171' : 'inherit' }}>{fmt$(d.overrun_amount)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : <div className="an-empty-chart" style={{ height: 60 }}><p>No budget overruns predicted.</p></div>}
                </div>
              </div>

              {/* High-risk projects list */}
              {risks.project_risk.high_risk_projects.length > 0 && (
                <div className="glass-panel an-table-card">
                  <SectionTitle><AlertTriangle size={15} /> High-Risk Projects</SectionTitle>
                  <div className="an-high-risk-list">
                    {risks.project_risk.high_risk_projects.map((p: any) => (
                      <div key={p.project_id} className="an-high-risk-item">
                        <ChevronRight size={14} style={{ color: '#ef4444', flexShrink: 0 }} />
                        <span className="an-td-name">{p.name}</span>
                        <span className="an-risk-badge" style={{ color: '#ef4444' }}>HIGH</span>
                        {p.risk_probability != null && (
                          <span className="an-sub">{(p.risk_probability * 100).toFixed(0)}% failure probability</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── TRENDS ───────────────────────────────────────────────────────── */}
      {activeTab === 'trends' && (
        <div className="an-tab-body">
          {loading.trends && <div className="loading-state"><div className="loading-spinner" /> Loading trend data…</div>}
          {error.trends && <div className="an-error">{error.trends}</div>}
          {trends && (
            <>
              <div className="an-trend-period glass-panel" style={{ padding: '0.65rem 1rem', marginBottom: '1rem', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                Showing last <strong style={{ color: 'var(--text-primary)' }}>{trends.period_days} days</strong>
                &nbsp;({trends.start_date} → {trends.end_date})
              </div>

              {/* Tasks trend */}
              <div className="glass-panel an-chart-card an-wide">
                <SectionTitle><CheckSquare size={15} /> Task Activity Over Time</SectionTitle>
                {!trends.has_task_data ? (
                  <EmptyChart message="Insufficient historical task data for the selected period. Create and complete tasks to build trend history." />
                ) : (
                  <ResponsiveContainer width="100%" height={240}>
                    <LineChart data={trends.series} margin={{ left: -10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
                      <XAxis dataKey="date" stroke="#9ba1b0" tick={{ fontSize: 10 }} interval={Math.floor(trends.series.length / 6)} />
                      <YAxis stroke="#9ba1b0" tick={{ fontSize: 11 }} allowDecimals={false} />
                      <Tooltip {...tooltipStyle} />
                      <Legend formatter={v => <span style={{ color: '#9ba1b0', fontSize: 12 }}>{v}</span>} />
                      <Line type="monotone" dataKey="tasks_completed" name="Completed" stroke="#10b981" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="tasks_created" name="Created" stroke="#6366f1" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>

              {/* Issues trend */}
              <div className="glass-panel an-chart-card an-wide">
                <SectionTitle><AlertCircle size={15} /> Issue Activity Over Time</SectionTitle>
                {!trends.has_issue_data ? (
                  <EmptyChart message="Insufficient historical issue data for the selected period." />
                ) : (
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={trends.series} margin={{ left: -10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
                      <XAxis dataKey="date" stroke="#9ba1b0" tick={{ fontSize: 10 }} interval={Math.floor(trends.series.length / 6)} />
                      <YAxis stroke="#9ba1b0" tick={{ fontSize: 11 }} allowDecimals={false} />
                      <Tooltip {...tooltipStyle} />
                      <Legend formatter={v => <span style={{ color: '#9ba1b0', fontSize: 12 }}>{v}</span>} />
                      <Line type="monotone" dataKey="issues_created" name="Created" stroke="#f59e0b" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="issues_resolved" name="Resolved" stroke="#10b981" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>

              {/* Activity events trend */}
              <div className="glass-panel an-chart-card an-wide">
                <SectionTitle><Activity size={15} /> Project Activity Events Over Time</SectionTitle>
                {!trends.has_activity_data ? (
                  <EmptyChart message="No project activity events recorded yet. Events are logged as your team interacts with projects, tasks and issues." />
                ) : (
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={trends.series} margin={{ left: -10 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
                      <XAxis dataKey="date" stroke="#9ba1b0" tick={{ fontSize: 10 }} interval={Math.floor(trends.series.length / 6)} />
                      <YAxis stroke="#9ba1b0" tick={{ fontSize: 11 }} allowDecimals={false} />
                      <Tooltip {...tooltipStyle} />
                      <Bar dataKey="activities" name="Activity Events" fill="#6366f1" radius={[3, 3, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default Analytics;
