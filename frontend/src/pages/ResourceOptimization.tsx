import React, { useEffect, useState } from 'react';
import {
  Users, ArrowRight, AlertTriangle, CheckCircle, BarChart3,
  RefreshCw, ChevronDown, ChevronUp, Zap, Clock
} from 'lucide-react';
import api from '../services/api';
import './ResourceOptimization.css';

interface EmployeeLoad {
  employee_id: string;
  name: string;
  role: string;
  specialization: string;
  weekly_capacity: number;
  assigned_hours: number;
  workload_ratio: number;
  available_hours: number;
  burnout_risk: string;
  is_overloaded: boolean;
  is_available: boolean;
}

interface Suggestion {
  id: string;
  task_title: string;
  task_hours: number;
  task_priority: string;
  from_employee_name: string;
  employee_name: string;
  reason: string;
  expectedImpact: string;
  from_employee: { current_workload: number; projected_workload: number; current_hours: number; projected_hours: number };
  to_employee: { current_workload: number; projected_workload: number; current_hours: number; projected_hours: number };
  skill_match: boolean;
  status: string;
}

interface OptimResult {
  project_id: string;
  project_name: string;
  summary: {
    total_employees: number;
    overloaded_count: number;
    available_count: number;
    avg_workload_percent: number;
    suggestions_count: number;
  };
  employee_workload_summary: EmployeeLoad[];
  reallocation_suggestions: Suggestion[];
  has_reallocations: boolean;
  message: string;
}

interface Project {
  id: string;
  name: string;
}

const getWorkloadColor = (ratio: number) => {
  if (ratio > 100) return '#ef4444';
  if (ratio > 80) return '#f59e0b';
  return '#10b981';
};

