import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Activity, Plus, X } from 'lucide-react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
import './Login.css';
import './Signup.css';

// ─── Predefined Options ────────────────────────────────────────────────────
const JOB_ROLE_OPTIONS = [
  'Backend Engineer',
  'Frontend Engineer',
  'Full Stack Engineer',
  'ML Engineer',
  'AI Engineer',
  'Data Engineer',
  'Data Scientist',
  'DevOps Engineer',
  'QA Engineer',
  'Cybersecurity Engineer',
  'UI/UX Designer',
  'Mobile Developer',
  'Other / Custom',
];

const SPECIALIZATION_OPTIONS = [
  'Backend Development',
  'Frontend Development',
  'Full Stack Development',
  'Machine Learning',
  'Artificial Intelligence',
  'Data Science',
  'Data Engineering',
  'DevOps / Cloud',
  'Cybersecurity',
  'Quality Assurance',
  'UI/UX',
  'Mobile Development',
  'Other / Custom',
];

const SKILL_OPTIONS = [
  'JavaScript', 'TypeScript', 'Python', 'Java', 'Go', 'Rust', 'C++', 'C#',
  'React', 'Vue', 'Angular', 'Next.js', 'Node.js', 'FastAPI', 'Django', 'Spring Boot',
  'PostgreSQL', 'MongoDB', 'Redis', 'Elasticsearch',
  'Docker', 'Kubernetes', 'AWS', 'GCP', 'Azure', 'Terraform', 'CI/CD',
  'Machine Learning', 'Deep Learning', 'NLP', 'Computer Vision', 'PyTorch', 'TensorFlow',
  'Data Analysis', 'SQL', 'Spark', 'Kafka',
  'Security Auditing', 'Penetration Testing', 'SIEM', 'Threat Modelling',
  'Figma', 'UI Design', 'UX Research', 'Prototyping',
  'React Native', 'Flutter', 'iOS', 'Android',
  'Unit Testing', 'Integration Testing', 'Selenium', 'Jest',
  'Other / Custom',
];

