import React, { useEffect, useState } from 'react';
import { Upload, FileText, AlertCircle, Bot, CheckCircle } from 'lucide-react';
import api from '../services/api';
import './DocumentAI.css';

const DocumentAI: React.FC = () => {
  const [documents, setDocuments] = useState<any[]>([]);
  const [projects, setProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [uploading, setUploading] = useState(false);
  const [selectedProject, setSelectedProject] = useState('');
  const [file, setFile] = useState<File | null>(null);

  const fetchData = async () => {
    try {
      const [docsRes, projRes] = await Promise.all([
        api.get('/documents/'),
        api.get('/projects/')
      ]);
      
      const enrichedDocs = await Promise.all(docsRes.data.map(async (doc: any) => {
        try {
          const analysisRes = await api.get(`/documents/analysis/${doc.id}`);
          return { ...doc, analysis: analysisRes.data };
        } catch (e) {
          return { ...doc, analysis: null };
        }
      }));
      
      setDocuments(enrichedDocs);
      setProjects(projRes.data);
      if (projRes.data.length > 0 && !selectedProject) {
        setSelectedProject(projRes.data[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !selectedProject) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', selectedProject);

    try {
      // 1. Upload
      const uploadRes = await api.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      
      // 2. Trigger Analysis
      await api.post(`/documents/analyze/${uploadRes.data.id}`);
      
      setFile(null);
      fetchData();
    } catch (err) {
      console.error('Upload failed', err);
    } finally {
      setUploading(false);
    }
  };

  if (loading) return <div className="loading-state">Loading document intelligence...</div>;

  return (
    <div className="doc-ai-page">
      <div className="page-header">
        <h1>Document Intelligence</h1>
        <p>AI-powered requirement analysis and issue detection</p>
      </div>

      <div className="upload-section glass-panel">
        <div className="upload-header">
          <Upload size={20} className="text-primary" />
          <h3>Analyze New Document</h3>
        </div>
        
        <form onSubmit={handleUpload} className="upload-form">
          <div className="form-row">
            <div className="form-group">
              <label>Target Project</label>
              <select 
                value={selectedProject} 
                onChange={(e) => setSelectedProject(e.target.value)}
                required
              >
                <option value="">Select a project...</option>
                {projects.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
            
            <div className="form-group file-group">
              <label>Document (PDF, DOCX, TXT, CSV)</label>
              <input 
                type="file" 
                accept=".pdf,.docx,.txt,.csv,.xlsx"
                onChange={handleFileChange}
                required
              />
            </div>
          </div>
          
          <button type="submit" disabled={uploading || !file} className="primary-button upload-btn">
            {uploading ? 'Processing & Analyzing...' : 'Upload & Analyze'}
          </button>
        </form>
      </div>

      <div className="documents-list">
        <h2>Analyzed Documents</h2>
        {documents.length === 0 ? (
          <p className="text-muted">No documents analyzed yet.</p>
        ) : (
          <div className="docs-grid">
            {documents.map((doc) => (
              <div key={doc.id} className="doc-card glass-panel">
                <div className="doc-header">
                  <FileText size={24} className="text-primary" />
                  <div className="doc-info">
                    <h3>{doc.original_filename}</h3>
                    <p>Uploaded {new Date(doc.created_at).toLocaleDateString()}</p>
                  </div>
                </div>

                {doc.analysis ? (
                  <div className="analysis-results">
                    <div className="analysis-summary">
                      <div className="mode-badge">
                        <Bot size={14} />
                        {doc.analysis.analysis_mode} MODE
                      </div>
                      <p>{doc.analysis.summary}</p>
                    </div>

                    {doc.analysis.issues && doc.analysis.issues.length > 0 ? (
                      <div className="issues-list">
                        <h4>Detected Issues ({doc.analysis.total_issues})</h4>
                        {doc.analysis.issues.map((issue: any, idx: number) => (
                          <div key={idx} className={`issue-item severity-${issue.severity}`}>
                            <div className="issue-header">
                              <AlertCircle size={14} />
                              <strong>{issue.title}</strong>
                            </div>
                            <p className="issue-desc">{issue.description}</p>
                            <div className="issue-meta">
                              <span className="domain-badge">{issue.domain}</span>
                              <span className="action-req">→ Consult: {issue.recommended_specialist}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="no-issues">
                        <CheckCircle size={20} className="text-success" />
                        <p>No critical issues detected in this document.</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="analysis-pending">
                    <p>Analysis pending or failed.</p>
                    <button 
                      className="analyze-button"
                      onClick={async () => {
                        await api.post(`/documents/analyze/${doc.id}`);
                        fetchData();
                      }}
                    >
                      Retry Analysis
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default DocumentAI;
