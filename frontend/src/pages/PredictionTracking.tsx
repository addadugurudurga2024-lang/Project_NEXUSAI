import React, { useState, useEffect } from 'react';
import {
  Activity,
  CheckCircle2,
  Clock,
  HelpCircle,
  TrendingUp,
  TrendingDown,
  Minus,
  Eye,
  Edit3,
  Sparkles,
  Info,
  RefreshCw,
  CheckSquare,
} from 'lucide-react';
import api from '../services/api';
import './PredictionTracking.css';

interface ModelPerformance {
  model_name: string;
  prediction_type: string;
  total_predictions: number;
  evaluated_count: number;
  pending_count: number;
  unavailable_count: number;
  mae?: number;
  median_absolute_error?: number;
  rmse?: number;
  mean_error_bias?: number;
  accuracy?: number;
  precision?: number;
  recall?: number;
  f1_score?: number;
  sample_size_status: 'SUFFICIENT' | 'LIMITED_SAMPLE' | 'NO_EVALUATED_DATA';
  sample_size_warning?: string;
}

interface TrajectoryPoint {
  id: string;
  timestamp: string;
  prediction_value: any;
  prediction_class?: string;
  prediction_numeric_value?: number;
  actual_value?: any;
  actual_class?: string;
  evaluation_status: string;
  error_value?: number;
}

interface TrajectoryData {
  project_id: string;
  project_name: string;
  prediction_type: string;
  trajectory_direction: string;
  history: TrajectoryPoint[];
}

interface PredictionRecord {
  id: string;
  project_id?: string;
  project_name?: string;
  entity_id?: string;
  entity_name?: string;
  prediction_type: string;
  model_name: string;
  model_version: string;
  prediction_timestamp: string;
  prediction_value: any;
  prediction_unit?: string;
  prediction_class?: string;
  prediction_numeric_value?: number;
  prediction_features_snapshot: Record<string, any>;
  prediction_context_snapshot?: Record<string, any>;
  target_date?: string;
  outcome_status: string;
  outcome_recorded_at?: string;
  actual_value?: any;
  actual_class?: string;
  actual_numeric_value?: number;
  actual_unit?: string;
  error_value?: number;
  absolute_error?: number;
  percentage_error?: number;
  evaluation_status: string;
  audit_trail: Array<{
    action: string;
    performed_by_name: string;
    timestamp: string;
    notes?: string;
    previous_actual_value?: any;
    new_actual_value?: any;
  }>;
}

