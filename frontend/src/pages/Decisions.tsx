import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Scale,
  CheckCircle2,
  AlertCircle,
  Clock,
  XCircle,
  PauseCircle,
  Search,
  Plus,
  ShieldAlert,
  BrainCircuit,
  User,
  Calendar,
  X,
  RefreshCw,
  TrendingUp,
  FileCheck,
  Check,
} from 'lucide-react';
import api from '../services/api';
import './Decisions.css';

const DECISION_TYPES = [
  { value: 'ALL', label: 'All Decision Types' },
  { value: 'RESOURCE_REALLOCATION', label: 'Resource Reallocation' },
  { value: 'CROSS_PM_RESOURCE_REQUEST', label: 'Cross-PM Resource Request' },
  { value: 'SCHEDULE_COMPRESSION', label: 'Schedule Compression' },
  { value: 'SPRINT_RESCOPE', label: 'Sprint Rescope' },
  { value: 'BUDGET_INVESTIGATION', label: 'Budget Investigation' },
  { value: 'QUALITY_ESCALATION', label: 'Quality Escalation' },
  { value: 'RISK_MITIGATION', label: 'Risk Mitigation' },
  { value: 'PROJECT_SCOPE_CHANGE', label: 'Project Scope Change' },
  { value: 'OTHER', label: 'Other' },
];

const STATUS_FILTERS = ['ALL', 'PENDING', 'APPROVED', 'REJECTED', 'DEFERRED'];

