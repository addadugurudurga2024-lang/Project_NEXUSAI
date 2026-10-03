import React, { useEffect, useState, useCallback } from 'react';
import {
  Activity, ShieldAlert, AlertTriangle, Plus, Edit2, Trash2,
  X, AlertCircle, Briefcase, DollarSign, Calendar, Users, Clock, ChevronDown, ChevronUp
} from 'lucide-react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
import './Projects.css';

/* ─── Types ─────────────────────────────────────────── */
interface Project {
  id: string;
  name: string;
  description?: string;
  client?: string;
  domain?: string;
  status: string;
  priority: string;
  start_date?: string;
  end_date?: string;
  budget: number;
  current_expenditure: number;
  progress: number;
  manager_id?: string;
  manager_name?: string;
  team_member_ids: string[];
  prediction?: any;
}

const STATUS_OPTIONS   = ['planning','active','on_hold','completed','cancelled'];
const PRIORITY_OPTIONS = ['low','medium','high','critical'];
const DOMAIN_OPTIONS   = ['fintech','healthcare','e-commerce','education','logistics','saas','manufacturing','other'];

const EMPTY_FORM = {
  name: '', description: '', client: '', domain: '',
  status: 'planning', priority: 'medium',
  start_date: '', end_date: '',
  budget: 0, current_expenditure: 0, progress: 0,
  manager_id: '', team_member_ids: [] as string[],
  requirements: '', tech_stack: '',
};

/* ─── Helpers ────────────────────────────────────────── */
const canManage = (role: string) => ['admin','project_manager'].includes(role);

const healthColor = (s: number) => s >= 80 ? '#10b981' : s >= 60 ? '#f59e0b' : '#ef4444';
const riskColor   = (r: string) => r === 'LOW' ? '#10b981' : r === 'MEDIUM' ? '#f59e0b' : '#ef4444';

