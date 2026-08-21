import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Activity } from 'lucide-react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
import './Login.css';

const Login: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const response = await api.post('/auth/login', {
        email: email,
        password: password,
      });

      await login(response.data.access_token);
      navigate('/dashboard');
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || 'Invalid email or password');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-glass-panel">
        <div className="login-header">
          <div className="logo-container">
            <Activity className="logo-icon" size={32} />
            <h1>NexusAI</h1>
          </div>
          <p>Enterprise Project Decision Intelligence System</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {error && <div className="error-message">{error}</div>}
          
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@nexusai.dev"
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

          <button type="submit" disabled={isLoading} className="login-button">
            {isLoading ? 'Authenticating...' : 'Sign In'}
          </button>
        </form>

        <div className="login-footer">
          <p>Don't have an account? <Link to="/signup" className="text-primary" style={{ color: '#818cf8', textDecoration: 'none', fontWeight: 600 }}>Create one here →</Link></p>
        </div>
      </div>
    </div>
  );
};

export default Login;
