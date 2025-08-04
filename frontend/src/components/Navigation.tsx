import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Navigation.css';

const Navigation: React.FC = () => {
  const { user, logout } = useAuth();
  const location = useLocation();

  const isActive = (path: string) => {
    return location.pathname === path;
  };

  return (
    <nav className="navigation">
      <div className="nav-brand">
        <h2>PRD Review</h2>
      </div>
      
      <div className="nav-menu">
        <Link 
          to="/" 
          className={`nav-link ${isActive('/') ? 'active' : ''}`}
        >
          <span className="nav-icon">💬</span>
          Chat
        </Link>
        <Link 
          to="/knowledge-base" 
          className={`nav-link ${isActive('/knowledge-base') ? 'active' : ''}`}
        >
          <span className="nav-icon">📚</span>
          Knowledge Base
        </Link>
        <Link 
          to="/prd-review" 
          className={`nav-link ${isActive('/prd-review') ? 'active' : ''}`}
        >
          <span className="nav-icon">📋</span>
          PRD Review
        </Link>
        <Link 
          to="/settings" 
          className={`nav-link ${isActive('/settings') ? 'active' : ''}`}
        >
          <span className="nav-icon">⚙️</span>
          Settings
        </Link>
      </div>

      <div className="nav-user">
        <span className="user-email">{user?.email}</span>
        <button onClick={logout} className="logout-btn">
          Logout
        </button>
      </div>
    </nav>
  );
};

export default Navigation; 