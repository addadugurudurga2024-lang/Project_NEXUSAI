import React, { useEffect, useState, useCallback } from 'react';
import { Plus, Edit2, Trash2, X, CheckSquare, AlertCircle } from 'lucide-react';
import api from '../services/api';
import './CRUD.css';

interface Task {
  id: string;
  title: string;
  description?: string;
  project_id: string;
  sprint_id?: string;
  assignee_id?: string;
  assignee_name?: string;
  status: string;
  priority: string;
  story_points: number;
  estimated_hours: number;
  actual_hours: number;
  due_date?: string;
  task_type?: string;
}

const STATUS_OPTIONS = ['todo', 'in_progress', 'review', 'done', 'blocked'];
const PRIORITY_OPTIONS = ['low', 'medium', 'high', 'critical'];
const TYPE_OPTIONS = ['feature', 'bug', 'chore', 'research', 'documentation'];

const EMPTY_FORM = {
  title: '',
  description: '',
  project_id: '',
  sprint_id: '',
  assignee_id: '',
  status: 'todo',
  priority: 'medium',
  story_points: 0,
  estimated_hours: 0,
  actual_hours: 0,
  due_date: '',
  task_type: 'feature',
};

const Tasks: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [projects, setProjects] = useState<any[]>([]);
  const [employees, setEmployees] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState('');
  const [filterProject, setFilterProject] = useState('');

  const fetchAll = useCallback(async () => {
    try {
      const [tasksRes, projectsRes, employeesRes] = await Promise.all([
        api.get('/tasks/'),
        api.get('/projects/'),
        api.get('/employees/'),
      ]);
      setTasks(tasksRes.data);
      setProjects(projectsRes.data);
      setEmployees(employeesRes.data);
    } catch (err) {
      console.error('Failed to fetch tasks', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const openCreate = () => {
    setEditingTask(null);
    setForm({ ...EMPTY_FORM, project_id: projects[0]?.id || '' });
    setError('');
    setModalOpen(true);
  };

  const openEdit = (task: Task) => {
    setEditingTask(task);
    setForm({
      title: task.title,
      description: task.description || '',
      project_id: task.project_id,
      sprint_id: task.sprint_id || '',
      assignee_id: task.assignee_id || '',
      status: task.status,
      priority: task.priority,
      story_points: task.story_points,
      estimated_hours: task.estimated_hours,
      actual_hours: task.actual_hours,
      due_date: task.due_date || '',
      task_type: task.task_type || 'feature',
    });
    setError('');
    setModalOpen(true);
  };

  const closeModal = () => {
    setModalOpen(false);
    setEditingTask(null);
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
        story_points: Number(form.story_points),
        estimated_hours: Number(form.estimated_hours),
        actual_hours: Number(form.actual_hours),
        sprint_id: form.sprint_id || undefined,
        assignee_id: form.assignee_id || undefined,
        due_date: form.due_date || undefined,
      };
      if (editingTask) {
        await api.put(`/tasks/${editingTask.id}`, payload);
      } else {
        await api.post('/tasks/', payload);
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
      await api.delete(`/tasks/${id}`);
      setDeleteId(null);
      fetchAll();
    } catch (err) {
      console.error('Delete failed', err);
    }
  };

  const filteredTasks = tasks.filter(t => {
    if (filterStatus && t.status !== filterStatus) return false;
    if (filterProject && t.project_id !== filterProject) return false;
    return true;
  });

  if (loading) return <div className="loading-state"><div className="loading-spinner" />Loading tasks...</div>;

  return (
    <div className="crud-page">
      <div className="page-header flex-between">
        <div>
          <h1>Tasks</h1>
          <p>Task management and tracking — {tasks.length} total</p>
        </div>
        <button className="primary-button" onClick={openCreate} id="new-task-btn">
          <Plus size={16} /> New Task
        </button>
      </div>

      {/* Filters */}
      <div className="filter-bar glass-panel">
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} className="filter-select" id="filter-status">
          <option value="">All Statuses</option>
          {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
        </select>
        <select value={filterProject} onChange={e => setFilterProject(e.target.value)} className="filter-select" id="filter-project">
          <option value="">All Projects</option>
          {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        {(filterStatus || filterProject) && (
          <button className="text-button" onClick={() => { setFilterStatus(''); setFilterProject(''); }}>Clear</button>
        )}
        <span className="filter-count">{filteredTasks.length} tasks</span>
      </div>

      <div className="table-container glass-panel">
        <table className="data-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Project</th>
              <th>Assignee</th>
              <th>Status</th>
              <th>Priority</th>
              <th>Est. h</th>
              <th>Actual h</th>
              <th>Due</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredTasks.map(task => (
              <tr key={task.id}>
                <td><strong>{task.title}</strong>{task.description && <span className="row-sub">{task.description.slice(0, 40)}{task.description.length > 40 ? '…' : ''}</span>}</td>
                <td>{projects.find(p => p.id === task.project_id)?.name || '—'}</td>
                <td>{task.assignee_name || '—'}</td>
                <td><span className={`badge status-${task.status}`}>{task.status.replace('_', ' ')}</span></td>
                <td><span className={`badge priority-${task.priority}`}>{task.priority}</span></td>
                <td>{task.estimated_hours}h</td>
                <td>{task.actual_hours}h</td>
                <td>{task.due_date ? new Date(task.due_date).toLocaleDateString() : '—'}</td>
                <td className="action-cell">
                  <button className="icon-btn" title="Edit" onClick={() => openEdit(task)} id={`edit-task-${task.id}`}><Edit2 size={14} /></button>
                  <button className="icon-btn danger" title="Delete" onClick={() => setDeleteId(task.id)} id={`delete-task-${task.id}`}><Trash2 size={14} /></button>
                </td>
              </tr>
            ))}
            {filteredTasks.length === 0 && (
              <tr><td colSpan={9} className="text-center py-4">
                <CheckSquare size={32} style={{ opacity: 0.2, display: 'block', margin: '0 auto 0.5rem' }} />
                No tasks found. {filterStatus || filterProject ? 'Try clearing filters.' : 'Create your first task!'}
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
              <h2>{editingTask ? 'Edit Task' : 'New Task'}</h2>
              <button className="icon-btn" onClick={closeModal} id="close-task-modal"><X size={18} /></button>
            </div>
            <form onSubmit={handleSubmit} className="modal-form">
              {error && <div className="form-error"><AlertCircle size={14} />{error}</div>}

              <div className="form-row">
                <div className="form-group flex-2">
                  <label>Title *</label>
                  <input name="title" value={form.title} onChange={handleChange} placeholder="Implement authentication flow" required />
                </div>
                <div className="form-group">
                  <label>Type</label>
                  <select name="task_type" value={form.task_type} onChange={handleChange}>
                    {TYPE_OPTIONS.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label>Description</label>
                <textarea name="description" value={form.description} onChange={handleChange} rows={2} placeholder="Optional details..." />
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
                  <label>Status</label>
                  <select name="status" value={form.status} onChange={handleChange}>
                    {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Priority</label>
                  <select name="priority" value={form.priority} onChange={handleChange}>
                    {PRIORITY_OPTIONS.map(p => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Story Points</label>
                  <input type="number" name="story_points" value={form.story_points} onChange={handleChange} min={0} />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Est. Hours</label>
                  <input type="number" name="estimated_hours" value={form.estimated_hours} onChange={handleChange} min={0} step={0.5} />
                </div>
                <div className="form-group">
                  <label>Actual Hours</label>
                  <input type="number" name="actual_hours" value={form.actual_hours} onChange={handleChange} min={0} step={0.5} />
                </div>
                <div className="form-group">
                  <label>Due Date</label>
                  <input type="date" name="due_date" value={form.due_date} onChange={handleChange} />
                </div>
              </div>

              <div className="modal-actions">
                <button type="button" className="secondary-button" onClick={closeModal}>Cancel</button>
                <button type="submit" className="primary-button" disabled={saving} id="save-task-btn">
                  {saving ? 'Saving...' : editingTask ? 'Update Task' : 'Create Task'}
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
            <h3>Delete Task?</h3>
            <p>This action cannot be undone.</p>
            <div className="modal-actions">
              <button className="secondary-button" onClick={() => setDeleteId(null)}>Cancel</button>
              <button className="danger-button" onClick={() => handleDelete(deleteId)} id="confirm-delete-task">Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Tasks;
