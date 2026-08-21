import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Activity } from 'lucide-react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
import './Login.css';

const Signup: React.FC = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('project_manager');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const response = await api.post('/auth/signup', {
        name,
        email,
        password,
        role
      });

      await login(response.data.access_token);
      navigate('/dashboard');
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || 'Failed to register account');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container signup-container">
      <div className="login-glass-panel">
        <div className="login-header">
          <div className="logo-container">
            <Activity className="logo-icon" size={32} />
            <h1>Join NexusAI</h1>
          </div>
          <p>Create your enterprise workspace account</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {error && <div className="error-message">{error}</div>}
          
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

          <button type="submit" disabled={isLoading} className="login-button">
            {isLoading ? 'Creating Account...' : 'Create Account'}
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
