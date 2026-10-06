import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Users, ArrowRight, AlertTriangle, CheckCircle,
  RefreshCw, ChevronDown, ChevronUp, Zap, Clock, Shield, Sparkles, UserCheck, X, Check, HelpCircle, Scale, Sliders
} from 'lucide-react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
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
  _id?: string;
  task_id?: string;
  task_title: string;
  task_hours: number;
  task_priority: string;
  task_skills?: string[];
  from_employee_id: string;
  from_employee_name: string;
  employee_id: string;
  employee_name: string;
  project_pm_id?: string;
  project_pm_name?: string;
  project_pm_specialization?: string;
  reason: string;
  expectedImpact: string;
  why_checklist?: string[];
  from_employee: {
    id?: string;
    name?: string;
    role?: string;
    specialization?: string;
    current_workload: number;
    projected_workload: number;
    current_hours: number;
    projected_hours: number;
    weekly_capacity?: number;
  };
  to_employee: {
    id?: string;
    name?: string;
    role?: string;
    specialization?: string;
    current_workload: number;
    projected_workload: number;
    current_hours: number;
    projected_hours: number;
    weekly_capacity?: number;
  };
  skill_match: boolean;
  status: string;
}

interface SkillGap {
  gap_id: string;
  task_id?: string;
  task_title?: string;
  task_hours?: number;
  task_priority?: string;
  required_role: string;
  required_skills: string[];
  gap_type: string;
  urgency: string;
  description: string;
}

interface CrossPMOpportunity {
  opportunity_id: string;
  project_id: string;
  project_name: string;
  task_id?: string;
  task_title?: string;
  task_hours?: number;
  candidate_employee_id: string;
  candidate_name: string;
  candidate_role: string;
  candidate_specialization: string;
  candidate_skills: string[];
  home_pm_user_id: string;
  home_pm_name: string;
  current_workload_percent: number;
  available_hours: number;
  relevance_level: string;
  suitability_score: number;
  reasons: string[];
  gap_addressed?: SkillGap;
}

interface PendingCrossPMRequest {
  id: string;
  project_id: string;
  project_name: string;
  requesting_pm_user_id?: string;
  requesting_pm_name: string;
  home_pm_user_id: string;
  home_pm_name?: string;
  candidate_employee_id?: string;
  candidate_name: string;
  candidate_role: string;
  task_title?: string;
  requested_hours?: number;
  status: string;
}

interface OptimResult {
  project_id: string;
  project_name: string;
  project_pm_id?: string;
  project_pm_name?: string;
  project_pm_specialization?: string;
  summary: {
    total_employees: number;
    overloaded_count: number;
    available_count: number;
    avg_workload_percent: number;
    suggestions_count: number;
    gaps_count?: number;
    cross_pm_opportunities_count?: number;
  };
  employee_workload_summary: EmployeeLoad[];
  reallocation_suggestions: Suggestion[];
  project_skill_gaps?: SkillGap[];
  cross_pm_opportunities?: CrossPMOpportunity[];
  pending_cross_pm_requests?: PendingCrossPMRequest[];
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
  const { user } = useAuth();
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>('');
  const [result, setResult] = useState<OptimResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [expandedEmployee, setExpandedEmployee] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Level 1 Proposal Review Modal state
  const [selectedSuggestion, setSelectedSuggestion] = useState<Suggestion | null>(null);

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
    setActionMsg(null);
    try {
      const res = await api.get(`/resource-optimization/${selectedProject}`);
      setResult(res.data);
    } catch (err: any) {
      console.error('Optimization failed', err);
      setActionMsg({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to compute resource optimization.'
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedProject) runOptimization();
  }, [selectedProject]);