/* ─── Component ──────────────────────────────────────── */
const Projects: React.FC = () => {
  const { user } = useAuth();
  const role = user?.role || 'team_member';
  const canWrite = canManage(role);

  const [projects,  setProjects]  = useState<Project[]>([]);
  const [employees, setEmployees] = useState<any[]>([]);
  const [loading,   setLoading]   = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving,    setSaving]    = useState(false);
  const [formError, setFormError] = useState('');
  const [deleteId,  setDeleteId]  = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState('');
  // Phase 6: per-project activity panel state
  const [activityOpen, setActivityOpen] = useState<string | null>(null);
  const [activities, setActivities] = useState<Record<string, any[]>>({});
  const [activityLoading, setActivityLoading] = useState<string | null>(null);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);

  /* ── Fetch ─────────────────────────────────────────── */
  const fetchAll = useCallback(async () => {
    try {
      const [projRes, empRes] = await Promise.all([
        api.get('/projects/'),
        api.get('/employees/'),
      ]);

      // Fetch predictions for each project (best-effort)
      const enriched = await Promise.all(projRes.data.map(async (p: any) => {
        try {
          const pr = await api.get(`/predictions/projects/${p.id}/latest`);
          return { ...p, prediction: pr.data };
        } catch {
          return { ...p, prediction: null };
        }
      }));

      setProjects(enriched);
      setEmployees(empRes.data);
    } catch (err) {
      console.error('Failed to fetch projects', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  /* ── Modal helpers ─────────────────────────────────── */
  const openCreate = () => {
    setEditingProject(null);
    setForm({ ...EMPTY_FORM, manager_id: '' });
    setFormError('');
    setModalOpen(true);
  };

  const openEdit = (p: Project) => {
    setEditingProject(p);
    setForm({
      name: p.name,
      description: p.description || '',
      client: p.client || '',
      domain: p.domain || '',
      status: p.status,
      priority: p.priority,
      start_date: p.start_date || '',
      end_date: p.end_date || '',
      budget: p.budget,
      current_expenditure: p.current_expenditure,
      progress: p.progress,
      manager_id: p.manager_id || '',
      team_member_ids: p.team_member_ids || [],
      requirements: '',
      tech_stack: '',
    });
    setFormError('');
    setModalOpen(true);
  };

  const closeModal = () => { setModalOpen(false); setEditingProject(null); };

  /* ── Form field handlers ───────────────────────────── */
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  const handleTeamToggle = (empId: string) => {
    setForm(prev => ({
      ...prev,
      team_member_ids: prev.team_member_ids.includes(empId)
        ? prev.team_member_ids.filter(id => id !== empId)
        : [...prev.team_member_ids, empId],
    }));
  };

  /* ── Validation ────────────────────────────────────── */
  const validate = (): string => {
    if (!form.name.trim())     return 'Project name is required.';
    if (Number(form.budget) < 0) return 'Budget cannot be negative.';
    if (Number(form.progress) < 0 || Number(form.progress) > 100)
      return 'Progress must be between 0 and 100.';
    if (form.start_date && form.end_date && form.end_date < form.start_date)
      return 'End date cannot be before start date.';
    return '';
  };

  /* ── Submit ────────────────────────────────────────── */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const err = validate();
    if (err) { setFormError(err); return; }

    setSaving(true);
    setFormError('');
    try {
      const payload = {
        name: form.name.trim(),
        description: form.description || undefined,
        client: form.client || undefined,
        domain: form.domain || undefined,
        status: form.status,
        priority: form.priority,
        start_date: form.start_date || undefined,
        end_date: form.end_date || undefined,
        budget: Number(form.budget),
        current_expenditure: Number(form.current_expenditure),
        progress: Number(form.progress),
        manager_id: form.manager_id || undefined,
        team_member_ids: form.team_member_ids,
        requirements: form.requirements || undefined,
        tech_stack: form.tech_stack
          ? form.tech_stack.split(',').map(s => s.trim()).filter(Boolean)
          : [],
      };

      if (editingProject) {
        await api.put(`/projects/${editingProject.id}`, payload);
      } else {
        await api.post('/projects/', payload);
      }
      closeModal();
      fetchAll();
    } catch (err: any) {
      setFormError(err.response?.data?.detail || 'Failed to save project.');
    } finally {
      setSaving(false);
    }
  };

  /* ── Delete ────────────────────────────────────────── */
  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/projects/${id}`);
      setDeleteId(null);
      fetchAll();
    } catch (err) {
      console.error('Delete failed', err);
    }
  };

  /* ── AI Analysis ───────────────────────────────────── */
  const runAnalysis = async (projectId: string) => {
    setAnalyzingId(projectId);
    try {
      await api.post(`/predictions/analyze/project/${projectId}`);
      await fetchAll();
    } catch (err) {
      console.error('Analysis failed', err);
    } finally {
      setAnalyzingId(null);
    }
  };

  // Phase 6: toggle activity panel and fetch on first open
  const toggleActivity = async (projectId: string) => {
    if (activityOpen === projectId) {
      setActivityOpen(null);
      return;
    }
    setActivityOpen(projectId);
    if (!activities[projectId]) {
      setActivityLoading(projectId);
      try {
        const res = await api.get(`/activities/project/${projectId}`);
        setActivities(prev => ({ ...prev, [projectId]: res.data }));
      } catch {
        setActivities(prev => ({ ...prev, [projectId]: [] }));
      } finally {
        setActivityLoading(null);
      }
    }
  };

  const ACTIVITY_ICONS: Record<string, string> = {
    PROJECT_CREATED: '🚀', PM_ASSIGNED: '👤', MEMBER_ADDED: '➕', MEMBER_REMOVED: '➖',
    TASK_CREATED: '📋', TASK_ASSIGNED: '🎯', TASK_REASSIGNED: '🔄', TASK_STATUS_CHANGED: '✅',
    ISSUE_CREATED: '🐛', ISSUE_ASSIGNED: '🔧', ISSUE_RESOLVED: '✔️', ISSUE_STATUS_CHANGED: '📝',
  };

  /* ── Filtered list ─────────────────────────────────── */
  const filtered = projects.filter(p => !filterStatus || p.status === filterStatus);

  if (loading) return <div className="loading-state"><div className="loading-spinner"/>Loading projects...</div>;

  /* ── Render ────────────────────────────────────────── */
  return (
    <div className="projects-page">

      {/* Header */}
      <div className="page-header flex-between">
        <div>
          <h1>Projects Portfolio</h1>
          <p>AI-enhanced project tracking — {projects.length} projects</p>
        </div>
        <div className="header-actions">
          <select
            value={filterStatus}
            onChange={e => setFilterStatus(e.target.value)}
            className="filter-select-sm"
            id="filter-project-status"
          >
            <option value="">All Statuses</option>
            {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace('_',' ')}</option>)}
          </select>
          {canWrite && (
            <button className="primary-button" onClick={openCreate} id="new-project-btn">
              <Plus size={16}/> New Project
            </button>
          )}
          {!canWrite && (
            <span className="role-notice" title="Team Members cannot create projects">
              View Only
            </span>
          )}
        </div>
      </div>

      {/* Empty state */}
      {filtered.length === 0 && (
        <div className="projects-empty glass-panel">
          <Briefcase size={40} style={{ opacity: 0.25 }}/>
          <h3>{filterStatus ? `No ${filterStatus} projects` : 'No projects yet'}</h3>
          {canWrite
            ? <p>Click <strong>New Project</strong> to create your first project.</p>
            : <p>No projects are available to view.</p>
          }
        </div>
      )}

      {/* Projects Grid */}
      <div className="projects-grid">
        {filtered.map(project => (
          <div key={project.id} className="project-card glass-panel">

            {/* Card Header */}
            <div className="project-header">
              <div className="project-title-group">
                <h2>{project.name}</h2>
                {project.client && <span className="project-client">{project.client}</span>}
              </div>
              <div className="project-header-right">
                <span className={`status-badge ${project.status}`}>
                  {project.status.replace('_',' ')}
                </span>
                <span className={`priority-dot priority-${project.priority}`} title={`Priority: ${project.priority}`}/>
              </div>
            </div>

            {project.description && (
              <p className="project-desc">{project.description}</p>
            )}

            {/* Metadata row */}
            <div className="project-meta-row">
              {project.domain && <span className="meta-chip">{project.domain}</span>}
              {project.manager_name && (
                <span className="meta-chip">
                  <Users size={11}/> {project.manager_name}
                </span>
              )}
              {project.start_date && (
                <span className="meta-chip">
                  <Calendar size={11}/> {project.start_date}
                </span>
              )}
            </div>

            {/* Progress */}
            <div className="project-metrics">
              <div className="metric">
                <span className="metric-label">Progress</span>
                <div className="progress-bar-container">
                  <div
                    className="progress-bar"
                    style={{
                      width: `${project.progress}%`,
                      background: project.progress >= 70
                        ? 'linear-gradient(90deg, #6366f1, #10b981)'
                        : 'linear-gradient(90deg, #6366f1, #f59e0b)'
                    }}
                  />
                </div>
                <span className="metric-value">{project.progress.toFixed(0)}%</span>
              </div>
            </div>

            {/* Budget */}
            <div className="budget-row">
              <DollarSign size={13} style={{ color: '#6366f1', flexShrink: 0 }}/>
              <div className="budget-bar-track">
                <div
                  className="budget-bar-fill"
                  style={{
                    width: project.budget > 0
                      ? `${Math.min(project.current_expenditure / project.budget * 100, 100)}%`
                      : '0%',
                    background: project.budget > 0 && project.current_expenditure / project.budget > 0.85
                      ? 'linear-gradient(90deg,#f59e0b,#ef4444)'
                      : 'linear-gradient(90deg,#6366f1,#10b981)',
                  }}
                />
              </div>
              <span className="budget-label">
                ${(project.current_expenditure/1000).toFixed(0)}k / ${(project.budget/1000).toFixed(0)}k
              </span>
            </div>

            {/* AI Insights */}
            {project.prediction ? (
              <div className="ai-insights">
                <div className="insight-header">
                  <Activity size={14}/><span>AI Intelligence</span>
                </div>
                <div className="insight-grid">
                  <div className="insight-item">
                    <span className="insight-label">Health Score</span>
                    <span className="insight-val" style={{ color: healthColor(project.prediction.health_score) }}>
                      {project.prediction.health_score}/100
                    </span>
                  </div>
                  <div className="insight-item">
                    <span className="insight-label">Risk Level</span>
                    <span className="insight-val flex-center gap-2" style={{ color: riskColor(project.prediction.risk_class) }}>
                      {project.prediction.risk_class === 'HIGH' && <AlertTriangle size={12}/>}
                      {project.prediction.risk_class}
                    </span>
                  </div>
                  <div className="insight-item">
                    <span className="insight-label">Predicted Delay</span>
                    <span className="insight-val" style={{ color: project.prediction.delay_days > 0 ? '#f59e0b' : '#10b981' }}>
                      {project.prediction.delay_days > 0 ? `+${project.prediction.delay_days} days` : 'On Time'}
                    </span>
                  </div>
                  <div className="insight-item">
                    <span className="insight-label">Budget Risk</span>
                    <span className="insight-val" style={{ color: riskColor(project.prediction.budget_overrun_risk) }}>
                      {project.prediction.budget_overrun_risk}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="ai-insights empty">
                <button
                  className="analyze-button"
                  disabled={analyzingId === project.id}
                  onClick={() => runAnalysis(project.id)}
                  id={`analyze-${project.id}`}
                >
                  <Activity size={14} className={analyzingId === project.id ? "spin" : ""} />
                  {analyzingId === project.id ? "Analyzing..." : "Run AI Analysis"}
                </button>
              </div>
            )}

            {/* Actions */}
            <div className="project-actions">
              {canWrite && (
                <>
                  <button
                    className="action-btn edit-btn"
                    onClick={() => openEdit(project)}
                    title="Edit project"
                    id={`edit-project-${project.id}`}
                  >
                    <Edit2 size={14}/> Edit
                  </button>
                  <button
                    className="action-btn delete-btn"
                    onClick={() => setDeleteId(project.id)}
                    title="Delete project"
                    id={`delete-project-${project.id}`}
                  >
                    <Trash2 size={14}/>
                  </button>
                </>
              )}
              {/* Phase 6: Activity toggle button */}
              <button
                className="action-btn activity-btn"
                onClick={() => toggleActivity(project.id)}
                id={`activity-${project.id}`}
                title="View project activity"
              >
                <Clock size={14}/>
                {activityOpen === project.id ? <ChevronUp size={12}/> : <ChevronDown size={12}/>}
                Activity
              </button>
            </div>

            {/* Phase 6: Activity Timeline Panel */}
            {activityOpen === project.id && (
              <div className="project-activity-panel">
                <div className="activity-panel-header">
                  <Clock size={14}/>
                  <span>Project Activity</span>
                </div>
                {activityLoading === project.id ? (
                  <div className="activity-loading">Loading activity...</div>
                ) : (activities[project.id] || []).length === 0 ? (
                  <div className="activity-empty">No activity recorded yet.</div>
                ) : (
                  <ul className="activity-list">
                    {(activities[project.id] || []).map((act: any) => (
                      <li key={act.id} className="activity-item">
                        <span className="activity-icon">
                          {ACTIVITY_ICONS[act.activity_type] || '•'}
                        </span>
                        <div className="activity-body">
                          <span className="activity-message">{act.message}</span>
                          <span className="activity-meta">
                            {act.timestamp
                              ? new Date(act.timestamp).toLocaleString()
                              : ''}
                          </span>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* ── Create / Edit Modal ─────────────────────── */}
      {modalOpen && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-panel proj-modal glass-panel" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{editingProject ? 'Edit Project' : 'Create New Project'}</h2>
              <button className="icon-btn" onClick={closeModal} id="close-project-modal"><X size={18}/></button>
            </div>

            <form onSubmit={handleSubmit} className="modal-form proj-form">
              {formError && (
                <div className="form-error">
                  <AlertCircle size={14}/>{formError}
                </div>
              )}

              {/* Name + Priority */}
              <div className="form-row">
                <div className="form-group" style={{ gridColumn: 'span 2' }}>
                  <label>Project Name *</label>
                  <input
                    name="name" value={form.name} onChange={handleChange}
                    placeholder="e.g. NexusAI Platform v2.0"
                    required id="proj-name"
                  />
                </div>
                <div className="form-group">
                  <label>Priority</label>
                  <select name="priority" value={form.priority} onChange={handleChange}>
                    {PRIORITY_OPTIONS.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
              </div>

              {/* Description */}
              <div className="form-group">
                <label>Description</label>
                <textarea
                  name="description" value={form.description} onChange={handleChange}
                  rows={2} placeholder="What is this project about?"
                />
              </div>

              {/* Client + Domain + Status */}
              <div className="form-row">
                <div className="form-group">
                  <label>Client</label>
                  <input name="client" value={form.client} onChange={handleChange} placeholder="Acme Corp"/>
                </div>
                <div className="form-group">
                  <label>Domain</label>
                  <select name="domain" value={form.domain} onChange={handleChange}>
                    <option value="">Select domain...</option>
                    {DOMAIN_OPTIONS.map(d => <option key={d} value={d}>{d}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Status</label>
                  <select name="status" value={form.status} onChange={handleChange}>
                    {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace('_',' ')}</option>)}
                  </select>
                </div>
              </div>

              {/* Dates */}
              <div className="form-row">
                <div className="form-group">
                  <label>Start Date</label>
                  <input type="date" name="start_date" value={form.start_date} onChange={handleChange}/>
                </div>
                <div className="form-group">
                  <label>End Date</label>
                  <input type="date" name="end_date" value={form.end_date} onChange={handleChange}/>
                </div>
              </div>

              {/* Budget */}
              <div className="form-row">
                <div className="form-group">
                  <label>Budget ($)</label>
                  <input
                    type="number" name="budget" value={form.budget} onChange={handleChange}
                    min={0} step={1000} placeholder="150000"
                  />
                </div>
                <div className="form-group">
                  <label>Current Expenditure ($)</label>
                  <input
                    type="number" name="current_expenditure" value={form.current_expenditure}
                    onChange={handleChange} min={0} step={100}
                  />
                </div>
                <div className="form-group">
                  <label>Progress (%)</label>
                  <input
                    type="number" name="progress" value={form.progress} onChange={handleChange}
                    min={0} max={100} step={1}
                  />
                </div>
              </div>

              {/* Project Manager */}
              <div className="form-group">
                <label>Project Manager</label>
                <select name="manager_id" value={form.manager_id} onChange={handleChange}>
                  <option value="">Unassigned</option>
                  {employees.map(e => (
                    <option key={e.id} value={e.id}>{e.name} — {e.role}</option>
                  ))}
                </select>
              </div>

              {/* Team Members */}
              <div className="form-group">
                <label>Team Members</label>
                <div className="team-selector">
                  {employees.map(e => (
                    <label key={e.id} className={`team-chip ${form.team_member_ids.includes(e.id) ? 'selected' : ''}`}>
                      <input
                        type="checkbox"
                        checked={form.team_member_ids.includes(e.id)}
                        onChange={() => handleTeamToggle(e.id)}
                        style={{ display: 'none' }}
                      />
                      {e.name}
                    </label>
                  ))}
                  {employees.length === 0 && (
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                      No employees found — add employees first.
                    </span>
                  )}
                </div>
              </div>

              {/* Tech Stack */}
              <div className="form-group">
                <label>Tech Stack <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>(comma-separated)</span></label>
                <input
                  name="tech_stack" value={form.tech_stack} onChange={handleChange}
                  placeholder="React, FastAPI, MongoDB, Python"
                />
              </div>

              {/* Requirements */}
              <div className="form-group">
                <label>Requirements / Notes</label>
                <textarea
                  name="requirements" value={form.requirements} onChange={handleChange}
                  rows={2} placeholder="Key requirements, constraints, or notes..."
                />
              </div>

              <div className="modal-actions">
                <button type="button" className="secondary-button" onClick={closeModal}>Cancel</button>
                <button
                  type="submit" className="primary-button" disabled={saving}
                  id={editingProject ? 'update-project-btn' : 'create-project-btn'}
                >
                  {saving ? 'Saving...' : editingProject ? 'Update Project' : 'Create Project'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Delete Confirmation ─────────────────────── */}
      {deleteId && (
        <div className="modal-overlay" onClick={() => setDeleteId(null)}>
          <div className="modal-panel confirm-panel glass-panel" onClick={e => e.stopPropagation()}>
            <ShieldAlert size={32} style={{ color: '#ef4444', margin: '0 auto' }}/>
            <h3>Delete Project?</h3>
            <p>This will permanently delete the project and cannot be undone. Associated tasks, issues, and documents will remain in the database.</p>
            <div className="modal-actions">
              <button className="secondary-button" onClick={() => setDeleteId(null)}>Cancel</button>
              <button className="danger-button" onClick={() => handleDelete(deleteId)} id="confirm-delete-project">
                Delete Project
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Projects;
