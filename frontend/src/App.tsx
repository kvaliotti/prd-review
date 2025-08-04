import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import PrivateRoute from './components/PrivateRoute';
import Login from './components/Login';
import Register from './components/Register';
import ChatInterface from './components/ChatInterface';
import SettingsPage from './components/SettingsPage';
import KnowledgeBasePage from './components/KnowledgeBasePage';
import PRDReviewPage from './components/PRDReviewPage';
import Navigation from './components/Navigation';

function App() {
  return (
    <AuthProvider>
      <MainApp />
    </AuthProvider>
  );
}

function MainApp() {
  const { user } = useAuth();

  return (
    <Router>
      <div className="App">
        {user && <Navigation />}
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          
          {/* Protected routes */}
          <Route 
            path="/" 
            element={
              <PrivateRoute>
                <ChatInterface />
              </PrivateRoute>
            } 
          />
          <Route 
            path="/settings" 
            element={
              <PrivateRoute>
                <SettingsPage />
              </PrivateRoute>
            } 
          />
          <Route 
            path="/knowledge-base" 
            element={
              <PrivateRoute>
                <KnowledgeBasePage />
              </PrivateRoute>
            }
          />
          <Route 
            path="/prd-review" 
            element={
              <PrivateRoute>
                <PRDReviewPage />
              </PrivateRoute>
            }
          />
          
          {/* Default redirect */}
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App; 