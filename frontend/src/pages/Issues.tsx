import React, { useEffect, useState, useCallback } from 'react';
import { Plus, Eye, Trash2, X, AlertCircle } from 'lucide-react';
import api from '../services/api';
import './CRUD.css';

interface Issue {
  id: string;
  title: string;
  description?: string;
  project_id: string;
  task_id?: string;
  category: string;
  severity: string;
  priority: string;
  status: string;
  assignee_id?: string;
  assignee_name?: string;
  resolution?: string;
  created_at?: string;
}

const CATEGORY_OPTIONS = ['bug', 'security', 'performance', 'compliance', 'ambiguity', 'design', 'integration', 'other'];
const SEVERITY_OPTIONS = ['low', 'medium', 'high', 'critical'];
const PRIORITY_OPTIONS = ['low', 'medium', 'high', 'critical'];
const STATUS_OPTIONS = ['open', 'in_progress', 'resolved', 'closed', 'wont_fix'];

const EMPTY_FORM = {
  title: '',
  description: '',
  project_id: '',
  task_id: '',
  category: 'bug',
  severity: 'medium',
  priority: 'medium',
  status: 'open',
  assignee_id: '',
  resolution: '',
};

const Issues: React.FC = () => {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [projects, setProjects] = useState<any[]>([]);
  const [employees, setEmployees] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingIssue, setEditingIssue] = useState<Issue | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [filterSeverity, setFilterSeverity] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterProject, setFilterProject] = useState('');

  const fetchAll = useCallback(async () => {
    try {
      const [issuesRes, projectsRes, employeesRes] = await Promise.all([
        api.get('/issues/'),
        api.get('/projects/'),
        api.get('/employees/'),
      ]);
      setIssues(issuesRes.data);
      setProjects(projectsRes.data);
      setEmployees(employeesRes.data);
    } catch (err) {
      console.error('Failed to fetch issues', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const openCreate = () => {
    setEditingIssue(null);
    setForm({ ...EMPTY_FORM, project_id: projects[0]?.id || '' });
    setError('');
    setModalOpen(true);
  };

  const openEdit = (issue: Issue) => {
    setEditingIssue(issue);
    setForm({
      title: issue.title,
      description: issue.description || '',
      project_id: issue.project_id,
      task_id: issue.task_id || '',
      category: issue.category,
      severity: issue.severity,
      priority: issue.priority,
      status: issue.status,
      assignee_id: issue.assignee_id || '',
      resolution: issue.resolution || '',
    });
    setError('');
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingIssue(null);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) { setError('Title is required'); return; }
    if (!form.project_id) { setError('Project is required'); return; }
    setSaving(true);
    setError('');
    try {
      const payload = {
        ...form,
        task_id: form.task_id || undefined,
        assignee_id: form.assignee_id || undefined,
        resolution: form.resolution || undefined,
      };
      if (editingIssue) {
        await api.put(`/issues/${editingIssue.id}`, payload);
      } else {
        await api.post('/issues/', payload);
      }
      closeModal();
      fetchAll();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/issues/${id}`);
      setDeleteId(null);
      fetchAll();
    } catch (err) {
      console.error('Delete failed', err);
    }
  };

  const filtered = issues.filter(i => {
    if (filterSeverity && i.severity !== filterSeverity) return false;
    if (filterStatus && i.status !== filterStatus) return false;
    if (filterProject && i.project_id !== filterProject) return false;
    return true;
  });

  if (loading) return <div className="loading-state"><div className="loading-spinner" />Loading issues...</div>;

  return (
    <div className="crud-page">
      <div className="page-header flex-between">
        <div>
          <h1>Issues</h1>
          <p>Risk and defect tracking — {issues.length} total</p>
        </div>
        <button className="primary-button" onClick={openCreate} id="new-issue-btn">
          <Plus size={16} /> Log Issue
        </button>
      </div>

      {/* Filters */}
      <div className="filter-bar glass-panel">
        <select value={filterSeverity} onChange={e => setFilterSeverity(e.target.value)} className="filter-select">
          <option value="">All Severities</option>
          {SEVERITY_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} className="filter-select">
          <option value="">All Statuses</option>
          {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
        </select>
        <select value={filterProject} onChange={e => setFilterProject(e.target.value)} className="filter-select">
          <option value="">All Projects</option>
          {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        {(filterSeverity || filterStatus || filterProject) && (
          <button className="text-button" onClick={() => { setFilterSeverity(''); setFilterStatus(''); setFilterProject(''); }}>Clear</button>
        )}
        <span className="filter-count">{filtered.length} issues</span>
      </div>

      <div className="table-container glass-panel">
        <table className="data-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Project</th>
              <th>Category</th>
              <th>Severity</th>
              <th>Priority</th>
              <th>Status</th>
              <th>Assignee</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(issue => (
              <tr key={issue.id}>
                <td><strong>{issue.title}</strong></td>
                <td>{projects.find(p => p.id === issue.project_id)?.name || '—'}</td>
                <td style={{ textTransform: 'capitalize' }}>{issue.category}</td>
                <td><span className={`badge severity-${issue.severity}`}>{issue.severity}</span></td>
                <td><span className={`badge priority-${issue.priority}`}>{issue.priority}</span></td>
                <td><span className={`badge status-${issue.status}`}>{issue.status.replace('_', ' ')}</span></td>
                <td>{issue.assignee_name || '—'}</td>
                <td>{issue.created_at ? new Date(issue.created_at).toLocaleDateString() : '—'}</td>
                <td className="action-cell">
                  <button className="icon-btn" title="View / Edit" onClick={() => openEdit(issue)} id={`edit-issue-${issue.id}`}><Eye size={14} /></button>
                  <button className="icon-btn danger" title="Delete" onClick={() => setDeleteId(issue.id)} id={`delete-issue-${issue.id}`}><Trash2 size={14} /></button>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={9} className="text-center py-4">
                <AlertCircle size={32} style={{ opacity: 0.2, display: 'block', margin: '0 auto 0.5rem' }} />
                No issues found. {filterSeverity || filterStatus || filterProject ? 'Try clearing filters.' : 'Log your first issue!'}
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Create / Edit Modal */}
      {modalOpen && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-panel glass-panel" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{editingIssue ? 'Update Issue' : 'Log New Issue'}</h2>
              <button className="icon-btn" onClick={closeModal} id="close-issue-modal"><X size={18} /></button>
            </div>
            <form onSubmit={handleSubmit} className="modal-form">
              {error && <div className="form-error"><AlertCircle size={14} />{error}</div>}

              <div className="form-row">
                <div className="form-group flex-2">
                  <label>Title *</label>
                  <input name="title" value={form.title} onChange={handleChange} placeholder="Describe the issue concisely" required />
                </div>
                <div className="form-group">
                  <label>Category</label>
                  <select name="category" value={form.category} onChange={handleChange}>
                    {CATEGORY_OPTIONS.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label>Description</label>
                <textarea name="description" value={form.description} onChange={handleChange} rows={3} placeholder="Detailed description of the issue..." />
              </div>

              <div className="form-row">
                <div className="form-group flex-2">
                  <label>Project *</label>
                  <select name="project_id" value={form.project_id} onChange={handleChange} required>
                    <option value="">Select project...</option>
                    {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                  </select>
                </div>
                <div className="form-group flex-2">
                  <label>Assignee</label>
                  <select name="assignee_id" value={form.assignee_id} onChange={handleChange}>
                    <option value="">Unassigned</option>
                    {employees.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
                  </select>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Severity</label>
                  <select name="severity" value={form.severity} onChange={handleChange}>
                    {SEVERITY_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Priority</label>
                  <select name="priority" value={form.priority} onChange={handleChange}>
                    {PRIORITY_OPTIONS.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Status</label>
                  <select name="status" value={form.status} onChange={handleChange}>
                    {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
                  </select>
                </div>
              </div>

              {(form.status === 'resolved' || form.status === 'closed') && (
                <div className="form-group">
                  <label>Resolution Notes</label>
                  <textarea name="resolution" value={form.resolution} onChange={handleChange} rows={2} placeholder="Describe how the issue was resolved..." />
                </div>
              )}

              <div className="modal-actions">
                <button type="button" className="secondary-button" onClick={closeModal}>Cancel</button>
                <button type="submit" className="primary-button" disabled={saving} id="save-issue-btn">
                  {saving ? 'Saving...' : editingIssue ? 'Update Issue' : 'Log Issue'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirm */}
      {deleteId && (
        <div className="modal-overlay" onClick={() => setDeleteId(null)}>
          <div className="modal-panel confirm-panel glass-panel" onClick={e => e.stopPropagation()}>
            <h3>Delete Issue?</h3>
            <p>This action cannot be undone.</p>
            <div className="modal-actions">
              <button className="secondary-button" onClick={() => setDeleteId(null)}>Cancel</button>
              <button className="danger-button" onClick={() => handleDelete(deleteId)} id="confirm-delete-issue">Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Issues;