const ResourceOptimization: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>('');
  const [result, setResult] = useState<OptimResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState<string | null>(null);
  const [expandedEmployee, setExpandedEmployee] = useState<string | null>(null);

  useEffect(() => {
    api.get('/projects/').then(res => {
      setProjects(res.data);
      if (res.data.length > 0) setSelectedProject(res.data[0].id);
    }).catch(console.error);
  }, []);

  const runOptimization = async () => {
    if (!selectedProject) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await api.get(`/resource-optimization/${selectedProject}`);
      setResult(res.data);
    } catch (err) {
      console.error('Optimization failed', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedProject) runOptimization();
  }, [selectedProject]);

  const applyAllocation = async (allocationId: string) => {
    setApplying(allocationId);
    try {
      await api.post(`/resource-optimization/apply/${allocationId}`);
      runOptimization(); // refresh
    } catch (err) {
      console.error('Apply failed', err);
    } finally {
      setApplying(null);
    }
  };

  return (
    <div className="optim-page">
      <div className="page-header flex-between">
        <div>
          <h1>Resource Optimization</h1>
          <p>AI-suggested task reallocations to balance team workload and improve capacity utilization</p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <select
            className="project-select"
            value={selectedProject}
            onChange={e => setSelectedProject(e.target.value)}
          >
            {projects.map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <button className="primary-button" onClick={runOptimization} disabled={loading}>
            <RefreshCw size={14} style={{ display: 'inline', marginRight: '0.4rem' }} />
            {loading ? 'Analyzing…' : 'Re-Analyze'}
          </button>
        </div>
      </div>

      {loading && (
        <div className="loading-state">Analyzing team workload and computing optimal reallocations…</div>
      )}

      {!loading && result && (
        <>
          {/* Summary Cards */}
          <div className="optim-summary-grid">
            <div className="summary-card glass-panel">
              <Users size={24} className="summary-icon" />
              <div>
                <p className="summary-label">Total Team</p>
                <h3>{result.summary.total_employees}</h3>
              </div>
            </div>
            <div className="summary-card glass-panel">
              <AlertTriangle size={24} className="summary-icon error" />
              <div>
                <p className="summary-label">Overloaded</p>
                <h3 className="text-error">{result.summary.overloaded_count}</h3>
              </div>
            </div>
            <div className="summary-card glass-panel">
              <CheckCircle size={24} className="summary-icon success" />
              <div>
                <p className="summary-label">Available</p>
                <h3 className="text-success">{result.summary.available_count}</h3>
              </div>
            </div>
            <div className="summary-card glass-panel">
              <BarChart3 size={24} className="summary-icon warning" />
              <div>
                <p className="summary-label">Avg Workload</p>
                <h3 style={{ color: getWorkloadColor(result.summary.avg_workload_percent) }}>
                  {result.summary.avg_workload_percent.toFixed(1)}%
                </h3>
              </div>
            </div>
            <div className="summary-card glass-panel">
              <Zap size={24} className="summary-icon primary" />
              <div>
                <p className="summary-label">Suggestions</p>
                <h3>{result.summary.suggestions_count}</h3>
              </div>
            </div>
          </div>

          {/* Team Workload Table */}
          <div className="section-block glass-panel">
            <h2>Team Workload Overview</h2>
            <div className="workload-table-wrap">
              <table className="workload-table">
                <thead>
                  <tr>
                    <th>Team Member</th>
                    <th>Role</th>
                    <th>Specialization</th>
                    <th>Assigned</th>
                    <th>Capacity</th>
                    <th>Load %</th>
                    <th>Burnout</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {result.employee_workload_summary.map(emp => (
                    <tr
                      key={emp.employee_id}
                      className={emp.is_overloaded ? 'row-overloaded' : emp.is_available ? 'row-available' : ''}
                      onClick={() => setExpandedEmployee(expandedEmployee === emp.employee_id ? null : emp.employee_id)}
                      style={{ cursor: 'pointer' }}
                    >
                      <td>
                        <div className="emp-name-cell">
                          {expandedEmployee === emp.employee_id ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                          <strong>{emp.name}</strong>
                        </div>
                      </td>
                      <td>{emp.role}</td>
                      <td><span className="spec-tag">{emp.specialization}</span></td>
                      <td>{emp.assigned_hours.toFixed(1)}h</td>
                      <td>{emp.weekly_capacity.toFixed(0)}h</td>
                      <td>
                        <div className="load-bar-cell">
                          <div className="load-bar">
                            <div
                              className="load-fill"
                              style={{
                                width: `${Math.min(emp.workload_ratio, 100)}%`,
                                background: getWorkloadColor(emp.workload_ratio),
                              }}
                            />
                          </div>
                          <span style={{ color: getWorkloadColor(emp.workload_ratio), fontWeight: 600 }}>
                            {emp.workload_ratio.toFixed(0)}%
                          </span>
                        </div>
                      </td>
                      <td>
                        <span className={`risk-badge risk-${emp.burnout_risk.toLowerCase()}`}>
                          {emp.burnout_risk}
                        </span>
                      </td>
                      <td>
                        {emp.is_overloaded
                          ? <span className="status-pill overloaded">⚠ Overloaded</span>
                          : emp.is_available
                            ? <span className="status-pill available">✓ Available</span>
                            : <span className="status-pill balanced">Balanced</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Reallocation Suggestions */}
          <div className="section-block">
            <h2>
              <Zap size={20} style={{ display: 'inline', marginRight: '0.5rem', color: '#6366f1' }} />
              Suggested Reallocations
            </h2>
            {result.has_reallocations ? (
              <div className="suggestions-list">
                {result.reallocation_suggestions.map(s => (
                  <div key={s.id} className="suggestion-card glass-panel">
                    <div className="suggestion-header">
                      <div>
                        <h3 className="suggestion-task">{s.task_title}</h3>
                        <div className="suggestion-meta">
                          <span><Clock size={13} /> {s.task_hours.toFixed(1)}h estimated</span>
                          <span className={`priority-tag prio-${s.task_priority}`}>{s.task_priority}</span>
                          {s.skill_match && <span className="skill-match-tag">✓ Skill Match</span>}
                        </div>
                      </div>
                      <button
                        className="primary-button"
                        onClick={() => applyAllocation(s.id)}
                        disabled={applying === s.id || s.status === 'applied'}
                        style={{ padding: '0.45rem 1rem', fontSize: '0.82rem' }}
                      >
                        {s.status === 'applied' ? '✓ Applied' : applying === s.id ? 'Applying…' : 'Apply'}
                      </button>
                    </div>

                    <div className="realloc-flow">
                      <div className="emp-box overloaded-emp">
                        <strong>{s.from_employee_name}</strong>
                        <span className="workload-change">
                          {s.from_employee?.current_workload?.toFixed(0) ?? '?'}%
                          → {s.from_employee?.projected_workload?.toFixed(0) ?? '?'}%
                        </span>
                        <span className="hours-change">
                          {s.from_employee?.current_hours?.toFixed(1) ?? '?'}h
                          → {s.from_employee?.projected_hours?.toFixed(1) ?? '?'}h
                        </span>
                      </div>
                      <ArrowRight size={20} className="arrow-icon" />
                      <div className="emp-box available-emp">
                        <strong>{s.employee_name}</strong>
                        <span className="workload-change">
                          {s.to_employee?.current_workload?.toFixed(0) ?? '?'}%
                          → {s.to_employee?.projected_workload?.toFixed(0) ?? '?'}%
                        </span>
                        <span className="hours-change">
                          {s.to_employee?.current_hours?.toFixed(1) ?? '?'}h
                          → {s.to_employee?.projected_hours?.toFixed(1) ?? '?'}h
                        </span>
                      </div>
                    </div>

                    <div className="suggestion-reason">
                      <strong>Why:</strong> {s.reason}
                    </div>
                    <div className="suggestion-impact">
                      <strong>Impact:</strong> {s.expectedImpact}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="glass-panel no-suggestions">
                <CheckCircle size={32} className="text-success" />
                <p>{result.message}</p>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default ResourceOptimization;
