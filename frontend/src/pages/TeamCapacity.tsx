import React, { useEffect, useState, useCallback } from 'react';
import {
  Users,
  UserCheck,
  UserX,
  AlertTriangle,
  Sparkles,
  CheckCircle,
  XCircle,
  Briefcase,
  Shield,
  Layers,
  Info,
  Clock,
  Send,
  RefreshCw,
  Mail,
  Calendar,
  Check,
} from 'lucide-react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
import './TeamCapacity.css';

interface CapabilityGap {
  type: string;
  name: string;
  status: string;
  description: string;
}

interface PendingRequest {
  id: string;
  pm_user_id: string;
  pm_name?: string;
  employee_id: string;
  candidate_name?: string;
  candidate_email?: string;
  candidate_role?: string;
  candidate_specialization?: string;
  candidate_skills?: string[];
  candidate_experience_years?: number;
  status: string;
  requested_at: string;
}

interface PMRecommendation {
  pm_user_id: string;
  pm_name: string;
  pm_email: string;
  pm_specialization: string;
  active_members_count: number;
  available_capacity: number;
  is_full: boolean;
  relevance_level: string;
  score: number;
  reasons: string[];
}

interface MemberStatusData {
  has_employee_profile: boolean;
  employee_id?: string;
  employee_name?: string;
  employee_email?: string;
  employee_role?: string;
  employee_skills?: string[];
  employee_specialization?: string;
  employee_weekly_capacity_hours?: number;
  status: 'active' | 'pending' | 'rejected' | 'none';
  pm_name?: string | null;
  pm_user_id?: string | null;
  pm_email?: string | null;
  pm_specialization?: string | null;
  rejection_reason?: string | null;
  requested_at?: string | null;
  reviewed_at?: string | null;
  assigned_at?: string | null;
  message?: string;
  all_requests?: any[];
}

const formatDate = (val?: string | null) => {
  if (!val) return '—';
  try {
    return new Date(val).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return String(val);
  }
};

