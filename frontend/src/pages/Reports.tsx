import React, { useEffect, useState } from 'react';
import {
  FileText, Download, RefreshCw, Trash2, Clock, User,
  ChevronDown, ChevronUp, PlusCircle
} from 'lucide-react';
import api from '../services/api';
import './Reports.css';

interface Report {
  id: string;
  project_id: string;
  project_name: string;
  generated_by: string;
  generated_by_name: string;
  report_type: string;
  title: string;
  content: string;
  created_at: string | null;
}

interface Project {
  id: string;
  name: string;
}

const formatDate = (val: string | null) => {
  if (!val) return '—';
  try {
    return new Date(val).toLocaleString('en-IN', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  } catch { return String(val); }
};

const Reports: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<string>('');
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    api.get('/projects/').then(res => {
      setProjects(res.data);
      if (res.data.length > 0) setSelectedProject(res.data[0].id);
    }).catch(console.error);
    fetchReports();
  }, []);

  const fetchReports = async (projectId?: string) => {
    setLoading(true);
    try {
      const params = projectId ? `?project_id=${projectId}` : '';
      const res = await api.get(`/reports/${params}`);
      setReports(res.data);
    } catch (err) {
      console.error('Failed to fetch reports', err);
    } finally {
      setLoading(false);
    }
  };

  const generateReport = async () => {
    if (!selectedProject) return;
    setGenerating(true);
    try {
      const res = await api.post(`/reports/generate/${selectedProject}`);
      setReports(prev => [res.data, ...prev]);
      setExpanded(res.data.id);
    } catch (err) {
      console.error('Report generation failed', err);
    } finally {
      setGenerating(false);
    }
  };

  const deleteReport = async (id: string) => {
    if (!window.confirm('Delete this report?')) return;
    setDeleting(id);
    try {
      await api.delete(`/reports/${id}`);
      setReports(prev => prev.filter(r => r.id !== id));
    } catch (err) {
      console.error('Delete failed', err);
    } finally {
      setDeleting(null);
    }
  };

  const downloadReport = (report: Report) => {
    const blob = new Blob([report.content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${report.title.replace(/[^a-z0-9]/gi, '_')}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const filteredReports = selectedProject
    ? reports.filter(r => r.project_id === selectedProject)
    : reports;

  return (
    <div className="reports-page">
      <div className="page-header flex-between">
        <div>
          <h1>
            <FileText size={26} style={{ display: 'inline', marginRight: '0.5rem', verticalAlign: 'middle' }} />
            Project Reports
          </h1>
          <p>AI-generated executive summaries from live MongoDB project data</p>
        </div>
        <div className="reports-actions">
          <select
            className="project-select-report"
            value={selectedProject}
            onChange={e => setSelectedProject(e.target.value)}
          >
            <option value="">All Projects</option>
            {projects.map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <button className="outline-button" onClick={() => fetchReports(selectedProject || undefined)}>
            <RefreshCw size={14} style={{ display: 'inline', marginRight: '0.4rem' }} />
            Refresh
          </button>
          <button
            className="primary-button"
            onClick={generateReport}
            disabled={generating || !selectedProject}
          >
            <PlusCircle size={14} style={{ display: 'inline', marginRight: '0.4rem' }} />
            {generating ? 'Generating…' : 'Generate Report'}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="loading-state">Loading reports…</div>
      ) : filteredReports.length === 0 ? (
        <div className="empty-state glass-panel" style={{ marginTop: '2rem', display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '3rem', gap: '1rem', borderRadius: 14 }}>
          <FileText size={48} style={{ color: '#475569' }} />
          <h3 style={{ color: '#e2e8f0', margin: 0 }}>No reports yet</h3>
          <p style={{ color: '#94a3b8', margin: 0, textAlign: 'center', maxWidth: 360 }}>
            Select a project and click "Generate Report" to create a comprehensive AI decision intelligence summary.
          </p>
        </div>
      ) : (
        <div className="reports-list">
          {filteredReports.map(report => (
            <div key={report.id} className="report-card glass-panel">
              <div className="report-card-header" onClick={() => setExpanded(expanded === report.id ? null : report.id)}>
                <div className="report-info">
                  <FileText size={20} className="report-file-icon" />
                  <div>
                    <h3 className="report-title">{report.title}</h3>
                    <div className="report-meta">
                      <span><User size={12} /> {report.generated_by_name || 'Manager'}</span>
                      <span><Clock size={12} /> {formatDate(report.created_at)}</span>
                      {report.project_name && (
                        <span className="project-tag">{report.project_name}</span>
                      )}
                      <span className="report-type-tag">{report.report_type?.replace(/_/g, ' ')}</span>
                    </div>
                  </div>
                </div>
                <div className="report-actions">
                  <button
                    className="icon-btn"
                    title="Download as Markdown"
                    onClick={e => { e.stopPropagation(); downloadReport(report); }}
                  >
                    <Download size={16} />
                  </button>
                  <button
                    className="icon-btn danger"
                    title="Delete report"
                    disabled={deleting === report.id}
                    onClick={e => { e.stopPropagation(); deleteReport(report.id); }}
                  >
                    <Trash2 size={16} />
                  </button>
                  {expanded === report.id ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                </div>
              </div>

              {expanded === report.id && (
                <div className="report-content">
                  <pre className="report-markdown">{report.content}</pre>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Reports;