  const handleApproveAllocation = async (allocationId: string) => {
    setActionLoading(allocationId);
    try {
      await api.post(`/resource-optimization/apply/${allocationId}`);
      setActionMsg({
        type: 'success',
        text: 'Task reallocation approved and successfully applied!'
      });
      setSelectedSuggestion(null);
      runOptimization();
    } catch (err: any) {
      console.error('Apply failed', err);
      setActionMsg({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to apply reallocation.'
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleRejectAllocation = async (allocationId: string) => {
    setActionLoading(allocationId);
    try {
      await api.post(`/resource-optimization/reject/${allocationId}`);
      setActionMsg({
        type: 'success',
        text: 'Task reallocation recommendation dismissed.'
      });
      setSelectedSuggestion(null);
      runOptimization();
    } catch (err: any) {
      console.error('Reject failed', err);
      setActionMsg({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to reject reallocation.'
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleRequestCrossPM = async (opp: CrossPMOpportunity) => {
    setActionLoading(opp.opportunity_id);
    try {
      let url = `/resource-optimization/request-cross-pm?project_id=${opp.project_id}&candidate_employee_id=${opp.candidate_employee_id}`;
      if (opp.task_id) url += `&task_id=${opp.task_id}`;
      await api.post(url);
      setActionMsg({
        type: 'success',
        text: `Cross-PM allocation requested for ${opp.candidate_name}! Home PM (${opp.home_pm_name}) notified for approval.`
      });
      runOptimization();
    } catch (err: any) {
      console.error('Cross-PM request failed', err);
      setActionMsg({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to request cross-PM resource.'
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleApproveCrossPM = async (reqId: string) => {
    setActionLoading(reqId);
    try {
      await api.post(`/resource-optimization/cross-pm-requests/${reqId}/approve`);
      setActionMsg({
        type: 'success',
        text: 'Cross-PM allocation approved! Employee assigned to project without changing Home PM ownership.'
      });
      runOptimization();
    } catch (err: any) {
      console.error('Cross-PM approval failed', err);
      setActionMsg({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to approve cross-PM allocation.'
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleRejectCrossPM = async (reqId: string) => {
    setActionLoading(reqId);
    try {
      await api.post(`/resource-optimization/cross-pm-requests/${reqId}/reject`);
      setActionMsg({
        type: 'success',
        text: 'Cross-PM allocation request rejected.'
      });
      runOptimization();
    } catch (err: any) {
      console.error('Cross-PM rejection failed', err);
      setActionMsg({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to reject cross-PM allocation.'
      });
    } finally {
      setActionLoading(null);
    }
  };

  const scrollToCrossPM = () => {
    const el = document.getElementById('level3-cross-pm-section');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  return (
    <div className="optim-page">
      {/* Header */}
      <div className="page-header flex-between">
        <div>
          <h1>3-Level Intelligent Resource Optimization</h1>
          <p>
            PM-Centric Reallocation • Project Skill Gap Detection • Cross-PM Resource Discovery • Human Decision Authority
          </p>
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
            <RefreshCw size={14} style={{ display: 'inline', marginRight: '0.4rem' }} className={loading ? 'spin' : ''} />
            {loading ? 'Analyzing…' : 'Re-Analyze'}
          </button>
        </div>
      </div>

      {actionMsg && (
        <div className={`tc-alert ${actionMsg.type === 'success' ? 'tc-alert-success' : 'tc-alert-error'}`} style={{ marginBottom: '16px' }}>
          {actionMsg.type === 'success' ? <CheckCircle size={18} /> : <AlertTriangle size={18} />}
          <span>{actionMsg.text}</span>
        </div>
      )}

      {loading && (
        <div className="loading-state">
          <RefreshCw size={24} className="spin" style={{ marginBottom: '8px', color: '#6366f1' }} />
          <div>Evaluating 3-level workload, skill gaps, and cross-PM resource opportunities…</div>
        </div>
      )}

      {!loading && result && (
        <>
          {/* PM Context Banner */}
          <div className="pm-context-banner glass-panel">
            <div className="pm-context-info">
              <span className="pm-context-badge">Project Scope & Ownership</span>
              <h2 className="pm-context-title">
                PM: {result.project_pm_name || 'Assigned Manager'}
                {result.project_pm_specialization && (
                  <span className="pm-context-spec"> • {result.project_pm_specialization}</span>
                )}
              </h2>
              <p className="pm-context-desc">
                Project: <strong>{result.project_name}</strong> — Recommendations preserve direct line-management team ownership and adhere to the 18-member capacity boundary.
              </p>
            </div>
          </div>

          {/* Summary Metrics */}
          <div className="optim-summary-grid">
            <div className="summary-card glass-panel">
              <Users size={24} className="summary-icon" />
              <div>
                <p className="summary-label">Project Team</p>
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
              <Shield size={24} className="summary-icon warning" />
              <div>
                <p className="summary-label">Detected Gaps</p>
                <h3>{result.summary.gaps_count || 0}</h3>
              </div>
            </div>
            <div className="summary-card glass-panel">
              <Sparkles size={24} className="summary-icon primary" />
              <div>
                <p className="summary-label">Cross-PM Opportunities</p>
                <h3>{result.summary.cross_pm_opportunities_count || 0}</h3>
              </div>
            </div>
          </div>

          {/* LEVEL 1: Internal Team Task Reallocations */}
          <div className="section-block">
            <div className="section-header-row">
              <div>
                <h2>
                  <Zap size={20} style={{ display: 'inline', marginRight: '0.5rem', color: '#6366f1' }} />
                  LEVEL 1 — Internal Team Task Reallocations
                </h2>
                <p className="section-subtitle">
                  PM-owned internal team workload rebalancing. Requires PM review and approval before execution.
                </p>
              </div>
            </div>

            {result.reallocation_suggestions && result.reallocation_suggestions.length > 0 ? (
              <div className="suggestions-list">
                {result.reallocation_suggestions.map(s => (
                  <div key={s.id} className="suggestion-card glass-panel">
                    <div className="pm-owner-tag">
                      <span>PM: {s.project_pm_name || result.project_pm_name} ({s.project_pm_specialization || result.project_pm_specialization || 'Internal Team'})</span>
                      <span className="ownership-badge">Team Resource Reallocation</span>
                    </div>

                    <div className="suggestion-header">
                      <div>
                        <h3 className="suggestion-task">{s.task_title}</h3>
                        <div className="suggestion-meta">
                          <span><Clock size={13} /> {s.task_hours.toFixed(1)}h estimated</span>
                          <span className={`priority-tag prio-${s.task_priority}`}>{s.task_priority} Priority</span>
                          {s.skill_match && <span className="skill-match-tag">✓ Skill Match</span>}
                        </div>
                      </div>

                      <div className="suggestion-actions" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        {s.status === 'applied' ? (
                          <span className="status-pill available">✓ Applied & Allocated</span>
                        ) : s.status === 'rejected' ? (
                          <span className="status-pill balanced">✕ Dismissed</span>
                        ) : (
                          <>
                            <button
                              className="outline-button"
                              style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.8rem', padding: '0.4rem 0.75rem', borderColor: 'rgba(139, 92, 246, 0.4)', color: '#c084fc' }}
                              onClick={() => {
                                navigate(`/dashboard/what-if-simulation?projectId=${selectedProject}&scenarioType=TASK_REALLOCATION`);
                              }}
                            >
                              <Sliders size={13} />
                              Simulate Scenario
                            </button>
                            <button
                              className="secondary-button"
                              style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.8rem', padding: '0.4rem 0.75rem' }}
                              onClick={() => {
                                const desc = `Reallocate task '${s.task_title}' (${s.task_hours}h) from ${s.from_employee_name} to ${s.employee_name}. Reason: ${s.reason}`;
                                navigate(`/dashboard/decisions?projectId=${selectedProject}&title=${encodeURIComponent(`Internal Reallocation: ${s.task_title}`)}&type=RESOURCE_REALLOCATION&description=${encodeURIComponent(desc)}`);
                              }}
                            >
                              <Scale size={13} />
                              Record Decision
                            </button>
                            <button
                              className="primary-button review-btn"
                              onClick={() => setSelectedSuggestion(s)}
                            >
                              Review Recommendation
                            </button>
                          </>
                        )}
                      </div>
                    </div>

                    <div className="realloc-flow">
                      <div className="emp-box overloaded-emp">
                        <span className="emp-box-label">Overloaded Member</span>
                        <strong>{s.from_employee_name}</strong>
                        <span className="emp-box-role">
                          {s.from_employee?.role || 'Senior Engineer'}
                          {s.from_employee?.specialization ? ` • ${s.from_employee?.specialization}` : ''}
                        </span>
                        <div className="emp-box-stats">
                          <span>Current: <strong className="text-error">{s.from_employee?.current_workload?.toFixed(0) ?? '?'}%</strong></span>
                          <span>Proposed: <strong>{s.from_employee?.projected_workload?.toFixed(0) ?? '?'}%</strong></span>
                        </div>
                      </div>

                      <div className="arrow-wrap">
                        <ArrowRight size={22} className="arrow-icon" />
                        <span className="arrow-label">{s.task_hours}h</span>
                      </div>

                      <div className="emp-box available-emp">
                        <span className="emp-box-label">Recommended Member</span>
                        <strong>{s.employee_name}</strong>
                        <span className="emp-box-role">
                          {s.to_employee?.role || 'Engineer'}
                          {s.to_employee?.specialization ? ` • ${s.to_employee?.specialization}` : ''}
                        </span>
                        <div className="emp-box-stats">
                          <span>Current: <strong>{s.to_employee?.current_workload?.toFixed(0) ?? '?'}%</strong></span>
                          <span>Proposed: <strong className="text-success">{s.to_employee?.projected_workload?.toFixed(0) ?? '?'}%</strong></span>
                        </div>
                      </div>
                    </div>

                    <div className="recommendation-narrative">
                      <p>
                        <strong>NexusAI Recommendation:</strong> {s.reason}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="glass-panel no-suggestions">
                <CheckCircle size={32} className="text-success" />
                <div>
                  <strong>Workload Balanced Within PM Team</strong>
                  <p>No internal team members are currently overloaded or requiring task reallocations.</p>
                </div>
              </div>
            )}
          </div>

          {/* LEVEL 2: Project Skill & Role Gaps */}
          <div className="section-block glass-panel" style={{ borderLeft: '4px solid #f59e0b' }}>
            <div className="section-header-row">
              <div>
                <h2>
                  <Shield size={20} style={{ display: 'inline', marginRight: '0.5rem', color: '#f59e0b' }} />
                  LEVEL 2 — Project Skill & Role Gaps ({result.project_skill_gaps?.length || 0})
                </h2>
                <p className="section-subtitle">
                  Detects missing specializations or skills for project deliverables and connects directly to cross-PM candidate discovery.
                </p>
              </div>
            </div>

            {result.project_skill_gaps && result.project_skill_gaps.length > 0 ? (
              <div className="gaps-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '14px', marginTop: '14px' }}>
                {result.project_skill_gaps.map((gap) => (
                  <div key={gap.gap_id} className="gap-card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <strong style={{ color: '#f8fafc', fontSize: '1rem' }}>{gap.required_role}</strong>
                      <span className={`priority-tag prio-${gap.urgency.toLowerCase()}`}>{gap.urgency} Urgency</span>
                    </div>
                    {gap.task_title && (
                      <div className="gap-task-info">
                        <span>Task: <strong>{gap.task_title}</strong></span>
                        {gap.task_hours && <span> • {gap.task_hours}h</span>}
                      </div>
                    )}
                    <p style={{ margin: '8px 0', fontSize: '0.85rem', color: '#94a3b8' }}>{gap.description}</p>
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '12px' }}>
                      {gap.required_skills?.map(s => (
                        <span key={s} className="skill-match-tag">{s}</span>
                      ))}
                    </div>

                    <div className="gap-action-bridge">
                      <div className="gap-bridge-text">
                        <span>Current Team Availability:</span>
                        <strong className="text-warning"> No suitable internal resource found</strong>
                      </div>
                      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                        <button
                          className="outline-button"
                          style={{ fontSize: '0.8rem', padding: '0.35rem 0.65rem', display: 'flex', alignItems: 'center', gap: '4px' }}
                          onClick={() => {
                            const desc = `Skill Gap detected for task '${gap.task_title || gap.required_role}'. Required role: ${gap.required_role}, Skills: ${gap.required_skills?.join(', ')}. ${gap.description}`;
                            navigate(`/dashboard/decisions?projectId=${selectedProject}&title=${encodeURIComponent(`Skill Gap Decision: ${gap.required_role}`)}&type=SPRINT_RESCOPE&description=${encodeURIComponent(desc)}`);
                          }}
                        >
                          <Scale size={13} />
                          Record Decision
                        </button>
                        <button className="secondary-button view-cross-btn" onClick={scrollToCrossPM}>
                          <Sparkles size={14} style={{ marginRight: '4px' }} />
                          View Cross-PM Opportunities
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="no-gaps-box">
                <CheckCircle size={20} className="text-success" style={{ marginRight: '8px' }} />
                <span>All required project roles and skill domains are adequately covered by the active team.</span>
              </div>
            )}
          </div>

          {/* LEVEL 3: Cross-PM Resource Opportunities */}
          <div id="level3-cross-pm-section" className="section-block glass-panel" style={{ borderLeft: '4px solid #8b5cf6' }}>
            <div className="section-header-row">
              <div>
                <h2>
                  <Sparkles size={20} style={{ display: 'inline', marginRight: '0.5rem', color: '#8b5cf6' }} />
                  LEVEL 3 — Cross-PM Resource Opportunities ({result.cross_pm_opportunities?.length || 0})
                </h2>
                <p className="section-subtitle">
                  Intelligent candidate discovery from other PM teams. Candidate's Home PM line-management ownership is strictly preserved.
                </p>
              </div>
            </div>

            {result.cross_pm_opportunities && result.cross_pm_opportunities.length > 0 ? (
              <div className="suggestions-list" style={{ marginTop: '14px' }}>
                {result.cross_pm_opportunities.map(opp => (
                  <div key={opp.opportunity_id} className="suggestion-card glass-panel cross-pm-card">
                    <div className="cross-pm-card-header">
                      <div>
                        <div className="candidate-role-badge">{opp.candidate_role}</div>
                        <h3 className="candidate-name">
                          {opp.candidate_name}
                        </h3>
                        <div className="home-pm-pill">
                          <span>Home PM: <strong>{opp.home_pm_name}</strong></span>
                          <span className="ownership-tag">Direct Ownership Preserved</span>
                        </div>
                      </div>

                      <div className="candidate-score-badge">
                        <span className="score-num">{opp.suitability_score || 91}</span>
                        <span className="score-denom">/100</span>
                        <span className="score-label">Match Score</span>
                      </div>
                    </div>

                    <div className="candidate-metrics-row">
                      <div className="metric-pill">
                        <span>Workload:</span>
                        <strong style={{ color: getWorkloadColor(opp.current_workload_percent) }}>{opp.current_workload_percent}%</strong>
                      </div>
                      <div className="metric-pill">
                        <span>Available Bandwidth:</span>
                        <strong className="text-success">{opp.available_hours}h</strong>
                      </div>
                      <div className="metric-pill">
                        <span>Relevance:</span>
                        <span className={`priority-tag prio-${opp.relevance_level.toLowerCase()}`}>{opp.relevance_level}</span>
                      </div>
                      {opp.task_title && (
                        <div className="metric-pill task-target">
                          <span>Target Task:</span>
                          <strong>{opp.task_title} ({opp.task_hours || 16}h)</strong>
                        </div>
                      )}
                    </div>

                    <div className="candidate-reasons-box">
                      <span className="reasons-title">Why Recommended?</span>
                      <ul>
                        {opp.reasons.map((r, i) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    </div>

                    <div className="cross-pm-footer">
                      <span className="cross-pm-notice">
                        Submitting creates a <code>CROSS_PM_RESOURCE_REQUESTED</code> notification requiring Home PM ({opp.home_pm_name}) approval.
                      </span>
                      <button
                        className="primary-button request-cross-btn"
                        onClick={() => handleRequestCrossPM(opp)}
                        disabled={actionLoading === opp.opportunity_id}
                      >
                        <UserCheck size={14} style={{ marginRight: '6px' }} />
                        {actionLoading === opp.opportunity_id ? 'Requesting…' : 'Request Resource'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-cross-pm-box">
                <HelpCircle size={28} className="empty-cross-icon" />
                <div className="empty-cross-content">
                  <h4>No Suitable Cross-PM Resources Currently Available</h4>
                  <p>NexusAI evaluated authorized cross-PM candidates based on multi-factor criteria:</p>
                  <ul>
                    <li>✓ Role &amp; Skill alignment for detected project gaps</li>
                    <li>✓ Current Workload &lt; 80% (Available Bandwidth &gt; 20%)</li>
                    <li>✓ Existing project commitments and priority deadlines</li>
                    <li>✓ Cross-PM candidate discovery authority</li>
                  </ul>
                  <p className="empty-cross-foot">No external candidate currently satisfies all allocation criteria.</p>
                </div>
              </div>
            )}
          </div>

          {/* Pending Cross-PM Requests Awaiting Approval */}
          {result.pending_cross_pm_requests && result.pending_cross_pm_requests.length > 0 && (
            <div className="section-block glass-panel" style={{ borderLeft: '4px solid #38bdf8' }}>
              <div className="section-header-row">
                <div>
                  <h2>
                    <Clock size={20} style={{ display: 'inline', marginRight: '0.5rem', color: '#38bdf8' }} />
                    Pending Cross-PM Allocation Requests ({result.pending_cross_pm_requests.length})
                  </h2>
                  <p className="section-subtitle">
                    Awaiting Home PM decision. Human approval is mandatory before any project allocation occurs.
                  </p>
                </div>
              </div>

              <div className="suggestions-list" style={{ marginTop: '14px' }}>
                {result.pending_cross_pm_requests.map(req => {
                  const isHomePm = user && (user.id === req.home_pm_user_id || user.role === 'admin');
                  return (
                    <div key={req.id} className="suggestion-card glass-panel pending-req-card">
                      <div className="suggestion-header">
                        <div>
                          <div className="pending-badge">Pending Approval</div>
                          <h3 className="suggestion-task">{req.candidate_name} <span style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 400 }}>({req.candidate_role})</span></h3>
                          <div className="suggestion-meta">
                            <span>Project: <strong>{req.project_name}</strong></span>
                            <span>Requesting PM: <strong>{req.requesting_pm_name}</strong></span>
                            {req.home_pm_name && <span>Home PM: <strong>{req.home_pm_name}</strong></span>}
                            {req.task_title && <span>Task: {req.task_title}</span>}
                          </div>
                        </div>

                        {isHomePm ? (
                          <div className="pending-decision-actions">
                            <button
                              className="primary-button approve-btn"
                              onClick={() => handleApproveCrossPM(req.id)}
                              disabled={actionLoading === req.id}
                            >
                              <Check size={14} style={{ marginRight: '4px' }} />
                              Approve Allocation
                            </button>
                            <button
                              className="secondary-button reject-btn"
                              onClick={() => handleRejectCrossPM(req.id)}
                              disabled={actionLoading === req.id}
                            >
                              <X size={14} style={{ marginRight: '4px' }} />
                              Reject
                            </button>
                          </div>
                        ) : (
                          <div className="awaiting-pill">
                            <Clock size={14} style={{ marginRight: '4px' }} />
                            Awaiting Home PM Decision
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Team Workload Table (PM Scope) */}
          <div className="section-block glass-panel">
            <h2>Team Workload Overview (PM Scope)</h2>
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
        </>
      )}

      {/* LEVEL 1 RECOMMENDATION REVIEW MODAL */}
      {selectedSuggestion && (
        <div className="modal-backdrop">
          <div className="modal-content review-modal glass-panel">
            <div className="modal-header">
              <div>
                <span className="modal-category">Level 1 Reallocation Proposal</span>
                <h2>Resource Reallocation Review</h2>
              </div>
              <button className="modal-close-btn" onClick={() => setSelectedSuggestion(null)}>
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              <div className="modal-project-task">
                <div className="modal-meta-row">
                  <span>Project:</span>
                  <strong>{result?.project_name}</strong>
                </div>
                <div className="modal-meta-row">
                  <span>Task:</span>
                  <strong>{selectedSuggestion.task_title}</strong>
                  <span className="modal-task-hours">({selectedSuggestion.task_hours}h estimated effort)</span>
                </div>
              </div>

              <div className="modal-comparison-grid">
                {/* CURRENT OWNER */}
                <div className="comparison-col current-owner-col">
                  <div className="col-header text-error">CURRENT OWNER</div>
                  <div className="member-name">{selectedSuggestion.from_employee_name}</div>
                  <div className="member-role">
                    {selectedSuggestion.from_employee?.role || 'Senior Engineer'}
                    {selectedSuggestion.from_employee?.specialization ? ` (${selectedSuggestion.from_employee.specialization})` : ''}
                  </div>
                  <div className="load-stat-box">
                    <div className="stat-line">
                      <span>Workload:</span>
                      <strong className="text-error">{selectedSuggestion.from_employee?.current_workload?.toFixed(0)}%</strong>
                    </div>
                    <div className="stat-line">
                      <span>Assigned Hours:</span>
                      <span>{selectedSuggestion.from_employee?.current_hours?.toFixed(1)}h / {selectedSuggestion.from_employee?.weekly_capacity || 40}h</span>
                    </div>
                    <div className="stat-line projected-line">
                      <span>After Reallocation:</span>
                      <strong className="text-success">{selectedSuggestion.from_employee?.projected_workload?.toFixed(0)}% ({selectedSuggestion.from_employee?.projected_hours?.toFixed(1)}h)</strong>
                    </div>
                  </div>
                </div>

                {/* PROPOSED OWNER */}
                <div className="comparison-col proposed-owner-col">
                  <div className="col-header text-success">PROPOSED OWNER</div>
                  <div className="member-name">{selectedSuggestion.employee_name}</div>
                  <div className="member-role">
                    {selectedSuggestion.to_employee?.role || 'Engineer'}
                    {selectedSuggestion.to_employee?.specialization ? ` (${selectedSuggestion.to_employee.specialization})` : ''}
                  </div>
                  <div className="load-stat-box">
                    <div className="stat-line">
                      <span>Workload:</span>
                      <strong>{selectedSuggestion.to_employee?.current_workload?.toFixed(0)}%</strong>
                    </div>
                    <div className="stat-line">
                      <span>Assigned Hours:</span>
                      <span>{selectedSuggestion.to_employee?.current_hours?.toFixed(1)}h / {selectedSuggestion.to_employee?.weekly_capacity || 40}h</span>
                    </div>
                    <div className="stat-line projected-line">
                      <span>After Allocation:</span>
                      <strong className="text-success">{selectedSuggestion.to_employee?.projected_workload?.toFixed(0)}% ({selectedSuggestion.to_employee?.projected_hours?.toFixed(1)}h)</strong>
                    </div>
                  </div>
                </div>
              </div>

              {/* WHY? Checklist */}
              <div className="modal-why-box">
                <div className="why-title">WHY IS THIS RECOMMENDED?</div>
                <div className="why-list">
                  {selectedSuggestion.why_checklist && selectedSuggestion.why_checklist.length > 0 ? (
                    selectedSuggestion.why_checklist.map((item, idx) => (
                      <div key={idx} className="why-item">{item}</div>
                    ))
                  ) : (
                    <>
                      <div className="why-item">✓ Required skill match ({selectedSuggestion.to_employee?.specialization || 'Engineering'})</div>
                      <div className="why-item">✓ Available capacity bandwidth</div>
                      <div className="why-item">✓ Reduces overloaded engineer workload from {selectedSuggestion.from_employee?.current_workload?.toFixed(0)}% to {selectedSuggestion.from_employee?.projected_workload?.toFixed(0)}%</div>
                      <div className="why-item">✓ Keeps work inside current PM team ({result?.project_pm_name})</div>
                      <div className="why-item">✓ No line-management ownership change</div>
                    </>
                  )}
                </div>
              </div>

              <div className="modal-note">
                NexusAI executes this task reassignment only upon your explicit approval. Direct PM team line-management ownership remains unchanged.
              </div>
            </div>

            <div className="modal-footer">
              <button
                className="secondary-button reject-btn"
                onClick={() => handleRejectAllocation(selectedSuggestion.id)}
                disabled={actionLoading === selectedSuggestion.id}
              >
                <X size={14} style={{ marginRight: '4px' }} />
                Reject Proposal
              </button>
              <button
                className="primary-button approve-btn"
                onClick={() => handleApproveAllocation(selectedSuggestion.id)}
                disabled={actionLoading === selectedSuggestion.id}
              >
                <Check size={14} style={{ marginRight: '4px' }} />
                {actionLoading === selectedSuggestion.id ? 'Allocating…' : 'Approve & Allocate'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ResourceOptimization;
