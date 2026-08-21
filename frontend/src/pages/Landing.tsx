import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity, ShieldCheck, Zap, BrainCircuit, ArrowRight, BarChart3, Users,
  TrendingUp, FileText, AlertTriangle, CheckCircle2, ChevronDown
} from 'lucide-react';
import './Landing.css';

/* ── Animated counter hook ───────────────────────────── */
function useCounter(target: number, duration = 2000, start = false) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (!start) return;
    let startTime: number | null = null;
    const step = (ts: number) => {
      if (!startTime) startTime = ts;
      const progress = Math.min((ts - startTime) / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      setCount(Math.floor(ease * target));
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [target, duration, start]);
  return count;
}

/* ── Particle canvas ─────────────────────────────────── */
const ParticleCanvas: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    const particles: { x: number; y: number; r: number; dx: number; dy: number; alpha: number }[] = [];
    for (let i = 0; i < 80; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        r: Math.random() * 1.5 + 0.3,
        dx: (Math.random() - 0.5) * 0.3,
        dy: (Math.random() - 0.5) * 0.3,
        alpha: Math.random() * 0.5 + 0.1,
      });
    }

    let raf: number;
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach(p => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(129,140,248,${p.alpha})`;
        ctx.fill();
        p.x += p.dx;
        p.y += p.dy;
        if (p.x < 0 || p.x > canvas.width) p.dx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.dy *= -1;
      });
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', resize);
    };
  }, []);
  return <canvas ref={canvasRef} className="particle-canvas" />;
};

/* ── Landing Page ────────────────────────────────────── */
const Landing: React.FC = () => {
  const [statsVisible, setStatsVisible] = useState(false);
  const statsRef = useRef<HTMLDivElement>(null);
  const [navScrolled, setNavScrolled] = useState(false);

  const projects = useCounter(240, 2200, statsVisible);
  const teams = useCounter(1800, 2400, statsVisible);
  const accuracy = useCounter(94, 2000, statsVisible);
  const saved = useCounter(12, 2600, statsVisible);

  useEffect(() => {
    // Nav scroll class
    const onScroll = () => setNavScrolled(window.scrollY > 60);
    window.addEventListener('scroll', onScroll, { passive: true });

    // IntersectionObserver for scroll animations
    const observer = new IntersectionObserver(
      (entries) => entries.forEach(e => {
        if (e.isIntersecting) {
          e.target.classList.add('show');
          if (e.target === statsRef.current) setStatsVisible(true);
        }
      }),
      { threshold: 0.15 }
    );
    document.querySelectorAll('.anim').forEach(el => observer.observe(el));
    if (statsRef.current) observer.observe(statsRef.current);

    return () => {
      window.removeEventListener('scroll', onScroll);
      observer.disconnect();
    };
  }, []);

  const features = [
    {
      icon: <BrainCircuit size={28} />,
      color: '#818cf8',
      bg: 'rgba(99,102,241,0.08)',
      border: 'rgba(99,102,241,0.2)',
      title: 'Predictive Risk Engine',
      desc: 'ML models trained on 10k+ projects predict delays, budget overruns, and team failures weeks before they happen.',
      tag: 'AI / ML'
    },
    {
      icon: <FileText size={28} />,
      color: '#34d399',
      bg: 'rgba(16,185,129,0.08)',
      border: 'rgba(16,185,129,0.2)',
      title: 'Document Intelligence',
      desc: 'Upload requirement PDFs. NLP automatically extracts ambiguities, security gaps, and missing acceptance criteria.',
      tag: 'NLP'
    },
    {
      icon: <Users size={28} />,
      color: '#fbbf24',
      bg: 'rgba(245,158,11,0.08)',
      border: 'rgba(245,158,11,0.2)',
      title: 'Burnout Detection',
      desc: 'Real-time workload vs capacity analysis flags burnout risk before morale tanks. Protect your best engineers.',
      tag: 'People Analytics'
    },
    {
      icon: <BarChart3 size={28} />,
      color: '#f472b6',
      bg: 'rgba(236,72,153,0.08)',
      border: 'rgba(236,72,153,0.2)',
      title: 'Sprint Velocity Tracking',
      desc: 'Automated story point aggregation per sprint. Identify velocity trends and forecast delivery timelines precisely.',
      tag: 'Agile'
    },
    {
      icon: <AlertTriangle size={28} />,
      color: '#fb923c',
      bg: 'rgba(251,146,60,0.08)',
      border: 'rgba(251,146,60,0.2)',
      title: 'Issue Intelligence',
      desc: 'Categorize, prioritize, and route issues by severity automatically. Critical path issues surface immediately.',
      tag: 'Risk'
    },
    {
      icon: <CheckCircle2 size={28} />,
      color: '#38bdf8',
      bg: 'rgba(56,189,248,0.08)',
      border: 'rgba(56,189,248,0.2)',
      title: 'Resource Optimization',
      desc: 'AI-powered resource allocation recommendations. Balance workload, avoid bottlenecks, maximize delivery.',
      tag: 'Optimization'
    },
  ];

  return (
    <div className="landing-page">
      <ParticleCanvas />

      {/* ── Navigation ─────────────────────────────────── */}
      <nav className={`landing-nav ${navScrolled ? 'nav-scrolled' : ''}`}>
        <div className="logo-container">
          <div className="logo-icon-wrap">
            <Activity className="logo-icon" size={20} />
          </div>
          <span className="logo-text">NexusAI</span>
          <span className="logo-badge">Enterprise</span>
        </div>
        <div className="nav-links-center">
          <a href="#features" className="nav-link">Features</a>
          <a href="#metrics" className="nav-link">Impact</a>
          <a href="#workflow" className="nav-link">Workflow</a>
        </div>
        <div className="nav-actions">
          <Link to="/login" className="nav-link" id="nav-login">Sign In</Link>
          <Link to="/signup" className="nav-cta-btn" id="nav-signup">Get Started <ArrowRight size={14} /></Link>
        </div>
      </nav>

      {/* ── Hero ───────────────────────────────────────── */}
      <header className="hero-section">
        <div className="hero-bg-effects">
          <div className="glow-orb primary-orb" />
          <div className="glow-orb secondary-orb" />
          <div className="glow-orb tertiary-orb" />
          <div className="mesh-grid" />
        </div>

        <div className="hero-content anim">
          <div className="badge-pill">
            <span className="pulse-dot" />
            Enterprise Project Decision Intelligence
          </div>
          <h1 className="hero-title">
            Stop Guessing.<br />
            <span className="gradient-text animated-gradient">Start Predicting.</span>
          </h1>
          <p className="hero-subtitle">
            NexusAI combines machine learning, document AI, and real-time analytics
            to give engineering leaders a <strong>complete intelligence layer</strong> over
            their entire project portfolio.
          </p>
          <div className="hero-cta-group">
            <Link to="/signup" className="primary-button hero-btn glow-btn" id="hero-get-started">
              Start For Free <ArrowRight size={18} />
            </Link>
            <a href="#features" className="ghost-btn hero-btn">
              See Features <ChevronDown size={18} />
            </a>
          </div>
          <div className="hero-trust-bar">
            <span><CheckCircle2 size={14} /> No credit card</span>
            <span><CheckCircle2 size={14} /> Real MongoDB data</span>
            <span><CheckCircle2 size={14} /> JWT secured</span>
          </div>
        </div>

        {/* Mockup */}
        <div className="hero-visual anim delay-2">
          <div className="dashboard-mockup">
            <div className="mockup-header">
              <div className="dots"><span /><span /><span /></div>
              <div className="mockup-url-bar">nexusai.dev/dashboard</div>
            </div>
            <div className="mockup-body">
              <div className="mockup-sidebar">
                <div className="mockup-nav-item active" />
                <div className="mockup-nav-item" />
                <div className="mockup-nav-item" />
                <div className="mockup-nav-item" />
                <div className="mockup-nav-item" />
              </div>
              <div className="mockup-content">
                <div className="mockup-stat-row">
                  {['#6366f1','#10b981','#f59e0b','#ef4444'].map((c,i) => (
                    <div key={i} className="mockup-stat" style={{ borderTop: `2px solid ${c}` }}>
                      <div className="mockup-stat-val" style={{ background: `${c}30` }} />
                      <div className="mockup-stat-lbl" />
                    </div>
                  ))}
                </div>
                <div className="mockup-charts">
                  <div className="mockup-chart-l">
                    <div className="mockup-chart-title" />
                    <div className="mockup-bar-chart">
                      {[60,85,45,90,70,55,80].map((h, i) => (
                        <div key={i} className="mockup-bar" style={{ height: `${h}%`, animationDelay: `${i*0.1}s` }} />
                      ))}
                    </div>
                  </div>
                  <div className="mockup-chart-r">
                    <div className="mockup-chart-title" />
                    <div className="mockup-shimmer-list">
                      {[1,2,3].map(i => <div key={i} className="mockup-shimmer-row" />)}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* ── Metrics Strip ──────────────────────────────── */}
      <div className="metrics-strip anim" id="metrics" ref={statsRef}>
        <div className="metric-item">
          <span className="metric-value gradient-text">{projects}+</span>
          <span className="metric-label">Projects Tracked</span>
        </div>
        <div className="metric-divider" />
        <div className="metric-item">
          <span className="metric-value gradient-text">{teams}+</span>
          <span className="metric-label">Team Members Monitored</span>
        </div>
        <div className="metric-divider" />
        <div className="metric-item">
          <span className="metric-value gradient-text">{accuracy}%</span>
          <span className="metric-label">Prediction Accuracy</span>
        </div>
        <div className="metric-divider" />
        <div className="metric-item">
          <span className="metric-value gradient-text">${saved}M</span>
          <span className="metric-label">Budget Risk Prevented</span>
        </div>
      </div>

      {/* ── Features ───────────────────────────────────── */}
      <section id="features" className="features-section">
        <div className="section-header anim">
          <div className="section-eyebrow">Platform Features</div>
          <h2>Intelligence at <span className="gradient-text">Every Level</span></h2>
          <p>From document upload to ML predictions — complete visibility into your engineering organization.</p>
        </div>

        <div className="features-grid">
          {features.map((f, i) => (
            <div
              key={i}
              className={`feature-card anim delay-${i % 3}`}
              style={{ '--card-color': f.color, '--card-bg': f.bg, '--card-border': f.border } as React.CSSProperties}
            >
              <div className="feature-tag">{f.tag}</div>
              <div className="feature-icon">{f.icon}</div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
              <div className="feature-hover-line" />
            </div>
          ))}
        </div>
      </section>

      {/* ── Workflow ───────────────────────────────────── */}
      <section id="workflow" className="workflow-section">
        <div className="section-header anim">
          <div className="section-eyebrow">How It Works</div>
          <h2>From Data to <span className="gradient-text">Decisions</span></h2>
        </div>
        <div className="workflow-steps">
          {[
            { num: '01', title: 'Connect Your Data', desc: 'Projects, sprints, tasks, and team data flow into MongoDB in real-time via REST API.' },
            { num: '02', title: 'AI Processes Everything', desc: 'ML models run risk classification, burnout detection, and document analysis automatically.' },
            { num: '03', title: 'Actionable Intelligence', desc: 'Dashboard surfaces predictions, anomalies, and recommendations for immediate action.' },
          ].map((step, i) => (
            <div key={i} className={`workflow-step anim delay-${i}`}>
              <div className="step-number">{step.num}</div>
              <div className="step-content">
                <h3>{step.title}</h3>
                <p>{step.desc}</p>
              </div>
              {i < 2 && <div className="step-connector" />}
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA ────────────────────────────────────────── */}
      <section className="cta-section anim">
        <div className="cta-glass">
          <div className="cta-orb" />
          <div className="section-eyebrow">Ready to Transform?</div>
          <h2>Start Making Better<br /><span className="gradient-text">Project Decisions Today</span></h2>
          <p>Join engineering teams using NexusAI to predict risk before it becomes reality.</p>
          <div className="hero-cta-group">
            <Link to="/signup" className="primary-button hero-btn glow-btn" id="cta-signup">
              Create Your Account <ArrowRight size={18} />
            </Link>
            <Link to="/login" className="ghost-btn hero-btn" id="cta-login">
              Sign In
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────── */}
      <footer className="landing-footer">
        <div className="footer-top">
          <div className="logo-container">
            <div className="logo-icon-wrap">
              <Activity className="logo-icon" size={18} />
            </div>
            <span className="logo-text">NexusAI</span>
          </div>
          <p className="footer-tagline">Enterprise Project Decision Intelligence System</p>
        </div>
        <div className="footer-divider" />
        <p className="footer-text">© 2026 NexusAI Enterprise. All rights reserved. Built with FastAPI + React + MongoDB.</p>
      </footer>
    </div>
  );
};

export default Landing;
