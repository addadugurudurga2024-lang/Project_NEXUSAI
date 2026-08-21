import React, { useEffect, useState } from 'react';
import { BrainCircuit, AlertTriangle, ArrowRight, CheckCircle, Zap, Check, X } from 'lucide-react';
import api from '../services/api';
import './Recommendations.css';

const Recommendations: React.FC = () => {
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchRecommendations = async () => {
    try {
      const response = await api.get('/recommendations/');
      const sorted = response.data.sort((a: any, b: any) => {
        const pOrder: any = { critical: 0, high: 1, medium: 2, low: 3 };
        return pOrder[a.priority] - pOrder[b.priority];
      });
      setRecommendations(sorted);
    } catch (err) {
      console.error('Failed to fetch recommendations', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecommendations();
  }, []);

  const handleAction = async (id: string, action: 'accept' | 'reject' | 'complete') => {
    try {
      await api.post(`/recommendations/${id}/${action}`);
      fetchRecommendations();
    } catch (err) {
      console.error(`Failed to ${action} recommendation`, err);
    }
  };

  if (loading) return <div className="loading-state">Loading AI Insights...</div>;

  return (
    <div className="recs-page">
      <div className="page-header flex-between">
        <div>
          <h1>AI Decision Intelligence</h1>
          <p>Actionable recommendations based on real-time project metrics</p>
        </div>
        <button 
          className="primary-button"
          onClick={() => {
            setLoading(true);
            fetchRecommendations();
          }}
        >
          <Zap size={16} style={{ display: 'inline', marginRight: '0.5rem' }} />
          Refresh Insights
        </button>
      </div>

      <div className="recs-list">
        {recommendations.length === 0 ? (
          <div className="glass-panel p-4 text-center">No recommendations available. Run analysis on projects first.</div>
        ) : (
          recommendations.map((rec) => (
            <div key={rec.id} className={`rec-card glass-panel priority-${rec.priority}`}>
              <div className="rec-header">
                <div className="rec-title-group">
                  {rec.priority === 'critical' ? (
                    <AlertTriangle size={24} className="text-error" />
                  ) : rec.priority === 'high' ? (
                    <AlertTriangle size={24} className="text-warning" />
                  ) : (
                    <CheckCircle size={24} className="text-success" />
                  )}
                  <div>
                    <h3>{rec.title}</h3>
                    <span className="rec-category">{rec.category}</span>
                    {rec.status && rec.status !== 'pending' && (
                      <span className={`status-badge ml-2 status-${rec.status}`}>{rec.status}</span>
                    )}
                  </div>
                </div>
                <div className="rec-meta">
                  <span className="project-name">{rec.project_name}</span>
                  <span className={`priority-badge ${rec.priority}`}>{rec.priority}</span>
                </div>
              </div>

              <div className="rec-body">
                <div className="rec-reason">
                  <strong>Why?</strong>
                  <p>{rec.reason}</p>
                </div>
                
                <div className="rec-impact">
                  <strong>Expected Impact</strong>
                  <p className="flex-center gap-2">
                    <ArrowRight size={14} className="text-primary" />
                    {rec.expected_impact}
                  </p>
                </div>
              </div>
              
              <div className="rec-actions">
                {rec.status === 'pending' && (
                  <>
                    <button className="outline-button" onClick={() => handleAction(rec.id, 'reject')}>
                      <X size={14} style={{ display: 'inline', marginRight: '0.25rem' }} />
                      Reject
                    </button>
                    <button className="primary-button" style={{ padding: '0.5rem 1rem' }} onClick={() => handleAction(rec.id, 'accept')}>
                      <Check size={14} style={{ display: 'inline', marginRight: '0.25rem' }} />
                      Accept
                    </button>
                  </>
                )}
                {rec.status === 'accepted' && (
                  <button className="primary-button" style={{ padding: '0.5rem 1rem' }} onClick={() => handleAction(rec.id, 'complete')}>
                    <CheckCircle size={14} style={{ display: 'inline', marginRight: '0.25rem' }} />
                    Mark as Completed
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default Recommendations;
