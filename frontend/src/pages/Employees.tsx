import React, { useEffect, useState } from 'react';
import { ShieldAlert, Flame, BrainCircuit, Activity, UserPlus } from 'lucide-react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
import './Employees.css';

const Employees: React.FC = () => {
  const [employees, setEmployees] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const { user } = useAuth();

  const isManager = user?.role === 'project_manager' || user?.role === 'admin';

  const fetchEmployees = async () => {
    try {
      const response = await api.get('/employees/');

      const enriched = await Promise.all(response.data.map(async (emp: any) => {
        try {
          const predRes = await api.get(`/employee-risk/${emp.id}/latest`);
          return { ...emp, risk: predRes.data };
        } catch (e) {
          return { ...emp, risk: null };
        }
      }));

      setEmployees(enriched);
    } catch (err) {
      console.error('Failed to fetch employees', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEmployees();
  }, []);

  const getRiskColor = (level: string) => {
    if (level === 'HIGH') return 'var(--error)';
    if (level === 'MEDIUM') return 'var(--warning)';
    return 'var(--success)';
  };

  if (loading) return <div className="loading-state">Loading employees...</div>;

  return (
    <div className="employees-page">
      <div className="page-header flex-between">
        <div>
          <h1>Team Intelligence</h1>
          <p>Workload and burnout risk monitoring</p>
        </div>
        {/* Only admin / project_manager can add members */}
        {isManager && (
          <button className="primary-button" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <UserPlus size={16} />
            Add Member
          </button>
        )}
      </div>

      <div className="employees-grid">
        {employees.map((emp) => (
          <div key={emp.id} className="employee-card glass-panel">
            <div className="emp-header">
              <div className="emp-avatar">{emp.name.charAt(0)}</div>
              <div className="emp-info">
                <h3>{emp.name}</h3>
                <p>{emp.role}</p>
              </div>
              <span className={`status-dot ${emp.status}`} />
            </div>

            {/* Specialization badge */}
            {emp.specialization && (
              <div className="emp-specialization">
                <span className="spec-label">Specialization</span>
                <span className="spec-value">{emp.specialization}</span>
              </div>
            )}

            <div className="skills-container">
              {emp.skills.map((skill: string) => (
                <span key={skill} className="skill-badge">{skill}</span>
              ))}
            </div>

            <div className="emp-capacity">
              <span className="label">Weekly Capacity</span>
              <span className="value">{emp.weekly_capacity_hours}h</span>
            </div>

            {emp.risk && (
              <div className="burnout-insights" style={{ borderLeftColor: getRiskColor(emp.risk.risk_level) }}>
                <div className="burnout-header">
                  <div className="flex-center gap-2">
                    <Flame size={16} color={getRiskColor(emp.risk.risk_level)} />
                    <span style={{ color: getRiskColor(emp.risk.risk_level), fontWeight: 600 }}>
                      {emp.risk.risk_level} BURNOUT RISK
                    </span>
                  </div>
                  <span className="prob-value">{(emp.risk.risk_probability * 100).toFixed(0)}%</span>
                </div>

                <ul className="factors-list">
                  {emp.risk.contributing_factors.slice(0, 3).map((factor: string, i: number) => (
                    <li key={i}>{factor}</li>
                  ))}
                </ul>
              </div>
            )}

            {!emp.risk && (
              <div className="burnout-insights empty">
                <button
                  className="analyze-button"
                  onClick={async () => {
                    await api.post(`/employee-risk/analyze/${emp.id}`);
                    fetchEmployees();
                  }}
                >
                  <BrainCircuit size={16} />
                  Analyze Workload Risk
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default Employees;
