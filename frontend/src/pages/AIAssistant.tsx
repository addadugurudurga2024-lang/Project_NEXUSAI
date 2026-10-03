import React, { useState, useEffect, useRef } from 'react';
import { Bot, Send, Sparkles, Trash2, HelpCircle } from 'lucide-react';
import api from '../services/api';
import './AIAssistant.css';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

const SUGGESTIONS = [
  'Which projects are at high risk?',
  'Which project is most delayed?',
  'How many tasks are overdue?',
  'Who has available capacity?',
  'What should we prioritize today?',
];

const AIAssistant: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [projects, setProjects] = useState<any[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch projects for optional filter dropdown
  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const res = await api.get('/projects/');
        setProjects(res.data || []);
      } catch (err) {
        console.error('Failed to fetch projects list for assistant', err);
      }
    };
    fetchProjects();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = async (queryText?: string) => {
    const textToSend = queryText || input.trim();
    if (!textToSend || loading) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: textToSend,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!queryText) setInput('');
    setLoading(true);

    try {
      // Build lightweight conversation history for the assistant
      const history = messages.slice(-4).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const payload: any = {
        message: textToSend,
        history,
      };
      if (selectedProjectId) {
        payload.project_id = selectedProjectId;
      }

      const res = await api.post('/ai-assistant/chat', payload);

      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: res.data.response || 'No response received from assistant.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, aiMsg]);
    } catch (err: any) {
      const errMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content:
          err.response?.data?.detail ||
          'The AI Decision Assistant is currently unavailable. Please try again.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
  };

  // Simple markdown renderer for bold, lists, and headers
  const renderFormattedMessage = (content: string) => {
    const lines = content.split('\n');
    return lines.map((line, idx) => {
      if (line.startsWith('### ')) {
        return <h3 key={idx}>{line.replace('### ', '')}</h3>;
      }
      if (line.startsWith('- ')) {
        const bulletText = line.replace('- ', '');
        return (
          <li key={idx}>
            {renderInlineMarkdown(bulletText)}
          </li>
        );
      }
      if (line.trim() === '') {
        return <div key={idx} style={{ height: '0.5rem' }} />;
      }
      return <p key={idx}>{renderInlineMarkdown(line)}</p>;
    });
  };

  const renderInlineMarkdown = (text: string) => {
    // Basic bold parser for **text**
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i}>{part.slice(2, -2)}</strong>;
      }
      return part;
    });
  };

  return (
    <div className="ai-assistant-page">
      {/* Header */}
      <div className="ai-assistant-header glass-panel">
        <div className="ai-header-left">
          <div className="ai-icon-badge">
            <Bot size={24} />
          </div>
          <div className="ai-title-desc">
            <h1>NexusAI Decision Assistant</h1>
            <p>Grounded intelligence powered by live project data, ML predictions & recommendations</p>
          </div>
        </div>

        <div className="ai-header-right">
          <select
            className="project-select-filter"
            value={selectedProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
          >
            <option value="">All Scoped Projects</option>
            {projects.map((p) => (
              <option key={p.id || p._id} value={p.id || p._id}>
                {p.name}
              </option>
            ))}
          </select>

          {messages.length > 0 && (
            <button className="ai-clear-btn" onClick={clearChat} title="Clear conversation">
              <Trash2 size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Chat Area */}
      <div className="ai-chat-window">
        <div className="ai-messages-area">
          {messages.length === 0 ? (
            <div className="ai-empty-state">
              <div className="empty-icon-circle">
                <Sparkles size={30} />
              </div>
              <h3>Ask anything about your projects and teams</h3>
              <p>
                Get instant, grounded answers distinguishing real facts, ML predictions, and actionable recommendations.
              </p>

              <div className="prompt-chips-grid">
                {SUGGESTIONS.map((s, idx) => (
                  <button
                    key={idx}
                    className="prompt-chip"
                    onClick={() => handleSend(s)}
                  >
                    <HelpCircle size={14} />
                    <span>{s}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((m) => (
                <div key={m.id} className={`ai-msg-row ${m.role}`}>
                  <div className={`msg-avatar ${m.role === 'user' ? 'user-av' : 'ai-av'}`}>
                    {m.role === 'user' ? 'You' : <Bot size={18} />}
                  </div>
                  <div className="msg-bubble">
                    {renderFormattedMessage(m.content)}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="ai-msg-row assistant">
                  <div className="msg-avatar ai-av">
                    <Bot size={18} />
                  </div>
                  <div className="msg-bubble">
                    <div className="typing-indicator">
                      <div className="typing-dot" />
                      <div className="typing-dot" />
                      <div className="typing-dot" />
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Input Bar */}
        <div className="ai-input-area">
          <input
            type="text"
            className="ai-input-field"
            placeholder="Ask about project risks, overdue tasks, employee workload, predictions..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            disabled={loading}
          />
          <button
            className="ai-send-btn"
            onClick={() => handleSend()}
            disabled={loading || !input.trim()}
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
};

export default AIAssistant;