const Decisions: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [decisions, setDecisions] = useState<any[]>([]);
  const [stats, setStats] = useState<any>({ total: 0, pending: 0, approved: 0, rejected: 0, deferred: 0 });
  const [projects, setProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedProject, setSelectedProject] = useState<string>('ALL');
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL');
  const [selectedType, setSelectedType] = useState<string>('ALL');

  // Active Detail Modal
  const [selectedDecision, setSelectedDecision] = useState<any | null>(null);
  const [actionRationale, setActionRationale] = useState<string>('');
  const [selectedAltId, setSelectedAltId] = useState<string>('');
  const [isSubmittingAction, setIsSubmittingAction] = useState<boolean>(false);
  const [actionError, setActionError] = useState<string>('');

  // Create Decision Modal
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [createProjectId, setCreateProjectId] = useState<string>('');
  const [createType, setCreateType] = useState<string>('RESOURCE_REALLOCATION');
  const [createTitle, setCreateTitle] = useState<string>('');
  const [createDescription, setCreateDescription] = useState<string>('');
  const [createPriority, setCreatePriority] = useState<string>('high');
  const [createSelectedAction, setCreateSelectedAction] = useState<string>('');
  const [createRationale, setCreateRationale] = useState<string>('');
  const [createAlternatives, setCreateAlternatives] = useState<string[]>([
    'Option A: Adopt AI recommended reallocation',
    'Option B: Maintain current baseline allocation',
    'Option C: Defer to next sprint milestone',
  ]);
  const [newAltText, setNewAltText] = useState<string>('');
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [createError, setCreateError] = useState<string>('');

  const fetchDecisionsAndStats = async () => {
    try {
      setLoading(true);
      const [decRes, statsRes, projRes] = await Promise.all([
        api.get('/decisions/'),
        api.get('/decisions/stats'),
        api.get('/projects/'),
      ]);
      setDecisions(decRes.data || []);
      setStats(statsRes.data || { total: 0, pending: 0, approved: 0, rejected: 0, deferred: 0 });
      setProjects(projRes.data || []);

      const qProjectId = searchParams.get('projectId');
      const qTitle = searchParams.get('title');
      const qType = searchParams.get('type');
      const qDesc = searchParams.get('description');

      if (qProjectId) {
        setCreateProjectId(qProjectId);
        if (qTitle) setCreateTitle(qTitle);
        if (qType) setCreateType(qType);
        if (qDesc) setCreateDescription(qDesc);
        setShowCreateModal(true);
      } else if (projRes.data && projRes.data.length > 0 && !createProjectId) {
        setCreateProjectId(projRes.data[0].id || projRes.data[0]._id);
      }
    } catch (err) {
      console.error('Failed to fetch decisions data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDecisionsAndStats();
  }, [searchParams]);

  // Filtered decisions list
  const filteredDecisions = decisions.filter((d) => {
    if (selectedProject !== 'ALL' && d.project_id !== selectedProject) return false;
    if (selectedStatus !== 'ALL' && d.decision_status !== selectedStatus) return false;
    if (selectedType !== 'ALL' && d.decision_type !== selectedType) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchTitle = (d.title || '').toLowerCase().includes(q);
      const matchProj = (d.project_name || '').toLowerCase().includes(q);
      const matchRationale = (d.decision_rationale || '').toLowerCase().includes(q);
      const matchMaker = (d.decision_maker_name || d.created_by_name || '').toLowerCase().includes(q);
      if (!matchTitle && !matchProj && !matchRationale && !matchMaker) return false;
    }
    return true;
  });

  // Open detail modal
  const handleOpenDetail = (d: any) => {
    setSelectedDecision(d);
    setActionRationale(d.decision_rationale || '');
    setActionError('');
    const selAlt = (d.alternatives || []).find((a: any) => a.is_selected);
    setSelectedAltId(selAlt ? selAlt.id : '');
  };

  // Execute decision action (Approve / Reject / Defer)
  const handleDecisionAction = async (action: 'approve' | 'reject' | 'defer') => {
    if (!selectedDecision) return;
    if (!actionRationale || !actionRationale.trim()) {
      setActionError('Human decision rationale is mandatory before finalizing.');
      return;
    }

    setIsSubmittingAction(true);
    setActionError('');
    try {
      const res = await api.post(`/decisions/${selectedDecision.id}/${action}`, {
        rationale: actionRationale.trim(),
        selected_alternative_id: selectedAltId || undefined,
      });
      setSelectedDecision(res.data);
      await fetchDecisionsAndStats();
    } catch (err: any) {
      console.error(`Failed to ${action} decision:`, err);
      setActionError(err.response?.data?.detail || `Failed to ${action} decision`);
    } finally {
      setIsSubmittingAction(false);
    }
  };

  // Submit Create Decision
  const handleCreateDecision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createTitle.trim()) {
      setCreateError('Please enter a decision title.');
      return;
    }
    if (!createProjectId) {
      setCreateError('Please select a project.');
      return;
    }
    if (!createRationale.trim()) {
      setCreateError('Human decision rationale is mandatory.');
      return;
    }

    setIsCreating(true);
    setCreateError('');
    try {
      const alts = createAlternatives.map((alt, idx) => ({
        id: `alt-${idx + 1}`,
        title: alt,
        is_selected: idx === 0,
      }));

      await api.post('/decisions/', {
        project_id: createProjectId,
        decision_type: createType,
        title: createTitle.trim(),
        description: createDescription.trim(),
        priority: createPriority,
        decision_status: 'PENDING',
        selected_action: createSelectedAction.trim() || createAlternatives[0],
        decision_rationale: createRationale.trim(),
        alternatives: alts,
      });

      setShowCreateModal(false);
      setCreateTitle('');
      setCreateDescription('');
      setCreateRationale('');
      setCreateSelectedAction('');
      await fetchDecisionsAndStats();
    } catch (err: any) {
      console.error('Failed to create decision:', err);
      setCreateError(err.response?.data?.detail || 'Failed to record decision');
    } finally {
      setIsCreating(false);
    }
  };

  const handleAddAlternative = () => {
    if (newAltText.trim()) {
      setCreateAlternatives([...createAlternatives, newAltText.trim()]);
      setNewAltText('');
    }
  };

  const handleRemoveAlternative = (index: number) => {
    setCreateAlternatives(createAlternatives.filter((_, idx) => idx !== index));
  };

  const formatDate = (isoStr?: string) => {
    if (!isoStr) return '—';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch {
      return isoStr;
    }
  };

  return (
    <div className="decisions-page">
      {/* HEADER */}
      <div className="decisions-header">
        <div className="decisions-title-area">
          <h1>
            <Scale size={28} className="text-primary" />
            Decision Intelligence & Audit Log
          </h1>
          <p>Traceable management decisions linked to live project intelligence, ML predictions, and human rationale.</p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <button className="btn-view-details" onClick={fetchDecisionsAndStats} title="Refresh Log">
            <RefreshCw size={15} />
            Refresh
          </button>
          <button className="btn-record-decision" onClick={() => setShowCreateModal(true)}>
            <Plus size={18} />
            Record Decision
          </button>
        </div>
      </div>

      {/* STATS SUMMARY GRID */}
      <div className="decisions-stats-grid">
        <div className="stat-card">
          <div className="stat-icon-wrapper stat-icon-total">
            <Scale size={22} />
          </div>
          <div className="stat-info">
            <div className="stat-val">{stats.total || 0}</div>
            <div className="stat-lbl">Total Decisions</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon-wrapper stat-icon-approved">
            <CheckCircle2 size={22} />
          </div>
          <div className="stat-info">
            <div className="stat-val">{stats.approved || 0}</div>
            <div className="stat-lbl">Approved Actions</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon-wrapper stat-icon-pending">
            <Clock size={22} />
          </div>
          <div className="stat-info">
            <div className="stat-val">{stats.pending || 0}</div>
            <div className="stat-lbl">Pending Review</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon-wrapper stat-icon-rejected">
            <XCircle size={22} />
          </div>
          <div className="stat-info">
            <div className="stat-val">{stats.rejected || 0}</div>
            <div className="stat-lbl">Rejected Actions</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon-wrapper stat-icon-deferred">
            <PauseCircle size={22} />
          </div>
          <div className="stat-info">
            <div className="stat-val">{stats.deferred || 0}</div>
            <div className="stat-lbl">Deferred</div>
          </div>
        </div>
      </div>

      {/* FILTER CONTROLS BAR */}
      <div className="decisions-filter-bar">
        <div className="search-input-group">
          <Search size={16} />
          <input
            type="text"
            placeholder="Search by title, project, rationale, or maker..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        {/* Project Filter */}
        <select
          className="filter-select"
          value={selectedProject}
          onChange={(e) => setSelectedProject(e.target.value)}
        >
          <option value="ALL">All Authorized Projects ({projects.length})</option>
          {projects.map((p) => (
            <option key={p.id || p._id} value={p.id || p._id}>
              {p.name}
            </option>
          ))}
        </select>

        {/* Status Filter */}
        <select
          className="filter-select"
          value={selectedStatus}
          onChange={(e) => setSelectedStatus(e.target.value)}
        >
          {STATUS_FILTERS.map((st) => (
            <option key={st} value={st}>
              Status: {st}
            </option>
          ))}
        </select>

        {/* Type Filter */}
        <select
          className="filter-select"
          value={selectedType}
          onChange={(e) => setSelectedType(e.target.value)}
        >
          {DECISION_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
      </div>

      {/* DECISION LOG TABLE */}
      <div className="decisions-table-container">
        {loading ? (
          <div className="empty-decisions">
            <RefreshCw size={24} className="animate-spin" />
            <p>Loading Decision Log & Intelligence...</p>
          </div>
        ) : filteredDecisions.length === 0 ? (
          <div className="empty-decisions">
            <FileCheck size={36} />
            <h3>No Decisions Found</h3>
            <p>No formal management decisions match your filter criteria.</p>
          </div>
        ) : (
          <table className="decisions-table">
            <thead>
              <tr>
                <th>Decision & Project</th>
                <th>Type</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Decision Maker</th>
                <th>Date</th>
                <th>Rationale Snippet</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredDecisions.map((d) => (
                <tr key={d.id || d._id} onClick={() => handleOpenDetail(d)}>
                  <td>
                    <div className="decision-title-cell">{d.title}</div>
                    <div className="decision-desc-cell">{d.project_name}</div>
                  </td>
                  <td>
                    <span className="badge-type">{(d.decision_type || 'OTHER').replace(/_/g, ' ')}</span>
                  </td>
                  <td>
                    <span className={`badge-status status-${(d.decision_status || 'PENDING').toLowerCase()}`}>
                      {d.decision_status === 'APPROVED' && <Check size={12} />}
                      {d.decision_status === 'REJECTED' && <X size={12} />}
                      {d.decision_status === 'PENDING' && <Clock size={12} />}
                      {d.decision_status === 'DEFERRED' && <PauseCircle size={12} />}
                      {d.decision_status}
                    </span>
                  </td>
                  <td>
                    <span className={`badge-priority priority-${(d.priority || 'medium').toLowerCase()}`}>
                      {d.priority}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <User size={14} className="text-secondary" />
                      <span>{d.decision_maker_name || d.created_by_name || 'PM'}</span>
                    </div>
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#94a3b8' }}>
                      <Calendar size={14} />
                      <span>{formatDate(d.decided_at || d.created_at)}</span>
                    </div>
                  </td>
                  <td>
                    <div className="decision-rationale-cell" title={d.decision_rationale || 'No rationale recorded'}>
                      {d.decision_rationale || '—'}
                    </div>
                  </td>
                  <td>
                    <button
                      className="btn-view-details"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenDetail(d);
                      }}
                    >
                      View Details
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ==================================================================== */}
      {/* DETAILED DECISION INTELLIGENCE MODAL */}
      {/* ==================================================================== */}
      {selectedDecision && (
        <div className="modal-backdrop" onClick={() => setSelectedDecision(null)}>
          <div className="decision-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <Scale size={22} className="text-primary" />
                Decision Intelligence Record
              </h2>
              <button className="btn-close-modal" onClick={() => setSelectedDecision(null)}>
                <X size={20} />
              </button>
            </div>

            <div className="modal-body">
              {actionError && (
                <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.4)', color: '#f87171', padding: '0.75rem', borderRadius: '8px', fontSize: '0.875rem' }}>
                  {actionError}
                </div>
              )}

              {/* 1. HEADER META INFO */}
              <div className="decision-section-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.6rem' }}>
                  <div>
                    <h3 style={{ margin: '0 0 0.25rem 0', color: '#fff', fontSize: '1.2rem' }}>{selectedDecision.title}</h3>
                    <span style={{ color: '#818cf8', fontWeight: 600, fontSize: '0.875rem' }}>
                      Project: {selectedDecision.project_name}
                    </span>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <span className={`badge-status status-${(selectedDecision.decision_status || 'PENDING').toLowerCase()}`}>
                      {selectedDecision.decision_status}
                    </span>
                    <span className={`badge-priority priority-${(selectedDecision.priority || 'medium').toLowerCase()}`}>
                      {selectedDecision.priority}
                    </span>
                  </div>
                </div>
                {selectedDecision.description && (
                  <p style={{ margin: '0.5rem 0 0 0', color: '#94a3b8', fontSize: '0.875rem', lineHeight: 1.4 }}>
                    {selectedDecision.description}
                  </p>
                )}
                <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', marginTop: '0.85rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(255, 255, 255, 0.06)', fontSize: '0.8rem', color: '#94a3b8' }}>
                  <div><strong>Created By:</strong> {selectedDecision.created_by_name || 'PM'} ({formatDate(selectedDecision.created_at)})</div>
                  {selectedDecision.decided_at && (
                    <div><strong>Decided By:</strong> {selectedDecision.decision_maker_name || 'PM'} ({formatDate(selectedDecision.decided_at)})</div>
                  )}
                  <div><strong>Type:</strong> {(selectedDecision.decision_type || 'OTHER').replace(/_/g, ' ')}</div>
                </div>
              </div>

              {/* 2. WHAT NEXUSAI RECOMMENDED */}
              {selectedDecision.recommendation_summary && (
                <div className="decision-section-card">
                  <div className="section-header-title">
                    <BrainCircuit size={16} />
                    What NexusAI Recommended
                  </div>
                  <div className="rec-callout-box">
                    <div className="rec-callout-title">{selectedDecision.recommendation_summary.title}</div>
                    <div className="rec-callout-action">
                      <strong>Action: </strong> {selectedDecision.recommendation_summary.suggested_action}
                    </div>
                    {selectedDecision.recommendation_summary.expected_impact && (
                      <div style={{ color: '#a5b4fc', fontSize: '0.8rem', marginTop: '0.35rem' }}>
                        <strong>Expected Impact: </strong> {selectedDecision.recommendation_summary.expected_impact}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* 3. OBSERVED FACTS & ML PREDICTIONS */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1rem' }}>
                {/* Facts */}
                <div className="decision-section-card">
                  <div className="section-header-title">
                    <AlertCircle size={16} />
                    Observed Facts at Decision Time
                  </div>
                  {selectedDecision.observed_facts && selectedDecision.observed_facts.length > 0 ? (
                    <div className="facts-tag-grid">
                      {selectedDecision.observed_facts.map((f: any, idx: number) => (
                        <div key={idx} className="fact-tag">
                          <strong>{f.category || 'Metric'}:</strong> {f.factor || f.fact || JSON.stringify(f)}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p style={{ color: '#64748b', fontSize: '0.85rem', margin: 0 }}>No specific risk factors flagged at creation time.</p>
                  )}
                </div>

                {/* ML Predictions Snapshot */}
                {selectedDecision.prediction_summary && (
                  <div className="decision-section-card">
                    <div className="section-header-title">
                      <TrendingUp size={16} />
                      ML Prediction Context
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem', fontSize: '0.85rem' }}>
                      <div style={{ background: 'rgba(15, 23, 42, 0.8)', padding: '0.5rem', borderRadius: '6px' }}>
                        <span style={{ color: '#94a3b8' }}>Risk Level: </span>
                        <strong style={{ color: '#f87171' }}>{selectedDecision.prediction_summary.risk_class || 'LOW'}</strong>
                      </div>
                      <div style={{ background: 'rgba(15, 23, 42, 0.8)', padding: '0.5rem', borderRadius: '6px' }}>
                        <span style={{ color: '#94a3b8' }}>Health Score: </span>
                        <strong style={{ color: '#4ade80' }}>{selectedDecision.prediction_summary.health_score || '85'}/100</strong>
                      </div>
                      <div style={{ background: 'rgba(15, 23, 42, 0.8)', padding: '0.5rem', borderRadius: '6px' }}>
                        <span style={{ color: '#94a3b8' }}>Estimated Delay: </span>
                        <strong style={{ color: '#fb923c' }}>{selectedDecision.prediction_summary.delay_days || 0} days</strong>
                      </div>
                      <div style={{ background: 'rgba(15, 23, 42, 0.8)', padding: '0.5rem', borderRadius: '6px' }}>
                        <span style={{ color: '#94a3b8' }}>Est. Overrun: </span>
                        <strong style={{ color: '#e2e8f0' }}>₹{(selectedDecision.prediction_summary.budget_overrun_amount || 0).toLocaleString()}</strong>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* 4. ALTERNATIVES CONSIDERED */}
              {selectedDecision.alternatives && selectedDecision.alternatives.length > 0 && (
                <div className="decision-section-card">
                  <div className="section-header-title">
                    <FileCheck size={16} />
                    Alternatives Considered
                  </div>
                  <div className="alternatives-container">
                    {selectedDecision.alternatives.map((alt: any) => (
                      <div
                        key={alt.id}
                        className={`alt-option-card ${selectedAltId === alt.id || alt.is_selected ? 'selected' : ''}`}
                        onClick={() => setSelectedAltId(alt.id)}
                      >
                        <input
                          type="radio"
                          name="decision-alt"
                          checked={selectedAltId === alt.id || alt.is_selected}
                          onChange={() => setSelectedAltId(alt.id)}
                          className="alt-radio"
                        />
                        <div>
                          <div className="alt-title">{alt.title}</div>
                          {alt.description && <div className="alt-desc">{alt.description}</div>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 5. HUMAN MANAGEMENT DECISION & RATIONALE */}
              <div className="human-decision-box">
                <div className="human-decision-header">
                  <div className="section-header-title" style={{ color: '#fff', margin: 0 }}>
                    <ShieldAlert size={16} className="text-primary" />
                    Human Management Decision & Rationale
                  </div>
                  <span className={`badge-status status-${(selectedDecision.decision_status || 'PENDING').toLowerCase()}`}>
                    Status: {selectedDecision.decision_status}
                  </span>
                </div>

                <div style={{ marginBottom: '0.75rem' }}>
                  <label style={{ display: 'block', color: '#94a3b8', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                    DECISION RATIONALE (HUMAN-ENTERED):
                  </label>
                  <textarea
                    className="rationale-textarea"
                    placeholder="Enter the justification and rationale for this management decision..."
                    value={actionRationale}
                    onChange={(e) => setActionRationale(e.target.value)}
                  />
                </div>

                {/* ACTION BUTTONS (FOR PENDING OR DEFERRED) */}
                <div className="decision-action-buttons">
                  <button
                    type="button"
                    className="btn-action-approve"
                    disabled={isSubmittingAction}
                    onClick={() => handleDecisionAction('approve')}
                  >
                    <Check size={16} />
                    {isSubmittingAction ? 'Processing…' : 'Approve Decision'}
                  </button>
                  <button
                    type="button"
                    className="btn-action-reject"
                    disabled={isSubmittingAction}
                    onClick={() => handleDecisionAction('reject')}
                  >
                    <X size={16} />
                    {isSubmittingAction ? 'Processing…' : 'Reject Decision'}
                  </button>
                  <button
                    type="button"
                    className="btn-action-defer"
                    disabled={isSubmittingAction}
                    onClick={() => handleDecisionAction('defer')}
                  >
                    <PauseCircle size={16} />
                    {isSubmittingAction ? 'Processing…' : 'Defer Decision'}
                  </button>
                </div>
              </div>

              {/* 6. AUDIT TRAIL */}
              {selectedDecision.audit_trail && selectedDecision.audit_trail.length > 0 && (
                <div className="decision-section-card">
                  <div className="section-header-title">
                    <Clock size={16} />
                    Audit Trail & History
                  </div>
                  <div className="audit-timeline">
                    {selectedDecision.audit_trail.map((entry: any, idx: number) => (
                      <div key={idx} className="audit-item">
                        <div>
                          <strong>{entry.action}</strong> by {entry.performed_by_name || 'User'}
                        </div>
                        {entry.notes && <div style={{ color: '#cbd5e1', marginTop: '0.15rem' }}>{entry.notes}</div>}
                        <div className="audit-timestamp">{formatDate(entry.timestamp)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* RECORD DECISION MODAL */}
      {/* ==================================================================== */}
      {showCreateModal && (
        <div className="modal-backdrop" onClick={() => setShowCreateModal(false)}>
          <div className="decision-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>
                <Plus size={20} className="text-primary" />
                Record Formal Management Decision
              </h2>
              <button className="btn-close-modal" onClick={() => setShowCreateModal(false)}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreateDecision} className="modal-body">
              {createError && (
                <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.4)', color: '#f87171', padding: '0.75rem', borderRadius: '8px', fontSize: '0.875rem' }}>
                  {createError}
                </div>
              )}

              {/* Project & Type */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div>
                  <label style={{ display: 'block', color: '#94a3b8', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                    TARGET PROJECT *
                  </label>
                  <select
                    className="filter-select"
                    style={{ width: '100%' }}
                    value={createProjectId}
                    onChange={(e) => setCreateProjectId(e.target.value)}
                    required
                  >
                    <option value="">Select Project...</option>
                    {projects.map((p) => (
                      <option key={p.id || p._id} value={p.id || p._id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', color: '#94a3b8', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                    DECISION CATEGORY *
                  </label>
                  <select
                    className="filter-select"
                    style={{ width: '100%' }}
                    value={createType}
                    onChange={(e) => setCreateType(e.target.value)}
                  >
                    {DECISION_TYPES.filter((t) => t.value !== 'ALL').map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Title & Priority */}
              <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1rem' }}>
                <div>
                  <label style={{ display: 'block', color: '#94a3b8', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                    DECISION TITLE *
                  </label>
                  <input
                    type="text"
                    className="search-input-group"
                    style={{ width: '100%', background: 'rgba(15, 23, 42, 0.7)', border: '1px solid rgba(255, 255, 255, 0.1)', padding: '0.55rem 0.75rem', borderRadius: '6px', color: '#fff' }}
                    placeholder="e.g. Approve Schedule Compression for Milestone Alpha"
                    value={createTitle}
                    onChange={(e) => setCreateTitle(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label style={{ display: 'block', color: '#94a3b8', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                    PRIORITY
                  </label>
                  <select
                    className="filter-select"
                    style={{ width: '100%' }}
                    value={createPriority}
                    onChange={(e) => setCreatePriority(e.target.value)}
                  >
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              </div>

              {/* Description */}
              <div>
                <label style={{ display: 'block', color: '#94a3b8', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  DESCRIPTION / CONTEXT
                </label>
                <textarea
                  className="rationale-textarea"
                  style={{ minHeight: '60px' }}
                  placeholder="Summary of the situation or risk requiring this decision..."
                  value={createDescription}
                  onChange={(e) => setCreateDescription(e.target.value)}
                />
              </div>

              {/* Alternatives Considered */}
              <div>
                <label style={{ display: 'block', color: '#94a3b8', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  ALTERNATIVES CONSIDERED
                </label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginBottom: '0.5rem' }}>
                  {createAlternatives.map((alt, idx) => (
                    <div key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'rgba(15, 23, 42, 0.7)', padding: '0.45rem 0.75rem', borderRadius: '6px', fontSize: '0.85rem' }}>
                      <span>{alt}</span>
                      <button
                        type="button"
                        onClick={() => handleRemoveAlternative(idx)}
                        style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
                      >
                        <X size={14} />
                      </button>
                    </div>
                  ))}
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <input
                    type="text"
                    placeholder="Add an alternative option..."
                    value={newAltText}
                    onChange={(e) => setNewAltText(e.target.value)}
                    style={{ flex: 1, background: 'rgba(15, 23, 42, 0.7)', border: '1px solid rgba(255, 255, 255, 0.1)', padding: '0.45rem 0.75rem', borderRadius: '6px', color: '#fff', fontSize: '0.85rem' }}
                  />
                  <button
                    type="button"
                    onClick={handleAddAlternative}
                    style={{ background: 'rgba(99, 102, 241, 0.2)', border: '1px solid #6366f1', color: '#fff', padding: '0.45rem 0.85rem', borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem' }}
                  >
                    Add Option
                  </button>
                </div>
              </div>

              {/* RATIONALE */}
              <div>
                <label style={{ display: 'block', color: '#94a3b8', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.35rem' }}>
                  HUMAN DECISION RATIONALE *
                </label>
                <textarea
                  className="rationale-textarea"
                  placeholder="State the why and expected impact behind this management decision..."
                  value={createRationale}
                  onChange={(e) => setCreateRationale(e.target.value)}
                  required
                />
              </div>

              {/* Submit Buttons */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
                <button
                  type="button"
                  className="btn-view-details"
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-record-decision"
                  disabled={isCreating}
                >
                  <Check size={16} />
                  {isCreating ? 'Recording…' : 'Record Decision in Audit Log'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Decisions;