const PredictionTracking: React.FC = () => {
  const [projects, setProjects] = useState<any[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [predictionTypeFilter, setPredictionTypeFilter] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  const [performance, setPerformance] = useState<ModelPerformance[]>([]);
  const [trajectory, setTrajectory] = useState<TrajectoryData | null>(null);
  const [history, setHistory] = useState<PredictionRecord[]>([]);

  const [loading, setLoading] = useState<boolean>(true);
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Modals
  const [outcomeModalOpen, setOutcomeModalOpen] = useState<boolean>(false);
  const [selectedPrediction, setSelectedPrediction] = useState<PredictionRecord | null>(null);
  const [actualValueInput, setActualValueInput] = useState<string>('');
  const [actualClassInput, setActualClassInput] = useState<string>('LOW');
  const [outcomeSourceInput, setOutcomeSourceInput] = useState<string>('manual_audit');
  const [outcomeNotesInput, setOutcomeNotesInput] = useState<string>('');

  const [snapshotModalOpen, setSnapshotModalOpen] = useState<boolean>(false);

  useEffect(() => {
    fetchProjects();
  }, []);

  useEffect(() => {
    fetchMetricsAndHistory();
  }, [selectedProjectId, predictionTypeFilter, statusFilter]);

  const fetchProjects = async () => {
    try {
      const res = await api.get('/projects');
      const pList = Array.isArray(res.data) ? res.data : [];
      setProjects(pList);
    } catch (err: any) {
      console.error('Failed to fetch projects:', err);
    }
  };

  const fetchMetricsAndHistory = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      // 1. Fetch Model Performance
      const perfParams: any = {};
      if (selectedProjectId) perfParams.project_id = selectedProjectId;
      if (predictionTypeFilter !== 'ALL') perfParams.prediction_type = predictionTypeFilter;

      const perfRes = await api.get('/predictions/performance', { params: perfParams });
      setPerformance(perfRes.data || []);

      // 2. Fetch Prediction History (scoped to selected project or all authorized projects)
      const histParams: any = { limit: 100 };
      if (predictionTypeFilter !== 'ALL') histParams.prediction_type = predictionTypeFilter;
      if (statusFilter !== 'ALL') histParams.evaluation_status = statusFilter;

      const historyUrl = selectedProjectId
        ? `/predictions/history/${selectedProjectId}`
        : '/predictions/history';

      const histRes = await api.get(historyUrl, { params: histParams });
      setHistory(histRes.data || []);

      // 3. Trajectory is project-specific
      if (selectedProjectId) {
        const trajRes = await api.get(`/predictions/trajectory/${selectedProjectId}`, {
          params: { prediction_type: predictionTypeFilter !== 'ALL' ? predictionTypeFilter : 'PROJECT_RISK' },
        });
        setTrajectory(trajRes.data);
      } else {
        setTrajectory(null);
      }
    } catch (err: any) {
      console.error('Failed to load prediction tracking data:', err);
      setErrorMsg(err.response?.data?.detail || 'Failed to load prediction tracking data');
    } finally {
      setLoading(false);
    }
  };

  const handleAutoEvaluate = async () => {
    if (!selectedProjectId) return;
    setEvaluating(true);
    try {
      const res = await api.post(`/predictions/project/${selectedProjectId}/auto-evaluate`);
      alert(res.data.message || 'Auto-evaluation completed.');
      fetchMetricsAndHistory();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to auto-evaluate project outcomes.');
    } finally {
      setEvaluating(false);
    }
  };

  const openRecordOutcomeModal = (rec: PredictionRecord) => {
    setSelectedPrediction(rec);
    if (rec.prediction_type === 'PROJECT_RISK' || rec.prediction_type === 'EMPLOYEE_BURNOUT') {
      setActualClassInput(rec.actual_class || rec.prediction_class || 'LOW');
      setActualValueInput('');
    } else {
      setActualValueInput(rec.actual_numeric_value !== undefined && rec.actual_numeric_value !== null ? String(rec.actual_numeric_value) : '');
      setActualClassInput('');
    }
    setOutcomeSourceInput('manual_audit');
    setOutcomeNotesInput('');
    setOutcomeModalOpen(true);
  };

  const submitOutcome = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPrediction) return;

    try {
      const payload: any = {
        source: outcomeSourceInput,
        notes: outcomeNotesInput,
        status: 'EVALUATED',
      };

      if (selectedPrediction.prediction_type === 'PROJECT_RISK' || selectedPrediction.prediction_type === 'EMPLOYEE_BURNOUT') {
        payload.actual_class = actualClassInput;
        payload.actual_value = actualClassInput;
      } else {
        const num = parseFloat(actualValueInput);
        if (isNaN(num)) {
          alert('Please enter a valid numeric actual outcome.');
          return;
        }
        payload.actual_numeric_value = num;
        payload.actual_value = num;
        payload.actual_unit = selectedPrediction.prediction_unit;
      }

      await api.post(`/predictions/${selectedPrediction.id}/outcome`, payload);
      setOutcomeModalOpen(false);
      fetchMetricsAndHistory();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to record actual outcome.');
    }
  };

  const openSnapshotModal = (rec: PredictionRecord) => {
    setSelectedPrediction(rec);
    setSnapshotModalOpen(true);
  };

  const renderTrendIcon = (direction: string) => {
    switch (direction) {
      case 'IMPROVING':
        return <span className="pt-trend-badge pt-trend-improving"><TrendingDown size={14} /> IMPROVING</span>;
      case 'DETERIORATING':
        return <span className="pt-trend-badge pt-trend-deteriorating"><TrendingUp size={14} /> DETERIORATING</span>;
      case 'STABLE':
        return <span className="pt-trend-badge pt-trend-stable"><Minus size={14} /> STABLE</span>;
      default:
        return <span className="pt-trend-badge pt-trend-insufficient"><Info size={14} /> INSUFFICIENT DATA</span>;
    }
  };

  return (
    <div className="prediction-tracking-page">
      {/* Header & Controls */}
      <div className="pt-header">
        <div className="pt-header-left">
          <h1>
            <Activity className="text-blue-500" size={28} />
            Prediction → Outcome Tracking & ML Performance
          </h1>
          <p>
            Immutable snapshot evaluation of production ML predictions against real-world observed outcomes.
          </p>
        </div>

        <div className="pt-controls">
          <select
            className="pt-select"
            value={selectedProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
          >
            <option value="">All Authorized Projects</option>
            {projects.map((p) => (
              <option key={p.id || p._id} value={p.id || p._id}>
                {p.name}
              </option>
            ))}
          </select>

          <select
            className="pt-select"
            value={predictionTypeFilter}
            onChange={(e) => setPredictionTypeFilter(e.target.value)}
          >
            <option value="ALL">All Prediction Types</option>
            <option value="PROJECT_RISK">Project Risk</option>
            <option value="DEADLINE_DELAY">Deadline Delay</option>
            <option value="BUDGET_OVERRUN">Budget Overrun</option>
            <option value="EMPLOYEE_BURNOUT">Employee Burnout</option>
          </select>

          <select
            className="pt-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="ALL">All Outcome Statuses</option>
            <option value="EVALUATED">Evaluated</option>
            <option value="PENDING">Pending Outcome</option>
            <option value="UNAVAILABLE">Unavailable</option>
          </select>

          {selectedProjectId && (
            <button
              className="pt-btn-secondary"
              onClick={handleAutoEvaluate}
              disabled={evaluating}
              title="Evaluate completed project delay and budget from authoritative lifecycle data"
            >
              <RefreshCw size={14} className={evaluating ? 'animate-spin' : ''} />
              {evaluating ? 'Evaluating...' : 'Auto-Evaluate Lifecycle'}
            </button>
          )}

          <button className="pt-btn-primary" onClick={fetchMetricsAndHistory}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {errorMsg && (
        <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', padding: 12, borderRadius: 8, color: '#f87171', marginBottom: 20 }}>
          {errorMsg}
        </div>
      )}

      {/* Model Performance Cards Grid */}
      <div className="pt-models-grid">
        {performance.map((m) => {
          const isRegression = m.prediction_type === 'DEADLINE_DELAY' || m.prediction_type === 'BUDGET_OVERRUN';
          return (
            <div key={`${m.model_name}-${m.prediction_type}`} className="pt-model-card">
              <div>
                <div className="pt-model-header">
                  <div>
                    <div className="pt-model-title">{m.prediction_type.replace(/_/g, ' ')}</div>
                    <div className="pt-model-subtitle">{m.model_name}</div>
                  </div>
                  <span className={`pt-badge ${
                    m.sample_size_status === 'SUFFICIENT'
                      ? 'pt-badge-sufficient'
                      : m.sample_size_status === 'LIMITED_SAMPLE'
                      ? 'pt-badge-limited'
                      : 'pt-badge-no-data'
                  }`}>
                    {m.sample_size_status.replace(/_/g, ' ')}
                  </span>
                </div>

                <div className="pt-model-stats">
                  {isRegression ? (
                    <>
                      <div className="pt-stat-box">
                        <div className="pt-stat-label">MAE (Mean Abs Error)</div>
                        <div className="pt-stat-val pt-stat-val-highlight">
                          {m.mae !== undefined && m.mae !== null ? `${m.mae} ${m.prediction_type === 'DEADLINE_DELAY' ? 'days' : '$'}` : '—'}
                        </div>
                      </div>
                      <div className="pt-stat-box">
                        <div className="pt-stat-label">RMSE / Median Error</div>
                        <div className="pt-stat-val">
                          {m.rmse !== undefined && m.rmse !== null ? `${m.rmse}` : '—'}
                        </div>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="pt-stat-box">
                        <div className="pt-stat-label">Accuracy</div>
                        <div className="pt-stat-val pt-stat-val-highlight">
                          {m.accuracy !== undefined && m.accuracy !== null ? `${(m.accuracy * 100).toFixed(1)}%` : '—'}
                        </div>
                      </div>
                      <div className="pt-stat-box">
                        <div className="pt-stat-label">F1-Score</div>
                        <div className="pt-stat-val pt-stat-val-accent">
                          {m.f1_score !== undefined && m.f1_score !== null ? m.f1_score.toFixed(2) : '—'}
                        </div>
                      </div>
                    </>
                  )}
                </div>

                {m.sample_size_warning && (
                  <div style={{ fontSize: 11, color: '#fbbf24', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 4 }}>
                    <Info size={12} /> {m.sample_size_warning}
                  </div>
                )}
              </div>

              <div className="pt-model-footer">
                <span>Total Predictions: <strong>{m.total_predictions}</strong></span>
                <span>Evaluated: <strong>{m.evaluated_count}</strong> | Pending: <strong>{m.pending_count}</strong></span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Trajectory Section for Selected Project */}
      {selectedProjectId && trajectory && trajectory.history.length > 0 && (
        <div className="pt-trajectory-card">
          <div className="pt-trajectory-header">
            <div className="pt-trajectory-title">
              <Sparkles size={18} className="text-blue-400" />
              <span>{trajectory.project_name} — Prediction Trajectory ({trajectory.prediction_type.replace(/_/g, ' ')})</span>
            </div>
            <div>{renderTrendIcon(trajectory.trajectory_direction)}</div>
          </div>

          <div className="pt-trajectory-steps">
            {trajectory.history.map((pt, idx) => (
              <div key={pt.id || idx} className="pt-trajectory-step">
                <div className="pt-step-date">
                  {new Date(pt.timestamp).toLocaleDateString()} {new Date(pt.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </div>
                <div className="pt-step-val">
                  <span style={{ color: pt.prediction_class === 'HIGH' ? '#f87171' : pt.prediction_class === 'MEDIUM' ? '#fbbf24' : '#34d399' }}>
                    {String(pt.prediction_value)}
                  </span>
                </div>
                <div className="pt-step-outcome">
                  {pt.evaluation_status === 'EVALUATED' ? (
                    <span style={{ color: '#34d399', fontSize: 11 }}>
                      Actual: {String(pt.actual_value)} (Err: {pt.error_value !== undefined ? pt.error_value : 0})
                    </span>
                  ) : (
                    <span style={{ color: '#fbbf24', fontSize: 11 }}>Outcome Pending</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Historical Prediction Snapshots & Outcome Ledger Table */}
      <div className="pt-table-card">
        <div className="pt-table-header">
          <div className="pt-table-title">
            Immutable Prediction Snapshots & Outcome Ledger ({history.length} records)
          </div>
        </div>

        <div className="pt-table-container">
          <table className="pt-table">
            <thead>
              <tr>
                <th>Date & Time</th>
                <th>Project / Entity</th>
                <th>Type</th>
                <th>Model Artifact</th>
                <th>Predicted</th>
                <th>Actual Outcome</th>
                <th>Variance / Error</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {history.length === 0 ? (
                <tr>
                  <td colSpan={9} style={{ textAlign: 'center', padding: '32px 0', color: '#94a3b8' }}>
                    {loading ? 'Loading prediction records...' : (
                      performance.some(m => m.total_predictions > 0) && history.length === 0
                        ? 'No prediction snapshots match the selected filter criteria.'
                        : 'No prediction snapshots are available for the selected scope.'
                    )}
                  </td>
                </tr>
              ) : (
                history.map((rec) => {
                  let typeClass = 'pt-type-risk';
                  if (rec.prediction_type === 'DEADLINE_DELAY') typeClass = 'pt-type-delay';
                  else if (rec.prediction_type === 'BUDGET_OVERRUN') typeClass = 'pt-type-budget';
                  else if (rec.prediction_type === 'EMPLOYEE_BURNOUT') typeClass = 'pt-type-burnout';

                  return (
                    <tr key={rec.id}>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        {new Date(rec.prediction_timestamp).toLocaleDateString()}{' '}
                        <span style={{ color: '#64748b', fontSize: 11 }}>
                          {new Date(rec.prediction_timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </td>
                      <td>{rec.project_name || rec.entity_name || 'System Entity'}</td>
                      <td>
                        <span className={`pt-type-tag ${typeClass}`}>
                          {rec.prediction_type.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td style={{ fontSize: 12, color: '#94a3b8' }}>
                        {rec.model_name}
                      </td>
                      <td style={{ fontWeight: 600, color: '#f8fafc' }}>
                        {String(rec.prediction_value)}
                      </td>
                      <td>
                        {rec.evaluation_status === 'EVALUATED' ? (
                          <span style={{ color: '#34d399', fontWeight: 600 }}>
                            {String(rec.actual_value)} {rec.actual_unit || ''}
                          </span>
                        ) : rec.evaluation_status === 'PENDING' ? (
                          <span className="pt-status-pending"><Clock size={12} /> Pending</span>
                        ) : (
                          <span className="pt-status-unavailable">Unavailable</span>
                        )}
                      </td>
                      <td>
                        {rec.evaluation_status === 'EVALUATED' ? (
                          rec.prediction_numeric_value !== undefined && rec.prediction_numeric_value !== null ? (
                            <span style={{ color: Math.abs(rec.error_value || 0) <= 2 ? '#34d399' : '#fbbf24' }}>
                              {rec.error_value !== undefined ? (rec.error_value > 0 ? `+${rec.error_value}` : `${rec.error_value}`) : '0'} {rec.prediction_unit || ''}
                            </span>
                          ) : (
                            <span style={{ color: rec.error_value === 0 ? '#34d399' : '#f87171' }}>
                              {rec.error_value === 0 ? 'MATCH (Correct)' : 'MISMATCH'}
                            </span>
                          )
                        ) : (
                          <span style={{ color: '#64748b' }}>—</span>
                        )}
                      </td>
                      <td>
                        {rec.evaluation_status === 'EVALUATED' ? (
                          <span className="pt-status-evaluated"><CheckCircle2 size={13} /> Evaluated</span>
                        ) : rec.evaluation_status === 'PENDING' ? (
                          <span className="pt-status-pending"><Clock size={13} /> Pending</span>
                        ) : (
                          <span className="pt-status-unavailable"><HelpCircle size={13} /> Unavailable</span>
                        )}
                      </td>
                      <td>
                        <div className="pt-actions-cell">
                          <button
                            className="pt-action-btn pt-action-btn-primary"
                            onClick={() => openRecordOutcomeModal(rec)}
                            title="Record Ground Truth Outcome"
                          >
                            <Edit3 size={12} /> Outcome
                          </button>
                          <button
                            className="pt-action-btn"
                            onClick={() => openSnapshotModal(rec)}
                            title="View Exact Feature Snapshot"
                          >
                            <Eye size={12} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Record Outcome Modal */}
      {outcomeModalOpen && selectedPrediction && (
        <div className="pt-modal-overlay" onClick={() => setOutcomeModalOpen(false)}>
          <div className="pt-modal" onClick={(e) => e.stopPropagation()}>
            <div className="pt-modal-header">
              <h3>Record Observed Ground Truth Outcome</h3>
              <button className="pt-modal-close" onClick={() => setOutcomeModalOpen(false)}>✕</button>
            </div>

            <form onSubmit={submitOutcome}>
              <div style={{ background: '#0f172a', padding: 12, borderRadius: 8, marginBottom: 16, border: '1px solid #334155' }}>
                <div style={{ fontSize: 12, color: '#94a3b8' }}>Target Prediction Snapshot:</div>
                <div style={{ fontWeight: 600, color: '#f8fafc', marginTop: 4 }}>
                  {selectedPrediction.prediction_type} — Predicted: <strong>{String(selectedPrediction.prediction_value)}</strong>
                </div>
                <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
                  Model: {selectedPrediction.model_name} | Captured: {new Date(selectedPrediction.prediction_timestamp).toLocaleString()}
                </div>
              </div>

              {selectedPrediction.prediction_type === 'PROJECT_RISK' || selectedPrediction.prediction_type === 'EMPLOYEE_BURNOUT' ? (
                <div className="pt-form-group">
                  <label>Observed Realized Class</label>
                  <select
                    className="pt-input"
                    value={actualClassInput}
                    onChange={(e) => setActualClassInput(e.target.value)}
                    required
                  >
                    <option value="LOW">LOW</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HIGH">HIGH</option>
                  </select>
                </div>
              ) : (
                <div className="pt-form-group">
                  <label>Actual Observed Numeric Value ({selectedPrediction.prediction_unit})</label>
                  <input
                    type="number"
                    step="any"
                    className="pt-input"
                    placeholder={`e.g. 18 (${selectedPrediction.prediction_unit})`}
                    value={actualValueInput}
                    onChange={(e) => setActualValueInput(e.target.value)}
                    required
                  />
                </div>
              )}

              <div className="pt-form-group">
                <label>Observation Source</label>
                <select
                  className="pt-input"
                  value={outcomeSourceInput}
                  onChange={(e) => setOutcomeSourceInput(e.target.value)}
                >
                  <option value="project_completion">Project Completion Milestone</option>
                  <option value="sprint_closure">Sprint Retrospective Closure</option>
                  <option value="budget_audit">Financial / Budget Audit</option>
                  <option value="hr_review">Formal HR / Workload Review</option>
                  <option value="manual_audit">Manual Management Verification</option>
                </select>
              </div>

              <div className="pt-form-group">
                <label>Audit Rationale & Context Notes</label>
                <textarea
                  className="pt-textarea"
                  rows={3}
                  placeholder="Explain how the ground truth outcome was verified..."
                  value={outcomeNotesInput}
                  onChange={(e) => setOutcomeNotesInput(e.target.value)}
                />
              </div>

              <div className="pt-modal-actions">
                <button type="button" className="pt-btn-secondary" onClick={() => setOutcomeModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="pt-btn-primary">
                  <CheckSquare size={14} /> Commit Ground Truth
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Snapshot Details Modal */}
      {snapshotModalOpen && selectedPrediction && (
        <div className="pt-modal-overlay" onClick={() => setSnapshotModalOpen(false)}>
          <div className="pt-modal" onClick={(e) => e.stopPropagation()}>
            <div className="pt-modal-header">
              <h3>Prediction Snapshot & Feature Vector</h3>
              <button className="pt-modal-close" onClick={() => setSnapshotModalOpen(false)}>✕</button>
            </div>

            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 13, color: '#94a3b8' }}>Model & Timing:</div>
              <div style={{ color: '#f8fafc', fontWeight: 600 }}>
                {selectedPrediction.model_name} (v{selectedPrediction.model_version})
              </div>
              <div style={{ fontSize: 12, color: '#64748b' }}>
                Captured: {new Date(selectedPrediction.prediction_timestamp).toISOString()}
              </div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 13, color: '#cbd5e1', marginBottom: 6, fontWeight: 500 }}>
                Exact Features Fed to Model at Inference Time:
              </div>
              <pre className="pt-features-list">
                {JSON.stringify(selectedPrediction.prediction_features_snapshot, null, 2)}
              </pre>
            </div>

            {selectedPrediction.audit_trail && selectedPrediction.audit_trail.length > 0 && (
              <div>
                <div style={{ fontSize: 13, color: '#cbd5e1', marginBottom: 6, fontWeight: 500 }}>
                  Audit Trail History:
                </div>
                <div className="pt-audit-list">
                  {selectedPrediction.audit_trail.map((entry, aIdx) => (
                    <div key={aIdx} className="pt-audit-item">
                      <div style={{ display: 'flex', justifyContent: 'space-between', color: '#94a3b8' }}>
                        <span>{entry.action} by <strong>{entry.performed_by_name}</strong></span>
                        <span>{new Date(entry.timestamp).toLocaleString()}</span>
                      </div>
                      {entry.notes && (
                        <div style={{ marginTop: 4, color: '#cbd5e1' }}>
                          "{entry.notes}"
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="pt-modal-actions">
              <button type="button" className="pt-btn-secondary" onClick={() => setSnapshotModalOpen(false)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PredictionTracking;
