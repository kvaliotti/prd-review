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
import RagasEvaluationPage from './components/RagasEvaluationPage';

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
                <Navigate to="/chat" replace />
              </PrivateRoute>
            } 
          />
          <Route 
            path="/chat" 
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
          <Route 
            path="/ragas-evaluation" 
            element={
              <PrivateRoute>
                <RagasEvaluationPage />
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