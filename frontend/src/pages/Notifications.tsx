import React, { useEffect, useState } from 'react';
import {
  Bell, BellOff, CheckCheck, AlertTriangle, Info, Zap,
  AlertCircle, TrendingUp, FileText, Users, RefreshCw
} from 'lucide-react';
import api from '../services/api';
import './Notifications.css';

interface Notification {
  id: string;
  type: string;
  title: string;
  message: string;
  related_project_id?: string;
  severity: string;
  is_read: boolean;
  created_at: string | null;
}

const typeIcon = (type: string, severity: string) => {
  if (type?.includes('risk') || severity === 'high' || severity === 'critical')
    return <AlertTriangle size={20} className="notif-icon error" />;
  if (type?.includes('recommendation'))
    return <Zap size={20} className="notif-icon warning" />;
  if (type?.includes('resource') || type?.includes('task'))
    return <Users size={20} className="notif-icon primary" />;
  if (type?.includes('report') || type?.includes('document'))
    return <FileText size={20} className="notif-icon success" />;
  if (type?.includes('budget') || type?.includes('deadline'))
    return <TrendingUp size={20} className="notif-icon warning" />;
  return <Info size={20} className="notif-icon primary" />;
};

const formatDate = (val: string | null) => {
  if (!val) return '—';
  try {
    return new Date(val).toLocaleString('en-IN', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  } catch {
    return String(val);
  }
};

const Notifications: React.FC = () => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'unread'>('all');
  const [markingAll, setMarkingAll] = useState(false);

  const fetchNotifications = async () => {
    setLoading(true);
    try {
      const unread_only = filter === 'unread';
      const res = await api.get(`/dashboard/notifications?unread_only=${unread_only}`);
      setNotifications(res.data);
    } catch (err) {
      console.error('Failed to fetch notifications', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifications();
  }, [filter]);

  const markRead = async (id: string) => {
    try {
      await api.put(`/dashboard/notifications/${id}/read`);
      setNotifications(prev =>
        prev.map(n => n.id === id ? { ...n, is_read: true } : n)
      );
    } catch (err) {
      console.error('Failed to mark notification as read', err);
    }
  };

  const markAllRead = async () => {
    setMarkingAll(true);
    try {
      await api.put('/dashboard/notifications/read-all');
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    } catch (err) {
      console.error('Failed to mark all as read', err);
    } finally {
      setMarkingAll(false);
    }
  };

  const unreadCount = notifications.filter(n => !n.is_read).length;

  return (
    <div className="notif-page">
      <div className="page-header flex-between">
        <div>
          <h1 className="flex-center gap-2">
            <Bell size={28} />
            Notifications
            {unreadCount > 0 && (
              <span className="unread-badge">{unreadCount}</span>
            )}
          </h1>
          <p>System alerts, risk warnings, and action items for your projects</p>
        </div>
        <div className="notif-actions">
          <button
            className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All
          </button>
          <button
            className={`filter-btn ${filter === 'unread' ? 'active' : ''}`}
            onClick={() => setFilter('unread')}
          >
            Unread {unreadCount > 0 && `(${unreadCount})`}
          </button>
          <button className="outline-button" onClick={fetchNotifications}>
            <RefreshCw size={14} style={{ display: 'inline', marginRight: '0.4rem' }} />
            Refresh
          </button>
          {unreadCount > 0 && (
            <button
              className="primary-button"
              onClick={markAllRead}
              disabled={markingAll}
            >
              <CheckCheck size={14} style={{ display: 'inline', marginRight: '0.4rem' }} />
              {markingAll ? 'Marking…' : 'Mark All Read'}
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <div className="loading-state">Loading notifications…</div>
      ) : notifications.length === 0 ? (
        <div className="empty-state glass-panel">
          <BellOff size={48} className="empty-icon" />
          <h3>No notifications</h3>
          <p>
            {filter === 'unread'
              ? 'You\'re all caught up — no unread notifications.'
              : 'Generate AI insights or trigger events to create notifications.'}
          </p>
        </div>
      ) : (
        <div className="notif-list">
          {notifications.map(n => (
            <div
              key={n.id}
              className={`notif-card glass-panel ${!n.is_read ? 'unread' : ''} severity-${n.severity}`}
              onClick={() => !n.is_read && markRead(n.id)}
            >
              <div className="notif-left">
                {typeIcon(n.type, n.severity)}
              </div>
              <div className="notif-body">
                <div className="notif-header-row">
                  <h4 className="notif-title">{n.title}</h4>
                  <div className="notif-meta">
                    <span className={`severity-pill sev-${n.severity}`}>{n.severity}</span>
                    <span className="notif-time">{formatDate(n.created_at)}</span>
                  </div>
                </div>
                <p className="notif-message">{n.message}</p>
                <div className="notif-footer">
                  <span className="notif-type-label">{n.type?.replace(/_/g, ' ')}</span>
                  {!n.is_read && (
                    <button
                      className="mark-read-btn"
                      onClick={e => { e.stopPropagation(); markRead(n.id); }}
                    >
                      Mark read
                    </button>
                  )}
                  {n.is_read && <span className="read-label">✓ Read</span>}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Notifications;