const TeamCapacity: React.FC = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const isManager = user?.role === 'project_manager' || isAdmin;
  const isTeamMember = user?.role === 'team_member';

  // Manager state
  const [capacityData, setCapacityData] = useState<any>(null);
  const [pendingRequests, setPendingRequests] = useState<PendingRequest[]>([]);
  const [pmsList, setPmsList] = useState<any[]>([]);
  const [selectedPmId, setSelectedPmId] = useState<string>('');

  // Team member state
  const [memberStatus, setMemberStatus] = useState<MemberStatusData | null>(null);
  const [newPmSelection, setNewPmSelection] = useState<string>('');
  const [requestSubmitting, setRequestSubmitting] = useState(false);

  // Common state
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Recommendations Modal State
  const [analyzingCandidate, setAnalyzingCandidate] = useState<PendingRequest | null>(null);
  const [recommendationData, setRecommendationData] = useState<any>(null);
  const [recommendLoading, setRecommendLoading] = useState(false);

  const fetchManagerData = useCallback(async (pmId?: string) => {
    try {
      setLoading(true);
      setError(null);

      // Fetch PMs list for Admin selection or general overview
      const pmsRes = await api.get('/team-capacity/pms');
      setPmsList(pmsRes.data);

      // Fetch capacity details
      const capUrl = pmId ? `/team-capacity/my-capacity?pm_user_id=${pmId}` : '/team-capacity/my-capacity';
      const capRes = await api.get(capUrl);
      setCapacityData(capRes.data);

      // Fetch pending requests
      const reqRes = await api.get('/team-capacity/pending-requests');
      setPendingRequests(reqRes.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load team capacity data');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchMemberData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch PM list so member can request a new PM if needed
      const [statusRes, pmsRes] = await Promise.all([
        api.get('/team-capacity/my-status'),
        api.get('/team-capacity/pms'),
      ]);

      setMemberStatus(statusRes.data);
      setPmsList(pmsRes.data || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load team placement status');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isTeamMember) {
      fetchMemberData();
    } else {
      fetchManagerData(selectedPmId);
    }
  }, [isTeamMember, selectedPmId, fetchMemberData, fetchManagerData]);

  // PM Approve action
  const handleApprove = async (requestId: string) => {
    setActionLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await api.post(`/team-capacity/requests/${requestId}/approve`);
      setSuccessMsg('Candidate approved and assigned to active team!');
      await fetchManagerData(selectedPmId);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to approve candidate');
    } finally {
      setActionLoading(false);
    }
  };

  // PM Reject action
  const handleReject = async (requestId: string) => {
    setActionLoading(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await api.post(`/team-capacity/requests/${requestId}/reject`);
      setSuccessMsg('Candidate request rejected.');
      await fetchManagerData(selectedPmId);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reject candidate');
    } finally {
      setActionLoading(false);
    }
  };

  // AI Matching analysis
  const handleAnalyzeCandidate = async (req: PendingRequest) => {
    setAnalyzingCandidate(req);
    setRecommendLoading(true);
    try {
      const res = await api.get(`/team-capacity/analyze/${req.employee_id}`);
      setRecommendationData(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to generate recommendations');
    } finally {
      setRecommendLoading(false);
    }
  };

  // Team Member: Submit new PM request
  const handleSubmitNewRequest = async () => {
    if (!newPmSelection) {
      setError('Please select a Project Manager to submit request.');
      return;
    }
    setRequestSubmitting(true);
    setError(null);
    setSuccessMsg(null);
    try {
      await api.post(`/team-capacity/request/${newPmSelection}`);
      setSuccessMsg('Onboarding request submitted to Project Manager successfully!');
      setNewPmSelection('');
      await fetchMemberData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit PM request');
    } finally {
      setRequestSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="tc-container tc-loading">
        <Users className="animate-spin" size={32} />
        <p>Loading Team Capacity & Placement Intelligence…</p>
      </div>
    );
  }

  // ══════════════════════════════════════════════════════════════════════════
  // TEAM MEMBER VIEW (Authoritative Placement & Line Management Status)
  // ══════════════════════════════════════════════════════════════════════════
  if (isTeamMember) {
    const status = memberStatus?.status || 'none';
    const hasActive = status === 'active';
    const isPending = status === 'pending';
    const isRejected = status === 'rejected';

    return (
      <div className="tc-container tc-member-container">
        {/* ── Header ── */}
        <div className="tc-header">
          <div>
            <h1 className="tc-title">
              <Users className="tc-header-icon" /> Team Placement & Line Management Status
            </h1>
            <p className="tc-subtitle">
              Enterprise direct team assignment • Max 18 Active Members per PM rule
            </p>
          </div>
          <button className="tc-btn tc-btn-refresh" onClick={fetchMemberData} title="Refresh Status">
            <RefreshCw size={14} /> Refresh
          </button>
        </div>

        {error && <div className="tc-alert tc-alert-error"><AlertTriangle size={18} /> {error}</div>}
        {successMsg && <div className="tc-alert tc-alert-success"><CheckCircle size={18} /> {successMsg}</div>}

        {/* ── Authoritative Status Hero Banner ── */}
        <div className={`tc-status-hero glass-panel status-${status}`}>
          <div className="tc-status-hero-top">
            <div className="tc-status-pill-wrap">
              {hasActive && (
                <span className="tc-status-badge active">
                  <CheckCircle size={16} /> Approved / Active Team Member
                </span>
              )}
              {isPending && (
                <span className="tc-status-badge pending">
                  <Clock size={16} /> Pending PM Review
                </span>
              )}
              {isRejected && (
                <span className="tc-status-badge rejected">
                  <XCircle size={16} /> Request Not Approved
                </span>
              )}
              {status === 'none' && (
                <span className="tc-status-badge none">
                  <Info size={16} /> No Active PM Assignment
                </span>
              )}
            </div>
            <div className="tc-hero-date">
              {hasActive && <span>Assigned: <strong>{formatDate(memberStatus?.assigned_at || memberStatus?.reviewed_at)}</strong></span>}
              {isPending && <span>Requested: <strong>{formatDate(memberStatus?.requested_at)}</strong></span>}
              {isRejected && <span>Decision: <strong>{formatDate(memberStatus?.reviewed_at)}</strong></span>}
            </div>
          </div>

          <div className="tc-hero-content">
            <div className="tc-pm-info-box">
              <div className="tc-pm-avatar">
                {memberStatus?.pm_name ? memberStatus.pm_name.charAt(0) : 'P'}
              </div>
              <div>
                <span className="tc-label-small">
                  {hasActive ? 'Direct Line Manager (PM)' : isPending ? 'Requested Project Manager' : isRejected ? 'Previous Requested PM' : 'Project Manager'}
                </span>
                <h2 className="tc-pm-name">{memberStatus?.pm_name || 'Not Assigned'}</h2>
                {memberStatus?.pm_specialization && (
                  <span className="tc-pm-spec">{memberStatus.pm_specialization}</span>
                )}
                {memberStatus?.pm_email && (
                  <div className="tc-pm-email"><Mail size={13} /> {memberStatus.pm_email}</div>
                )}
              </div>
            </div>

            <div className="tc-hero-message-box">
              <p className="tc-hero-message">{memberStatus?.message}</p>
              {hasActive && (
                <div className="tc-active-notice">
                  <Check size={14} /> Direct team capacity is active (18-member boundary verified).
                </div>
              )}
              {isRejected && memberStatus?.rejection_reason && (
                <div className="tc-rejection-reason-callout">
                  <strong>Reason:</strong> {memberStatus.rejection_reason}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Employee Profile & Capacity Info ── */}
        <div className="tc-grid">
          <div className="tc-card glass-panel">
            <div className="tc-card-header">
              <h3><Briefcase size={18} /> Your Employee Profile</h3>
            </div>
            <div className="tc-card-body">
              <div className="tc-profile-stat-row">
                <span className="tc-stat-label">Full Name:</span>
                <strong>{memberStatus?.employee_name || user?.name}</strong>
              </div>
              <div className="tc-profile-stat-row">
                <span className="tc-stat-label">Functional Role:</span>
                <span className="tc-role-pill">{memberStatus?.employee_role || 'Specialist'}</span>
              </div>
              {memberStatus?.employee_specialization && (
                <div className="tc-profile-stat-row">
                  <span className="tc-stat-label">Specialization:</span>
                  <span>{memberStatus.employee_specialization}</span>
                </div>
              )}
              <div className="tc-profile-stat-row">
                <span className="tc-stat-label">Weekly Bandwidth:</span>
                <span>{memberStatus?.employee_weekly_capacity_hours || 40} hours / week</span>
              </div>
              <div className="tc-profile-stat-row" style={{ alignItems: 'flex-start', marginTop: '6px' }}>
                <span className="tc-stat-label">Skills:</span>
                <div className="tc-skills-tags">
                  {memberStatus?.employee_skills?.map((s) => (
                    <span key={s} className="tc-skill-pill">{s}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* New Request Submission Card (Available if rejected or none) */}
          <div className="tc-card glass-panel">
            <div className="tc-card-header">
              <h3><Send size={18} /> {isRejected ? 'Submit Request to Another PM' : hasActive ? 'Line Management Placement' : 'Request PM Association'}</h3>
            </div>
            <div className="tc-card-body">
              {hasActive ? (
                <div className="tc-confirmed-box">
                  <CheckCircle size={24} className="tc-success-icon" />
                  <div>
                    <strong>You are actively placed!</strong>
                    <p>
                      Your direct line management is linked to {memberStatus?.pm_name}. Any project or task allocations will be coordinated through your Project Manager.
                    </p>
                  </div>
                </div>
              ) : (
                <div>
                  <p className="tc-form-intro">
                    {isRejected
                      ? 'Your previous request was rejected. You can select another active Project Manager with available slots to submit a new request.'
                      : isPending
                        ? 'Your request is currently awaiting review. You can also re-submit to a different PM if needed.'
                        : 'Select an active Project Manager below to join their direct line-management team.'}
                  </p>

                  <div className="tc-request-form-group">
                    <label>Select Project Manager:</label>
                    <select
                      value={newPmSelection}
                      onChange={(e) => setNewPmSelection(e.target.value)}
                      className="tc-select tc-request-select"
                      disabled={requestSubmitting}
                    >
                      <option value="">Choose an active Project Manager...</option>
                      {pmsList.map((pm) => (
                        <option key={pm.pm_user_id} value={pm.pm_user_id} disabled={pm.is_full}>
                          {pm.name} {pm.specialization ? `(${pm.specialization})` : ''} — {pm.active_members_count}/18 slots {pm.is_full ? '(FULL)' : `(${pm.available_capacity} available)`}
                        </option>
                      ))}
                    </select>
                  </div>

                  <button
                    className="tc-btn tc-btn-submit-req"
                    onClick={handleSubmitNewRequest}
                    disabled={!newPmSelection || requestSubmitting}
                  >
                    <Send size={14} />
                    {requestSubmitting ? 'Submitting Request…' : 'Submit Placement Request'}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── Request History Timeline ── */}
        {memberStatus?.all_requests && memberStatus.all_requests.length > 0 && (
          <div className="tc-section">
            <div className="tc-section-header">
              <h2><Calendar size={20} /> Request & Decision History</h2>
              <p>Authoritative log of all team placement requests</p>
            </div>

            <div className="tc-table-container">
              <table className="tc-table">
                <thead>
                  <tr>
                    <th>Project Manager</th>
                    <th>Status</th>
                    <th>Requested Date</th>
                    <th>Reviewed / Decision Date</th>
                    <th>Decision Notes / Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {memberStatus.all_requests.map((req) => (
                    <tr key={req.id || req._id}>
                      <td>
                        <strong>{req.pm_name || 'Project Manager'}</strong>
                        {req.pm_specialization && <span className="tc-spec-text"> • {req.pm_specialization}</span>}
                      </td>
                      <td>
                        <span className={`tc-status-pill ${req.status}`}>
                          {req.status === 'active' ? '✓ Approved' : req.status === 'pending' ? '● Pending' : '✕ Rejected'}
                        </span>
                      </td>
                      <td>{formatDate(req.requested_at)}</td>
                      <td>{formatDate(req.reviewed_at || req.assigned_at)}</td>
                      <td>
                        {req.rejection_reason ? (
                          <span className="text-error">{req.rejection_reason}</span>
                        ) : req.status === 'active' ? (
                          <span className="text-success">Approved by {req.pm_name || 'PM'}</span>
                        ) : (
                          <span className="text-muted">Awaiting decision</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ══════════════════════════════════════════════════════════════════════════
  // PROJECT MANAGER / ADMIN VIEW (Full Capacity & Intelligence Dashboard)
  // ══════════════════════════════════════════════════════════════════════════
  const activeCount = capacityData?.active_members_count || 0;
  const maxCap = capacityData?.max_capacity || 18;
  const availCap = capacityData?.available_capacity || 0;
  const isFull = capacityData?.is_full || false;
  const fillPct = Math.min(100, Math.round((activeCount / maxCap) * 100));

  return (
    <div className="tc-container">
      {/* ── Header ── */}
      <div className="tc-header">
        <div>
          <h1 className="tc-title">
            <Users className="tc-header-icon" /> Team Capacity & Onboarding Intelligence
          </h1>
          <p className="tc-subtitle">
            Enterprise Line Management (Max 18 Active Members) • <span className="tc-principle">OBSERVE → ANALYZE → RECOMMEND → DECIDE</span>
          </p>
        </div>

        {isAdmin && pmsList.length > 0 && (
          <div className="tc-admin-select-wrapper">
            <label>Viewing PM:</label>
            <select
              value={selectedPmId}
              onChange={(e) => setSelectedPmId(e.target.value)}
              className="tc-select"
            >
              <option value="">My Scope ({user?.name})</option>
              {pmsList.map((pm) => (
                <option key={pm.pm_user_id} value={pm.pm_user_id}>
                  {pm.name} ({pm.active_members_count}/18)
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {error && <div className="tc-alert tc-alert-error"><AlertTriangle size={18} /> {error}</div>}
      {successMsg && <div className="tc-alert tc-alert-success"><CheckCircle size={18} /> {successMsg}</div>}

      {/* ── Main Capacity Banner ── */}
      <div className={`tc-capacity-banner ${isFull ? 'is-full' : fillPct >= 85 ? 'is-warning' : ''}`}>
        <div className="tc-banner-main">
          <div className="tc-stat-group">
            <span className="tc-stat-label">Active Managed Team Members</span>
            <div className="tc-stat-value">
              {activeCount} <span className="tc-stat-max">/ {maxCap}</span>
            </div>
          </div>

          <div className="tc-progress-section">
            <div className="tc-progress-header">
              <span>Team Capacity Utilization</span>
              <span className="tc-progress-pct">{fillPct}%</span>
            </div>
            <div className="tc-progress-bar-bg">
              <div
                className="tc-progress-bar-fill"
                style={{ width: `${fillPct}%` }}
              />
            </div>
          </div>

          <div className="tc-stat-group tc-stat-avail">
            <span className="tc-stat-label">Available PM Slots</span>
            <div className="tc-stat-value tc-avail-value">
              {availCap} <span className="tc-stat-unit">slots</span>
            </div>
          </div>
        </div>

        {isFull && (
          <div className="tc-full-warning">
            <AlertTriangle size={18} />
            <span>
              <strong>PM Capacity Full (18/18):</strong> Direct assignment of 19th member is locked server-side.
              NexusAI will generate intelligent alternative PM placement recommendations for candidate review.
            </span>
          </div>
        )}
      </div>

      {/* ── Grid Layout: Role Composition & Capability Gaps ── */}
      <div className="tc-grid">
        {/* Role Breakdown Card */}
        <div className="tc-card">
          <div className="tc-card-header">
            <h3><Layers size={18} /> Functional Role Distribution</h3>
          </div>
          <div className="tc-card-body">
            {capacityData?.role_breakdown && Object.keys(capacityData.role_breakdown).length > 0 ? (
              <div className="tc-role-list">
                {Object.entries(capacityData.role_breakdown).map(([rName, cnt]) => (
                  <div key={rName} className="tc-role-item">
                    <span className="tc-role-name">{rName}</span>
                    <span className="tc-role-badge">{cnt as number}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="tc-empty-text">No active team members assigned yet.</p>
            )}
          </div>
        </div>

        {/* Capability Gaps Card */}
        <div className="tc-card">
          <div className="tc-card-header">
            <h3><Shield size={18} /> Skill Coverage & Capability Gaps</h3>
          </div>
          <div className="tc-card-body">
            {capacityData?.capability_gaps && capacityData.capability_gaps.length > 0 ? (
              <div className="tc-gap-list">
                {capacityData.capability_gaps.map((gap: CapabilityGap, idx: number) => (
                  <div key={idx} className="tc-gap-item">
                    <div className="tc-gap-top">
                      <span className="tc-gap-name">{gap.name}</span>
                      <span className="tc-gap-badge">{gap.status}</span>
                    </div>
                    <p className="tc-gap-desc">{gap.description}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="tc-empty-text">No immediate capability gaps detected for current active projects.</p>
            )}
          </div>
        </div>
      </div>

      {/* ── Pending Candidate Member Requests Section ── */}
      <div className="tc-section">
        <div className="tc-section-header">
          <h2><UserCheck size={20} /> Pending Candidate Onboarding Requests ({pendingRequests.length})</h2>
          <p>Newly registered Team Members requesting line management association</p>
        </div>

        {pendingRequests.length === 0 ? (
          <div className="tc-empty-card">
            <CheckCircle size={32} className="tc-empty-icon" />
            <p>No pending onboarding requests awaiting decision.</p>
          </div>
        ) : (
          <div className="tc-table-container">
            <table className="tc-table">
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Role & Specialization</th>
                  <th>Skills</th>
                  <th>Requested PM</th>
                  <th>Request Date</th>
                  <th>Actions & Intelligence</th>
                </tr>
              </thead>
              <tbody>
                {pendingRequests.map((req) => (
                  <tr key={req.id}>
                    <td>
                      <div className="tc-user-cell">
                        <div className="tc-avatar">{req.candidate_name?.charAt(0) || 'C'}</div>
                        <div>
                          <div className="tc-user-name">{req.candidate_name}</div>
                          <div className="tc-user-email">{req.candidate_email}</div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <div className="tc-role-text">{req.candidate_role}</div>
                      <div className="tc-spec-text">{req.candidate_specialization || 'Engineering'}</div>
                    </td>
                    <td>
                      <div className="tc-skills-tags">
                        {req.candidate_skills?.map((sk) => (
                          <span key={sk} className="tc-skill-pill">{sk}</span>
                        ))}
                      </div>
                    </td>
                    <td>{req.pm_name || 'PM'}</td>
                    <td>{formatDate(req.requested_at)}</td>
                    <td>
                      <div className="tc-actions-cell">
                        {isManager && (
                          <>
                            <button
                              onClick={() => handleApprove(req.id)}
                              disabled={actionLoading || isFull}
                              className="tc-btn tc-btn-approve"
                              title={isFull ? 'PM capacity is full (18/18)' : 'Approve candidate'}
                            >
                              <UserCheck size={14} /> Approve
                            </button>
                            <button
                              onClick={() => handleReject(req.id)}
                              disabled={actionLoading}
                              className="tc-btn tc-btn-reject"
                              title="Reject request"
                            >
                              <UserX size={14} /> Reject
                            </button>
                          </>
                        )}
                        <button
                          onClick={() => handleAnalyzeCandidate(req)}
                          className="tc-btn tc-btn-ai"
                          title="Evaluate PM matches"
                        >
                          <Sparkles size={14} /> Analyze Matches
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Active Managed Team Members Roster ── */}
      <div className="tc-section">
        <div className="tc-section-header">
          <h2><Briefcase size={20} /> Managed Active Team Members ({activeCount} / {maxCap})</h2>
        </div>

        {capacityData?.active_members && capacityData.active_members.length > 0 ? (
          <div className="tc-table-container">
            <table className="tc-table">
              <thead>
                <tr>
                  <th>Member Name</th>
                  <th>Functional Role</th>
                  <th>Skills</th>
                  <th>Assigned Date</th>
                </tr>
              </thead>
              <tbody>
                {capacityData.active_members.map((mem: any, idx: number) => (
                  <tr key={mem.employee_id || idx}>
                    <td>
                      <div className="tc-user-cell">
                        <div className="tc-avatar tc-avatar-active">{mem.name?.charAt(0) || 'M'}</div>
                        <div className="tc-user-name">{mem.name}</div>
                      </div>
                    </td>
                    <td><span className="tc-role-pill">{mem.role}</span></td>
                    <td>
                      <div className="tc-skills-tags">
                        {mem.skills?.map((s: string) => (
                          <span key={s} className="tc-skill-pill tc-skill-active">{s}</span>
                        ))}
                      </div>
                    </td>
                    <td>{formatDate(mem.assigned_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="tc-empty-card">
            <p>No active line-managed team members currently assigned.</p>
          </div>
        )}
      </div>

      {/* ── Intelligent Recommendation Modal ── */}
      {analyzingCandidate && (
        <div className="tc-modal-overlay">
          <div className="tc-modal">
            <div className="tc-modal-header">
              <div>
                <h3><Sparkles size={20} className="tc-ai-icon" /> Intelligent PM Allocation Recommendation</h3>
                <p>NexusAI multi-criteria candidate suitability analysis</p>
              </div>
              <button className="tc-close-btn" onClick={() => setAnalyzingCandidate(null)}>
                <XCircle size={20} />
              </button>
            </div>

            <div className="tc-modal-body">
              {recommendLoading ? (
                <div className="tc-loading">
                  <Sparkles className="animate-spin" size={24} />
                  <p>Evaluating PM capacities, role demands, and team skill gaps…</p>
                </div>
              ) : recommendationData ? (
                <div>
                  <div className="tc-cand-summary">
                    <h4>Candidate Profile</h4>
                    <p>
                      <strong>{recommendationData.candidate.name}</strong> • Role: <em>{recommendationData.candidate.role}</em> • Skills: {recommendationData.candidate.skills?.join(', ')}
                    </p>
                  </div>

                  <h4 className="tc-rec-heading">Recommended PM Placement Options</h4>
                  <div className="tc-rec-list">
                    {recommendationData.recommendations?.map((rec: PMRecommendation) => (
                      <div key={rec.pm_user_id} className={`tc-rec-card ${rec.is_full ? 'rec-full' : ''}`}>
                        <div className="tc-rec-card-header">
                          <div>
                            <span className="tc-rec-pm-name">{rec.pm_name}</span>
                            <span className="tc-rec-pm-spec">{rec.pm_specialization || 'Project Manager'}</span>
                          </div>
                          <div className="tc-rec-badges">
                            <span className={`tc-score-badge score-${rec.relevance_level.toLowerCase()}`}>
                              Relevance: {rec.relevance_level}
                            </span>
                            <span className={`tc-cap-badge ${rec.is_full ? 'full' : 'avail'}`}>
                              {rec.active_members_count}/18 ({rec.is_full ? 'FULL' : `${rec.available_capacity} available`})
                            </span>
                          </div>
                        </div>

                        <div className="tc-rec-reasons">
                          {rec.reasons.map((r, i) => (
                            <div key={i} className="tc-reason-item">{r}</div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="tc-modal-footer-note">
                    <Info size={16} />
                    <span>
                      <strong>Principles:</strong> NexusAI provides decision intelligence recommendations. The final assignment decision remains with the authorized Project Manager or Administrator.
                    </span>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TeamCapacity;
