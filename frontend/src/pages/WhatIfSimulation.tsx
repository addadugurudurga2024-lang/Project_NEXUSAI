import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Sliders,
  Sparkles,
  Shield,
  AlertTriangle,
  Users,
  Clock,
  DollarSign,
  Briefcase,
  Play,
  Scale,
  Minus,
  CheckSquare,
  Square,
  FileCheck,
} from 'lucide-react';
import api from '../services/api';
import './WhatIfSimulation.css';

const SCENARIO_TYPES = [
  { id: 'RESOURCE_ADD', label: 'Add Resources', icon: Users, desc: 'Add engineers or specialists to boost capacity' },
  { id: 'RESOURCE_REMOVE', label: 'Remove Resource', icon: Minus, desc: 'Simulate departure or down-sizing impact' },
  { id: 'RESOURCE_REALLOCATION', label: 'Borrow Specialist', icon: Sparkles, desc: 'Simulate cross-PM candidate allocation' },
  { id: 'TASK_REALLOCATION', label: 'Reallocate Task', icon: Sliders, desc: 'Hand over task hours between team members' },
  { id: 'SCOPE_REDUCTION', label: 'Descope Tasks', icon: CheckSquare, desc: 'Simulate removing non-critical backlog items' },
  { id: 'SCHEDULE_CAPACITY_CHANGE', label: 'Velocity Boost', icon: Clock, desc: 'Simulate sprint throughput acceleration' },
  { id: 'BUDGET_RESOURCE_CHANGE', label: 'Budget Adjustment', icon: DollarSign, desc: 'Adjust project budget funding runway' },
];