// ─── Component ─────────────────────────────────────────────────────────────
const Signup: React.FC = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('project_manager');

  // Team-member extra fields
  const [jobRole, setJobRole] = useState('');
  const [customJobRole, setCustomJobRole] = useState('');
  const [specialization, setSpecialization] = useState('');
  const [customSpecialization, setCustomSpecialization] = useState('');
  const [skills, setSkills] = useState<string[]>([]);
  const [skillSelect, setSkillSelect] = useState('');
  const [customSkill, setCustomSkill] = useState('');
  const [weeklyCapacity, setWeeklyCapacity] = useState<number>(40);
  const [preferredPmId, setPreferredPmId] = useState('');
  const [pmsList, setPmsList] = useState<any[]>([]);
  const [loadingPms, setLoadingPms] = useState(false);
  const [pmsError, setPmsError] = useState('');

  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const isTeamMember = role === 'team_member';

  // Fetch available PMs when team_member role is selected
  React.useEffect(() => {
    if (isTeamMember) {
      setLoadingPms(true);
      setPmsError('');
      api.get('/team-capacity/pms')
        .then(res => {
          if (Array.isArray(res.data)) {
            setPmsList(res.data);
          }
        })
        .catch(err => {
          console.error('Failed to load project managers', err);
          setPmsError('Unable to load active Project Managers');
        })
        .finally(() => {
          setLoadingPms(false);
        });
    }
  }, [isTeamMember]);

  // Resolve "Other/Custom" values to the custom text entry
  const resolvedJobRole = jobRole === 'Other / Custom' ? customJobRole.trim() : jobRole;
  const resolvedSpecialization = specialization === 'Other / Custom' ? customSpecialization.trim() : specialization;

  const addSkill = () => {
    const raw = skillSelect === 'Other / Custom' ? customSkill.trim() : skillSelect.trim();
    if (!raw) return;
    if (!skills.includes(raw)) {
      setSkills(prev => [...prev, raw]);
    }
    setSkillSelect('');
    setCustomSkill('');
  };

  const removeSkill = (skill: string) => {
    setSkills(prev => prev.filter(s => s !== skill));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const cleanName = name.trim();
    const cleanEmail = email.trim().toLowerCase();

    if (!cleanName) {
      setError('Please enter your full name.');
      return;
    }
    if (!cleanEmail) {
      setError('Please enter your work email.');
      return;
    }

    // Auto-include pending skill if selected/typed but "+ Add" was not clicked
    let finalSkills = [...skills];
    const pendingSkill = skillSelect === 'Other / Custom' ? customSkill.trim() : skillSelect.trim();
    if (pendingSkill && !finalSkills.includes(pendingSkill)) {
      finalSkills.push(pendingSkill);
    }

    // Client-side validation for team members
    if (isTeamMember) {
      if (!resolvedJobRole) {
        setError('Please select or enter a Job Role.');
        return;
      }
      if (!resolvedSpecialization) {
        setError('Please select or enter a Specialization.');
        return;
      }
      if (finalSkills.length === 0) {
        setError('Please add at least one skill.');
        return;
      }
      const capNum = Number(weeklyCapacity);
      if (isNaN(capNum) || capNum <= 0 || capNum > 168) {
        setError('Weekly capacity must be between 1 and 168 hours.');
        return;
      }
    }

    setIsLoading(true);
    try {
      const payload: any = {
        name: cleanName,
        email: cleanEmail,
        password,
        role,
      };

      if (isTeamMember) {
        payload.job_role = resolvedJobRole;
        payload.specialization = resolvedSpecialization;
        payload.skills = finalSkills;
        payload.weekly_capacity_hours = Number(weeklyCapacity) > 0 ? Number(weeklyCapacity) : 40.0;
        if (preferredPmId && preferredPmId.trim() && preferredPmId !== 'none') {
          payload.preferred_pm_id = preferredPmId.trim();
        }
      }

      const response = await api.post('/auth/signup', payload);
      await login(response.data.access_token);
      navigate('/dashboard');
    } catch (err: any) {
      console.error('Signup error:', err);
      const detail = err.response?.data?.detail;
      let errorMsg = 'Failed to register account';

      if (typeof detail === 'string') {
        errorMsg = detail;
      } else if (Array.isArray(detail)) {
        errorMsg = detail
          .map((d: any) => {
            const loc = Array.isArray(d.loc) ? d.loc.filter((l: any) => l !== 'body').join('.') : '';
            return loc ? `${loc}: ${d.msg}` : (d.msg || JSON.stringify(d));
          })
          .join('; ');
      } else if (detail && typeof detail === 'object') {
        errorMsg = JSON.stringify(detail);
      }

      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container signup-container">
      <div className={`login-glass-panel ${isTeamMember ? 'signup-wide' : ''}`}>
        <div className="login-header">
          <div className="logo-container">
            <Activity className="logo-icon" size={32} />
            <h1>Join NexusAI</h1>
          </div>
          <p>Create your enterprise workspace account</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {error && <div className="error-message">{error}</div>}

          {/* ── Common Fields ── */}
          <div className="form-group">
            <label htmlFor="name">Full Name</label>
            <input
              type="text"
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Alex Chen"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="email">Work Email</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="alex@nexusai.dev"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              minLength={6}
            />
          </div>

          <div className="form-group">
            <label htmlFor="role">Role</label>
            <select
              id="role"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              required
              className="role-select"
            >
              <option value="project_manager">Project Manager</option>
              <option value="team_member">Team Member</option>
              <option value="admin">Administrator</option>
            </select>
          </div>

          {/* ── Team Member Extra Fields ── */}
          {isTeamMember && (
            <div className="team-member-section">
              <div className="tm-section-title">
                <span className="tm-section-label">Employee Profile</span>
                <span className="tm-section-line" />
              </div>

              {/* Job Role */}
              <div className="form-group">
                <label htmlFor="jobRole">Job Role</label>
                <select
                  id="jobRole"
                  value={jobRole}
                  onChange={(e) => setJobRole(e.target.value)}
                  required={isTeamMember}
                  className="role-select"
                >
                  <option value="">Select a job role…</option>
                  {JOB_ROLE_OPTIONS.map(opt => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
              </div>
              {jobRole === 'Other / Custom' && (
                <div className="form-group">
                  <label htmlFor="customJobRole">Custom Job Role</label>
                  <input
                    type="text"
                    id="customJobRole"
                    value={customJobRole}
                    onChange={(e) => setCustomJobRole(e.target.value)}
                    placeholder="Enter your job role"
                    required
                  />
                </div>
              )}

              {/* Specialization */}
              <div className="form-group">
                <label htmlFor="specialization">Specialization</label>
                <select
                  id="specialization"
                  value={specialization}
                  onChange={(e) => setSpecialization(e.target.value)}
                  required={isTeamMember}
                  className="role-select"
                >
                  <option value="">Select a specialization…</option>
                  {SPECIALIZATION_OPTIONS.map(opt => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
              </div>
              {specialization === 'Other / Custom' && (
                <div className="form-group">
                  <label htmlFor="customSpecialization">Custom Specialization</label>
                  <input
                    type="text"
                    id="customSpecialization"
                    value={customSpecialization}
                    onChange={(e) => setCustomSpecialization(e.target.value)}
                    placeholder="Enter your specialization"
                    required
                  />
                </div>
              )}

              {/* Skills */}
              <div className="form-group">
                <label>Skills</label>
                <div className="skill-selector-row">
                  <select
                    id="skillSelect"
                    value={skillSelect}
                    onChange={(e) => setSkillSelect(e.target.value)}
                    className="role-select skill-dropdown"
                  >
                    <option value="">Select a skill…</option>
                    {SKILL_OPTIONS.filter(s => !skills.includes(s) || s === 'Other / Custom').map(opt => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="skill-add-btn"
                    onClick={addSkill}
                    disabled={!skillSelect}
                    title="Add skill"
                  >
                    <Plus size={16} />
                    Add
                  </button>
                </div>
                {skillSelect === 'Other / Custom' && (
                  <input
                    type="text"
                    id="customSkill"
                    value={customSkill}
                    onChange={(e) => setCustomSkill(e.target.value)}
                    placeholder="Enter custom skill"
                    className="custom-skill-input"
                  />
                )}
                {skills.length > 0 && (
                  <div className="selected-skills">
                    {skills.map(skill => (
                      <span key={skill} className="skill-tag">
                        {skill}
                        <button
                          type="button"
                          className="skill-remove-btn"
                          onClick={() => removeSkill(skill)}
                          title={`Remove ${skill}`}
                        >
                          <X size={12} />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
                {skills.length === 0 && (
                  <p className="skills-hint">Add at least one skill to continue.</p>
                )}
              </div>

              {/* Weekly Capacity */}
              <div className="form-group">
                <label htmlFor="weeklyCapacity">Weekly Capacity (hours)</label>
                <input
                  type="number"
                  id="weeklyCapacity"
                  value={weeklyCapacity}
                  onChange={(e) => setWeeklyCapacity(Number(e.target.value))}
                  min={1}
                  max={168}
                  required={isTeamMember}
                />
              </div>

              {/* Preferred Project Manager */}
              <div className="form-group">
                <label htmlFor="preferredPm">Preferred Project Manager (Optional)</label>
                <select
                  id="preferredPm"
                  value={preferredPmId}
                  onChange={(e) => setPreferredPmId(e.target.value)}
                  className="role-select pm-dropdown-select"
                  disabled={loadingPms}
                >
                  <option value="">
                    {loadingPms
                      ? 'Loading Project Managers...'
                      : pmsList.length === 0
                        ? 'No active Project Managers available'
                        : 'Select a preferred Project Manager (Optional)...'}
                  </option>
                  {pmsList.map(pm => (
                    <option key={pm.pm_user_id} value={pm.pm_user_id}>
                      {pm.name} {pm.specialization ? `(${pm.specialization})` : ''} — {pm.active_members_count}/{pm.max_capacity || 18} slots {pm.is_full ? '(FULL)' : `(${pm.available_capacity} available)`}
                    </option>
                  ))}
                </select>
                {pmsError && (
                  <p className="skills-hint" style={{ color: 'var(--error)', marginTop: '4px' }}>
                    {pmsError}
                  </p>
                )}
                <p className="skills-hint" style={{ marginTop: '4px' }}>
                  Your preferred PM will receive an association request to review and approve your active team placement.
                </p>
              </div>
            </div>
          )}

          <button type="submit" disabled={isLoading} className="login-button">
            {isLoading ? 'Creating Account…' : 'Create Account'}
          </button>
        </form>

        <div className="login-footer">
          <p>Already have an account? <Link to="/login" className="text-primary">Sign in here</Link></p>
        </div>
      </div>
    </div>
  );
};

export default Signup;
