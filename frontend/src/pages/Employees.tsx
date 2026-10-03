import React, { useEffect, useState } from 'react';
import { Flame, BrainCircuit, Activity, UserPlus, Briefcase, CheckSquare, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
import './Employees.css';

const Employees: React.FC = () => {
  const [employees, setEmployees] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const { user } = useAuth();

  const isManager = user?.role === 'project_manager' || user?.role === 'admin';
  const isTeamMember = user?.role === 'team_member';

  // Phase 6: own history panel (for team_member view)
  const [myHistory, setMyHistory] = useState<any | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Phase 6: per-employee history panel (for manager/admin view)
  const [empHistoryOpen, setEmpHistoryOpen] = useState<string | null>(null);
  const [empHistories, setEmpHistories] = useState<Record<string, any>>({});
  const [empHistoryLoading, setEmpHistoryLoading] = useState<string | null>(null);

  const fetchEmployees = async () => {
    try {
      const response = await api.get('/employees/');
      const enriched = await Promise.all(response.data.map(async (emp: any) => {
        try {
          const predRes = await api.get(`/employee-risk/${emp.id}/latest`);
          return { ...emp, risk: predRes.data };
        } catch (e) {
          return { ...emp, risk: null };
        }
      }));
      setEmployees(enriched);
    } catch (err) {
      console.error('Failed to fetch employees', err);
    } finally {
      setLoading(false);
    }
  };

  // Phase 6: fetch own history for team_member
  const fetchMyHistory = async () => {
    setHistoryLoading(true);
    try {
      const res = await api.get('/activities/employee/me');
      setMyHistory(res.data);
    } catch {
      setMyHistory(null);
    } finally {
      setHistoryLoading(false);
    }
  };

  // Phase 6: toggle employee history for manager/admin
  const toggleEmpHistory = async (empId: string) => {
    if (empHistoryOpen === empId) {
      setEmpHistoryOpen(null);
      return;
    }
    setEmpHistoryOpen(empId);
    if (!empHistories[empId]) {
      setEmpHistoryLoading(empId);
      try {
        const res = await api.get(`/activities/employee/${empId}`);
        setEmpHistories(prev => ({ ...prev, [empId]: res.data }));
      } catch {
        setEmpHistories(prev => ({ ...prev, [empId]: null }));
      } finally {
        setEmpHistoryLoading(null);
      }
    }
  };

  useEffect(() => {
    fetchEmployees();
    if (isTeamMember) {
      fetchMyHistory();
      setHistoryOpen(true);
    }
  }, []);

  const getRiskColor = (level: string) => {
    if (level === 'HIGH') return 'var(--error)';
    if (level === 'MEDIUM') return 'var(--warning)';
    return 'var(--success)';
  };

  const getPriorityColor = (p: string) =>
    p === 'critical' ? 'var(--error)' : p === 'high' ? '#f59e0b' : 'var(--text-muted)';

  const getStatusBadgeClass = (s: string) => {
    if (s === 'done') return 'hist-badge done';
    if (s === 'in_progress') return 'hist-badge inprog';
    if (s === 'overdue') return 'hist-badge overdue';
    return 'hist-badge todo';
  };

  if (loading) return <div className="loading-state">Loading employees...</div>;

  return (
    <div className="employees-page">
      <div className="page-header flex-between">
        <div>
          <h1>Team Intelligence</h1>
          <p>Workload and burnout risk monitoring</p>
        </div>
        {isManager && (
          <button className="primary-button" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <UserPlus size={16} />
            Add Member
          </button>
        )}
      </div>

      {/* Phase 6: Team Member — My Work History Panel */}
      {isTeamMember && (
        <div className="glass-panel emp-history-panel">
          <div className="hist-panel-header" onClick={() => setHistoryOpen(v => !v)} style={{ cursor: 'pointer' }}>
            <Activity size={16} />
            <span>My Work History</span>
            {historyOpen ? <ChevronUp size={14} style={{ marginLeft: 'auto' }} /> : <ChevronDown size={14} style={{ marginLeft: 'auto' }} />}
          </div>
          {historyOpen && (
            historyLoading ? (
              <div className="activity-loading">Loading your history...</div>
            ) : !myHistory ? (
              <div className="activity-empty">Could not load history. Make sure your account is linked to an employee profile.</div>
            ) : (
              <div className="hist-sections">
                {/* Assigned Projects */}
                <div className="hist-section">
                  <div className="hist-section-title"><Briefcase size={13} /> Assigned Projects ({myHistory.projects?.length || 0})</div>
                  {(myHistory.projects || []).length === 0 ? (
                    <div className="hist-empty">No projects assigned.</div>
                  ) : (
                    <div className="hist-project-list">
                      {myHistory.projects.map((p: any) => (
                        <div key={p.id} className="hist-project-chip">
                          <span className="hist-proj-name">{p.name}</span>
                          <span className={`hist-badge ${p.status}`}>{p.status.replace('_', ' ')}</span>
                          <div className="hist-progress-mini">
                            <div className="hist-prog-fill" style={{ width: `${p.progress}%` }} />
                          </div>
                          <span className="hist-prog-pct">{p.progress}%</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Task History */}
                <div className="hist-section">
                  <div className="hist-section-title"><CheckSquare size={13} /> Task History</div>
                  {(['overdue', 'in_progress', 'todo', 'done'] as string[]).map(status => {
                    const taskList = status === 'overdue' ? (myHistory.tasks?.overdue || []) : (myHistory.tasks?.[status] || []);
                    if (taskList.length === 0) return null;
                    return (
                      <div key={status} className="hist-task-group">
                        <div className="hist-task-group-label">
                          <span className={getStatusBadgeClass(status)}>{status.replace('_', ' ')}</span>
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>({taskList.length})</span>
                        </div>
                        {taskList.map((t: any) => (
                          <div key={t.id} className="hist-task-row">
                            <span className="hist-task-title">{t.title}</span>
                            {t.project_name && <span className="hist-task-proj">{t.project_name}</span>}
                            <span className="hist-task-priority" style={{ color: getPriorityColor(t.priority) }}>{t.priority}</span>
                            {t.due_date && <span className="hist-task-due">{t.due_date}</span>}
                          </div>
                        ))}
                      </div>
                    );
                  })}
                  {Object.values(myHistory.tasks || {}).every((g: any) => g.length === 0) && (
                    <div className="hist-empty">No tasks assigned yet.</div>
                  )}
                </div>

                {/* Issue History */}
                {(myHistory.issues || []).length > 0 && (
                  <div className="hist-section">
                    <div className="hist-section-title"><AlertCircle size={13} /> Issues ({myHistory.issues.length})</div>
                    {myHistory.issues.map((iss: any) => (
                      <div key={iss.id} className="hist-task-row">
                        <span className="hist-task-title">{iss.title}</span>
                        {iss.project_name && <span className="hist-task-proj">{iss.project_name}</span>}
                        <span className={`hist-badge ${iss.status === 'resolved' ? 'done' : 'todo'}`}>{iss.status}</span>
                        <span className="hist-task-priority" style={{ color: getPriorityColor(iss.severity) }}>{iss.severity}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          )}
        </div>
      )}

      <div className="employees-grid">
        {employees.map((emp) => (
          <div key={emp.id} className="employee-card glass-panel">
            <div className="emp-header">
              <div className="emp-avatar">{emp.name.charAt(0)}</div>
              <div className="emp-info">
                <h3>{emp.name}</h3>
                <p>{emp.role}</p>
              </div>
              <span className={`status-dot ${emp.status}`} />
            </div>

            {/* Specialization badge */}
            {emp.specialization && (
              <div className="emp-specialization">
                <span className="spec-label">Specialization</span>
                <span className="spec-value">{emp.specialization}</span>
              </div>
            )}

            <div className="skills-container">
              {emp.skills.map((skill: string) => (
                <span key={skill} className="skill-badge">{skill}</span>
              ))}
            </div>

            <div className="emp-capacity">
              <span className="label">Weekly Capacity</span>
              <span className="value">{emp.weekly_capacity_hours}h</span>
            </div>

            {emp.risk && (
              <div className="burnout-insights" style={{ borderLeftColor: getRiskColor(emp.risk.risk_level) }}>
                <div className="burnout-header">
                  <div className="flex-center gap-2">
                    <Flame size={16} color={getRiskColor(emp.risk.risk_level)} />
                    <span style={{ color: getRiskColor(emp.risk.risk_level), fontWeight: 600 }}>
                      {emp.risk.risk_level} BURNOUT RISK
                    </span>
                  </div>
                  <span className="prob-value">{(emp.risk.risk_probability * 100).toFixed(0)}%</span>
                </div>

                {emp.risk.workload_stats && (
                  <div className="workload-stats-row">
                    <div className="wl-stat">
                      <span className="wl-label">Load</span>
                      <span className="wl-val" style={{ color: getRiskColor(emp.risk.risk_level) }}>
                        {emp.risk.workload_stats.workload_ratio.toFixed(0)}%
                      </span>
                    </div>
                    <div className="wl-stat">
                      <span className="wl-label">Active Tasks</span>
                      <span className="wl-val">{emp.risk.workload_stats.active_tasks}</span>
                    </div>
                    <div className="wl-stat">
                      <span className="wl-label">Overdue</span>
                      <span className="wl-val" style={{ color: emp.risk.workload_stats.overdue_tasks > 0 ? 'var(--error)' : 'inherit' }}>
                        {emp.risk.workload_stats.overdue_tasks}
                      </span>
                    </div>
                  </div>
                )}

                {emp.risk.recommendation && (
                  <div className="emp-recommendation">
                    <BrainCircuit size={14} className="rec-icon" />
                    <p>{emp.risk.recommendation}</p>
                  </div>
                )}

                <ul className="factors-list">
                  {emp.risk.contributing_factors && emp.risk.contributing_factors.slice(0, 3).map((factor: string, i: number) => (
                    <li key={i}>{factor}</li>
                  ))}
                </ul>
              </div>
            )}

            {!emp.risk && (
              <div className="burnout-insights empty">
                <button
                  className="analyze-button"
                  onClick={async () => {
                    await api.post(`/employee-risk/analyze/${emp.id}`);
                    fetchEmployees();
                  }}
                >
                  <BrainCircuit size={16} />
                  Analyze Workload Risk
                </button>
              </div>
            )}

            {/* Phase 6: Manager/Admin — Employee History toggle */}
            {isManager && (
              <>
                <button
                  className="analyze-button"
                  style={{ marginTop: '0.25rem', width: '100%', justifyContent: 'center' }}
                  onClick={() => toggleEmpHistory(emp.id)}
                  id={`hist-${emp.id}`}
                >
                  <Activity size={14} />
                  {empHistoryOpen === emp.id ? 'Hide' : 'View'} Work History
                  {empHistoryOpen === emp.id ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </button>

                {empHistoryOpen === emp.id && (
                  <div className="emp-history-inline">
                    {empHistoryLoading === emp.id ? (
                      <div className="activity-loading">Loading...</div>
                    ) : !empHistories[emp.id] ? (
                      <div className="activity-empty">No history available.</div>
                    ) : (
                      <>
                        {/* Projects */}
                        <div className="hist-mini-title">Projects ({empHistories[emp.id].projects?.length || 0})</div>
                        {(empHistories[emp.id].projects || []).length === 0 ? (
                          <div className="activity-empty">None</div>
                        ) : (empHistories[emp.id].projects || []).slice(0, 3).map((p: any) => (
                          <div key={p.id} className="hist-mini-row">
                            <span>{p.name}</span>
                            <span className={`hist-badge ${p.status}`}>{p.status.replace('_', ' ')}</span>
                          </div>
                        ))}

                        {/* Task summary */}
                        <div className="hist-mini-title" style={{ marginTop: '0.65rem' }}>Tasks</div>
                        <div className="hist-mini-stats">
                          {(['todo', 'in_progress', 'done', 'overdue'] as string[]).map(s => {
                            const lst = s === 'overdue' ? (empHistories[emp.id].tasks?.overdue || []) : (empHistories[emp.id].tasks?.[s] || []);
                            return lst.length > 0 ? (
                              <span key={s} className={getStatusBadgeClass(s)}>{s.replace('_', ' ')}: {lst.length}</span>
                            ) : null;
                          })}
                        </div>

                        {/* Issues */}
                        {(empHistories[emp.id].issues || []).length > 0 && (
                          <>
                            <div className="hist-mini-title" style={{ marginTop: '0.65rem' }}>
                              Issues ({empHistories[emp.id].issues.length})
                            </div>
                            {empHistories[emp.id].issues.slice(0, 2).map((iss: any) => (
                              <div key={iss.id} className="hist-mini-row">
                                <span>{iss.title}</span>
                                <span className={`hist-badge ${iss.status === 'resolved' ? 'done' : 'todo'}`}>{iss.status}</span>
                              </div>
                            ))}
                          </>
                        )}
                      </>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default Employees;