const WhatIfSimulation: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [projects, setProjects] = useState<any[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [projectOptions, setProjectOptions] = useState<any | null>(null);
  const [loadingOptions, setLoadingOptions] = useState<boolean>(false);

  // Active Scenario Configuration
  const [selectedScenarioType, setSelectedScenarioType] = useState<string>('RESOURCE_ADD');
  const [resourceCount, setResourceCount] = useState<number>(1);
  const [resourceRole, setResourceRole] = useState<string>('AI Engineer');
  const [resourceWeeklyHours, setResourceWeeklyHours] = useState<number>(40);
  const [removeEmployeeId, setRemoveEmployeeId] = useState<string>('');
  const [reallocCandidateId, setReallocCandidateId] = useState<string>('');
  const [reallocTaskId, setReallocTaskId] = useState<string>('');
  const [fromEmployeeId, setFromEmployeeId] = useState<string>('');
  const [toEmployeeId, setToEmployeeId] = useState<string>('');
  const [taskHours, setTaskHours] = useState<number>(16);
  const [selectedDescopeTaskIds, setSelectedDescopeTaskIds] = useState<string[]>([]);
  const [velocityBoostPct, setVelocityBoostPct] = useState<number>(25);
  const [budgetChangeAmount, setBudgetChangeAmount] = useState<number>(50000);

  // Simulation Results
  const [simulationResult, setSimulationResult] = useState<any | null>(null);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [simulationError, setSimulationError] = useState<string>('');

  // Initial Load
  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const res = await api.get('/projects/');
        const projs = res.data || [];
        setProjects(projs);

        const qPid = searchParams.get('projectId');
        const qScenario = searchParams.get('scenarioType');

        if (qPid && projs.some((p: any) => (p.id || p._id) === qPid)) {
          setSelectedProjectId(qPid);
        } else if (projs.length > 0) {
          setSelectedProjectId(projs[0].id || projs[0]._id);
        }

        if (qScenario && SCENARIO_TYPES.some((s) => s.id === qScenario)) {
          setSelectedScenarioType(qScenario);
        }
      } catch (err) {
        console.error('Failed to fetch projects for simulation:', err);
      }
    };
    fetchProjects();
  }, [searchParams]);

  // Fetch project simulation options (tasks, team members, candidates)
  useEffect(() => {
    if (!selectedProjectId) return;
    const fetchOptions = async () => {
      setLoadingOptions(true);
      try {
        const res = await api.get(`/simulations/options/${selectedProjectId}`);
        setProjectOptions(res.data);
        if (res.data.team_members?.length > 0) {
          setRemoveEmployeeId(res.data.team_members[0].id);
          setFromEmployeeId(res.data.team_members[0].id);
          if (res.data.team_members.length > 1) {
            setToEmployeeId(res.data.team_members[1].id);
          }
        }
        if (res.data.active_tasks?.length > 0) {
          setReallocTaskId(res.data.active_tasks[0].id);
        }
        if (res.data.available_candidates?.length > 0) {
          setReallocCandidateId(res.data.available_candidates[0].candidate_employee_id);
        }
      } catch (err) {
        console.error('Failed to fetch project simulation options:', err);
      } finally {
        setLoadingOptions(false);
      }
    };
    fetchOptions();
  }, [selectedProjectId]);

  // Run Simulation
  const handleRunSimulation = async () => {
    if (!selectedProjectId) return;
    setIsSimulating(true);
    setSimulationError('');

    let parameters: any = {};
    if (selectedScenarioType === 'RESOURCE_ADD') {
      parameters = {
        count: resourceCount,
        role: resourceRole,
        weekly_capacity_hours: resourceWeeklyHours,
        hourly_rate: 75.0,
      };
    } else if (selectedScenarioType === 'RESOURCE_REMOVE') {
      parameters = {
        count: 1,
        employee_id: removeEmployeeId,
      };
    } else if (selectedScenarioType === 'RESOURCE_REALLOCATION') {
      const cand = (projectOptions?.available_candidates || []).find(
        (c: any) => c.candidate_employee_id === reallocCandidateId
      );
      parameters = {
        candidate_employee_id: reallocCandidateId,
        candidate_name: cand?.candidate_name || 'Cross-PM Specialist',
        candidate_role: cand?.candidate_role || 'Specialist',
        weekly_capacity_hours: 40.0,
      };
    } else if (selectedScenarioType === 'TASK_REALLOCATION') {
      parameters = {
        task_id: reallocTaskId,
        task_hours: taskHours,
        from_employee_id: fromEmployeeId,
        to_employee_id: toEmployeeId,
      };
    } else if (selectedScenarioType === 'SCOPE_REDUCTION') {
      parameters = {
        task_ids: selectedDescopeTaskIds,
        count: selectedDescopeTaskIds.length || 3,
        hours_reduced: selectedDescopeTaskIds.length ? selectedDescopeTaskIds.length * 12.0 : 36.0,
      };
    } else if (selectedScenarioType === 'SCHEDULE_CAPACITY_CHANGE') {
      parameters = {
        velocity_boost_pct: velocityBoostPct,
      };
    } else if (selectedScenarioType === 'BUDGET_RESOURCE_CHANGE') {
      parameters = {
        budget_change_amount: budgetChangeAmount,
      };
    }

    try {
      const res = await api.post('/simulations/run', {
        project_id: selectedProjectId,
        scenario_type: selectedScenarioType,
        parameters,
      });
      setSimulationResult(res.data);
    } catch (err: any) {
      console.error('Simulation execution failed:', err);
      setSimulationError(err.response?.data?.detail || 'Simulation execution failed.');
    } finally {
      setIsSimulating(false);
    }
  };

  const toggleDescopeTask = (taskId: string) => {
    if (selectedDescopeTaskIds.includes(taskId)) {
      setSelectedDescopeTaskIds(selectedDescopeTaskIds.filter((id) => id !== taskId));
    } else {
      setSelectedDescopeTaskIds([...selectedDescopeTaskIds, taskId]);
    }
  };

  return (
    <div className="whatif-page">
      {/* HEADER */}
      <div className="whatif-header">
        <div className="whatif-title-area">
          <h1>
            <Sliders size={26} className="text-primary" />
            What-If Simulation &amp; Scenario Analysis
          </h1>
          <p>Test hypothetical project, resource, schedule, and scope decisions in-memory before taking formal action.</p>
        </div>
        <div className="simulation-mode-badge">
          <Sparkles size={14} />
          In-Memory Simulation Engine
        </div>
      </div>

      {/* SAFETY BANNER */}
      <div className="simulation-safety-banner">
        <div className="safety-banner-left">
          <div className="safety-banner-icon">
            <Shield size={20} />
          </div>
          <div className="safety-banner-text">
            <h4>Isolated Simulation Sandbox (Zero Live Mutation)</h4>
            <p>What-If simulations operate on a read-only project snapshot. Live projects, tasks, employees, and databases remain 100% untouched.</p>
          </div>
        </div>
      </div>

      {/* SCENARIO BUILDER CONTAINER */}
      <div className="scenario-builder-grid">
        {/* LEFT COLUMN: Project & Scenario Selector */}
        <div className="builder-panel">
          <h3>
            <Briefcase size={18} className="text-primary" />
            Select Project
          </h3>

          <div className="form-group">
            <label>Active Project Portfolio</label>
            <select
              className="form-select"
              value={selectedProjectId}
              onChange={(e) => {
                setSelectedProjectId(e.target.value);
                setSimulationResult(null);
              }}
            >
              {projects.map((p) => (
                <option key={p.id || p._id} value={p.id || p._id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          <h3 style={{ marginTop: '1.5rem' }}>
            <Sliders size={18} className="text-primary" />
            Choose Scenario Type
          </h3>

          <div className="scenario-type-list">
            {SCENARIO_TYPES.map((st) => {
              const IconComp = st.icon;
              const isActive = selectedScenarioType === st.id;
              return (
                <button
                  key={st.id}
                  className={`scenario-type-btn ${isActive ? 'active' : ''}`}
                  onClick={() => {
                    setSelectedScenarioType(st.id);
                    setSimulationResult(null);
                  }}
                >
                  <IconComp size={16} />
                  <div>
                    <div style={{ fontWeight: 600 }}>{st.label}</div>
                    <div style={{ fontSize: '0.74rem', color: '#94a3b8' }}>{st.desc}</div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* RIGHT COLUMN: Scenario Parameter Configuration */}
        <div className="builder-panel">
          <h3>
            <Sparkles size={18} className="text-primary" />
            Configure Scenario Parameters
          </h3>

          {/* SCENARIO 1: RESOURCE_ADD */}
          {selectedScenarioType === 'RESOURCE_ADD' && (
            <div className="scenario-config-box">
              <h4>Add Additional Engineering Capacity</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label>Quantity of Resources</label>
                  <input
                    type="number"
                    min="1"
                    max="10"
                    className="form-control"
                    value={resourceCount}
                    onChange={(e) => setResourceCount(parseInt(e.target.value) || 1)}
                  />
                </div>
                <div className="form-group">
                  <label>Specialization / Role</label>
                  <select
                    className="form-select"
                    value={resourceRole}
                    onChange={(e) => setResourceRole(e.target.value)}
                  >
                    <option value="AI Engineer">AI Engineer</option>
                    <option value="ML Engineer">ML Engineer</option>
                    <option value="Senior Backend Engineer">Senior Backend Engineer</option>
                    <option value="Full Stack Engineer">Full Stack Engineer</option>
                    <option value="DevOps Specialist">DevOps Specialist</option>
                    <option value="QA Lead">QA Lead</option>
                  </select>
                </div>
              </div>
              <div className="form-group">
                <label>Weekly Capacity Hours Per Member</label>
                <input
                  type="number"
                  min="10"
                  max="60"
                  className="form-control"
                  value={resourceWeeklyHours}
                  onChange={(e) => setResourceWeeklyHours(parseFloat(e.target.value) || 40)}
                />
              </div>
            </div>
          )}

          {/* SCENARIO 2: RESOURCE_REMOVE */}
          {selectedScenarioType === 'RESOURCE_REMOVE' && (
            <div className="scenario-config-box">
              <h4>Simulate Resource Down-Sizing or Departure</h4>
              <div className="form-group">
                <label>Select Team Member to Remove from Simulation</label>
                <select
                  className="form-select"
                  value={removeEmployeeId}
                  onChange={(e) => setRemoveEmployeeId(e.target.value)}
                >
                  {(projectOptions?.team_members || []).map((m: any) => (
                    <option key={m.id} value={m.id}>
                      {m.name} ({m.role} • {m.workload_ratio}% load)
                    </option>
                  ))}
                </select>
              </div>
            </div>
          )}

          {/* SCENARIO 3: RESOURCE_REALLOCATION */}
          {selectedScenarioType === 'RESOURCE_REALLOCATION' && (
            <div className="scenario-config-box">
              <h4>Borrow Cross-PM Specialist to Close Gap</h4>
              <div className="form-group">
                <label>Select Discovered Candidate Specialist</label>
                {projectOptions?.available_candidates?.length > 0 ? (
                  <select
                    className="form-select"
                    value={reallocCandidateId}
                    onChange={(e) => setReallocCandidateId(e.target.value)}
                  >
                    {projectOptions.available_candidates.map((c: any) => (
                      <option key={c.candidate_employee_id} value={c.candidate_employee_id}>
                        {c.candidate_name} ({c.candidate_role} • Home PM: {c.home_pm_name} • Match: {c.suitability_score}/100)
                      </option>
                    ))}
                  </select>
                ) : (
                  <p style={{ fontSize: '0.85rem', color: '#f59e0b' }}>
                    No cross-PM candidate recommendations found for this project's active gaps.
                  </p>
                )}
              </div>
            </div>
          )}

          {/* SCENARIO 4: TASK_REALLOCATION */}
          {selectedScenarioType === 'TASK_REALLOCATION' && (
            <div className="scenario-config-box">
              <h4>Hand Over Task Workload Between Engineers</h4>
              <div className="form-group">
                <label>Select Task to Reallocate</label>
                <select
                  className="form-select"
                  value={reallocTaskId}
                  onChange={(e) => setReallocTaskId(e.target.value)}
                >
                  {(projectOptions?.active_tasks || []).map((t: any) => (
                    <option key={t.id} value={t.id}>
                      {t.title} ({t.estimated_hours}h • Assignee: {t.assignee_name})
                    </option>
                  ))}
                </select>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label>From Engineer</label>
                  <select
                    className="form-select"
                    value={fromEmployeeId}
                    onChange={(e) => setFromEmployeeId(e.target.value)}
                  >
                    {(projectOptions?.team_members || []).map((m: any) => (
                      <option key={m.id} value={m.id}>
                        {m.name} ({m.workload_ratio}% load)
                      </option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>To Engineer</label>
                  <select
                    className="form-select"
                    value={toEmployeeId}
                    onChange={(e) => setToEmployeeId(e.target.value)}
                  >
                    {(projectOptions?.team_members || []).map((m: any) => (
                      <option key={m.id} value={m.id}>
                        {m.name} ({m.workload_ratio}% load)
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="form-group" style={{ marginTop: '0.75rem' }}>
                <label>Task Effort Hours to Reallocate</label>
                <input
                  type="number"
                  min="1"
                  max="120"
                  className="form-control"
                  value={taskHours}
                  onChange={(e) => setTaskHours(parseFloat(e.target.value) || 16)}
                />
              </div>
            </div>
          )}

          {/* SCENARIO 5: SCOPE_REDUCTION */}
          {selectedScenarioType === 'SCOPE_REDUCTION' && (
            <div className="scenario-config-box">
              <h4>Descope Non-Critical Tasks from Sprint</h4>
              <p style={{ fontSize: '0.82rem', color: '#94a3b8', marginBottom: '0.75rem' }}>
                Select specific tasks to remove from the simulated schedule:
              </p>
              <div style={{ maxHeight: '200px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                {(projectOptions?.active_tasks || []).map((t: any) => {
                  const isChecked = selectedDescopeTaskIds.includes(t.id);
                  return (
                    <div
                      key={t.id}
                      onClick={() => toggleDescopeTask(t.id)}
                      style={{
                        padding: '0.5rem 0.75rem',
                        borderRadius: 6,
                        background: isChecked ? 'rgba(99, 102, 241, 0.15)' : 'rgba(15, 23, 42, 0.5)',
                        border: isChecked ? '1px solid #6366f1' : '1px solid rgba(255, 255, 255, 0.05)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        cursor: 'pointer',
                        fontSize: '0.85rem',
                      }}
                    >
                      {isChecked ? <CheckSquare size={16} className="text-primary" /> : <Square size={16} style={{ color: '#64748b' }} />}
                      <span style={{ flex: 1 }}>{t.title}</span>
                      <span style={{ fontSize: '0.75rem', color: t.is_overdue ? '#f87171' : '#94a3b8' }}>
                        {t.estimated_hours}h {t.is_overdue ? '• Overdue' : ''}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* SCENARIO 6: SCHEDULE_CAPACITY_CHANGE */}
          {selectedScenarioType === 'SCHEDULE_CAPACITY_CHANGE' && (
            <div className="scenario-config-box">
              <h4>Sprint Velocity Acceleration</h4>
              <div className="form-group">
                <label>Projected Velocity Boost (+%): {velocityBoostPct}%</label>
                <input
                  type="range"
                  min="5"
                  max="50"
                  step="5"
                  className="form-control"
                  value={velocityBoostPct}
                  onChange={(e) => setVelocityBoostPct(parseInt(e.target.value) || 20)}
                />
              </div>
            </div>
          )}

          {/* SCENARIO 7: BUDGET_RESOURCE_CHANGE */}
          {selectedScenarioType === 'BUDGET_RESOURCE_CHANGE' && (
            <div className="scenario-config-box">
              <h4>Budget Funding Expansion</h4>
              <div className="form-group">
                <label>Additional Budget Allocation ($)</label>
                <input
                  type="number"
                  min="10000"
                  step="5000"
                  className="form-control"
                  value={budgetChangeAmount}
                  onChange={(e) => setBudgetChangeAmount(parseFloat(e.target.value) || 50000)}
                />
              </div>
            </div>
          )}

          {simulationError && (
            <div style={{ color: '#f87171', fontSize: '0.85rem', marginBottom: '0.75rem' }}>
              <AlertTriangle size={14} style={{ display: 'inline', marginRight: 4 }} />
              {simulationError}
            </div>
          )}

          <button
            className="btn-run-simulation"
            onClick={handleRunSimulation}
            disabled={isSimulating || loadingOptions}
          >
            {isSimulating ? (
              <>Running In-Memory Analysis...</>
            ) : (
              <>
                <Play size={16} />
                Run What-If Simulation
              </>
            )}
          </button>
        </div>
      </div>

      {/* RESULTS DISPLAY */}
      {simulationResult && (
        <div className="simulation-results-container">
          {/* COMPARISON KPI GRID */}
          <div className="comparison-grid">
            {simulationResult.comparison.map((m: any) => (
              <div key={m.metric_key} className={`comparison-card ${m.sentiment}`}>
                <div className="metric-title">{m.label}</div>
                <div className="metric-comparison-row">
                  <span className="metric-simulated-val">
                    {typeof m.simulated_value === 'number'
                      ? m.simulated_value.toLocaleString()
                      : m.simulated_value}
                    <span style={{ fontSize: '0.85rem', fontWeight: 500, color: '#94a3b8', marginLeft: 3 }}>
                      {m.unit}
                    </span>
                  </span>
                  <span className={`metric-delta-tag delta-${m.sentiment}`}>
                    {typeof m.delta === 'number' && m.delta > 0 ? `+${m.delta}` : m.delta}
                    {typeof m.delta === 'number' ? m.unit : ''}
                  </span>
                </div>
                <div className="metric-baseline-sub">
                  Current baseline: {m.baseline_value} {m.unit}
                </div>
              </div>
            ))}
          </div>

          {/* SIDE-BY-SIDE BASELINE VS SIMULATED STATE MATRIX */}
          <div className="state-matrix-grid">
            {/* BASELINE COLUMN */}
            <div className="matrix-column">
              <div className="matrix-col-header">
                <h3>Current Live Baseline</h3>
                <span className="col-badge badge-baseline">Live MongoDB State</span>
              </div>
              <div className="matrix-stats-list">
                <div className="matrix-stat-item">
                  <span className="matrix-stat-label">Team Size:</span>
                  <span className="matrix-stat-val">{simulationResult.baseline.team_size} members</span>
                </div>
                <div className="matrix-stat-item">
                  <span className="matrix-stat-label">Weekly Capacity:</span>
                  <span className="matrix-stat-val">{simulationResult.baseline.total_capacity_hours} hrs</span>
                </div>
                <div className="matrix-stat-item">
                  <span className="matrix-stat-label">Team Workload:</span>
                  <span className="matrix-stat-val">{simulationResult.baseline.team_workload_pct}%</span>
                </div>
                <div className="matrix-stat-item">
                  <span className="matrix-stat-label">Predicted Schedule Delay:</span>
                  <span className="matrix-stat-val" style={{ color: simulationResult.baseline.delay_days > 5 ? '#f87171' : '#10b981' }}>
                    {simulationResult.baseline.delay_days} days
                  </span>
                </div>
                <div className="matrix-stat-item">
                  <span className="matrix-stat-label">ML Risk Class:</span>
                  <span className="matrix-stat-val">{simulationResult.baseline.risk_class}</span>
                </div>
                <div className="matrix-stat-item">
                  <span className="matrix-stat-label">Project Health Score:</span>
                  <span className="matrix-stat-val">{simulationResult.baseline.health_score}/100</span>
                </div>
                <div className="matrix-stat-item">
                  <span className="matrix-stat-label">Budget Utilization:</span>
                  <span className="matrix-stat-val">{simulationResult.baseline.budget_utilization_pct}%</span>
                </div>
              </div>
            </div>

            {/* SIMULATED COLUMN */}
            <div className="matrix-column simulated-col">
              <div className="matrix-col-header">
                <h3>Simulated Hypothetical State</h3>
                <span className="col-badge badge-simulated">What-If Projected</span>
              </div>
              <div className="matrix-stats-list">
                <div className="matrix-stat-item">
                  <span className="matrix-stat-label">Team Size:</span>
                  <span className="matrix-stat-val" style={{ color: '#818cf8' }}>
                    {simulationResult.simulated.team_size} members
                  </span>
                </div>
                <div className="matrix-stat-item">
                  <span className="matrix-stat-label">Weekly Capacity:</span>
                  <span className="matrix-stat-val" style={{ color: '#818cf8' }}>
                    {simulationResult.simulated.total_capacity_hours} hrs
                  </span>
                </div>
                <div className="matrix-stat-item">
                  <span className="matrix-stat-label">Team Workload:</span>
                  <span className="matrix-stat-val" style={{ color: simulationResult.simulated.team_workload_pct <= 95 ? '#34d399' : '#f87171' }}>
                    {simulationResult.simulated.team_workload_pct}%
                  </span>
                </div>
                <div className="matrix-stat-item">
                  <span className="matrix-stat-label">Predicted Schedule Delay:</span>
                  <span className="matrix-stat-val" style={{ color: simulationResult.simulated.delay_days < simulationResult.baseline.delay_days ? '#34d399' : '#f87171' }}>
                    {simulationResult.simulated.delay_days} days
                  </span>
                </div>
                <div className="matrix-stat-item">
                  <span className="matrix-stat-label">ML Risk Class:</span>
                  <span className="matrix-stat-val">{simulationResult.simulated.risk_class}</span>
                </div>
                <div className="matrix-stat-item">
                  <span className="matrix-stat-label">Project Health Score:</span>
                  <span className="matrix-stat-val" style={{ color: simulationResult.simulated.health_score >= simulationResult.baseline.health_score ? '#34d399' : '#f87171' }}>
                    {simulationResult.simulated.health_score}/100
                  </span>
                </div>
                <div className="matrix-stat-item">
                  <span className="matrix-stat-label">Budget Utilization:</span>
                  <span className="matrix-stat-val">{simulationResult.simulated.budget_utilization_pct}%</span>
                </div>
              </div>
            </div>
          </div>

          {/* EXPLANATION & INSIGHTS CARD */}
          <div className="explanation-card">
            <h3>
              <FileCheck size={20} className="text-primary" />
              Scenario Analysis &amp; Explainability Insights
            </h3>
            <p style={{ fontSize: '0.9rem', color: '#cbd5e1', marginBottom: '1.25rem' }}>
              <strong>What Changed:</strong> {simulationResult.explanation.what_changed}{' '}
              <strong>Why:</strong> {simulationResult.explanation.why_it_changed}
            </p>

            <div className="explanation-sections">
              <div className="exp-box improvements">
                <h4>What Improved</h4>
                <ul>
                  {simulationResult.explanation.what_improved.map((item: string, idx: number) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>

              <div className="exp-box worsened">
                <h4>Trade-offs / Regression</h4>
                <ul>
                  {simulationResult.explanation.what_worsened.map((item: string, idx: number) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>

              <div className="exp-box risks">
                <h4>Remaining Risks</h4>
                <ul>
                  {simulationResult.explanation.remaining_risks.map((item: string, idx: number) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>

              {simulationResult.explanation.recommendations_resolved?.length > 0 && (
                <div className="exp-box resolved">
                  <h4>Recommendations Resolved</h4>
                  <ul>
                    {simulationResult.explanation.recommendations_resolved.map((item: string, idx: number) => (
                      <li key={idx}>✓ {item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>

          {/* RECORD DECISION ACTION BAR */}
          <div className="simulation-action-bar">
            <div className="action-bar-left">
              <h4>Formalize What-If Scenario into a Management Decision?</h4>
              <p>Turn these simulation insights into an audited decision record in the Decision Log.</p>
            </div>
            <button
              className="btn-record-decision-action"
              onClick={() => {
                const title = `Approve ${simulationResult.scenario_title} based on What-If Simulation`;
                const desc = `${simulationResult.scenario_description}. ${simulationResult.explanation.what_changed}`;
                let dType = 'RESOURCE_REALLOCATION';
                if (simulationResult.scenario_type === 'SCOPE_REDUCTION') dType = 'SPRINT_RESCOPE';
                else if (simulationResult.scenario_type === 'SCHEDULE_CAPACITY_CHANGE') dType = 'SCHEDULE_COMPRESSION';
                else if (simulationResult.scenario_type === 'BUDGET_RESOURCE_CHANGE') dType = 'BUDGET_INVESTIGATION';

                navigate(
                  `/dashboard/decisions?projectId=${selectedProjectId}&title=${encodeURIComponent(
                    title
                  )}&type=${dType}&description=${encodeURIComponent(desc)}`
                );
              }}
            >
              <Scale size={16} />
              Record Formal Decision
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default WhatIfSimulation;
