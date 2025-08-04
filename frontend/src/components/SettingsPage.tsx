import React, { useState, useEffect } from 'react';
import { notionAPI } from '../services/api';
import { NotionSettingsUpdate } from '../types';
import './SettingsPage.css';

const SettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<NotionSettingsUpdate>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await notionAPI.getSettings();
        if (response.data) {
          setSettings({
            notion_token: response.data.notion_token || '',
            prd_database_id: response.data.prd_database_id || '',
            research_database_id: response.data.research_database_id || '',
            analytics_database_id: response.data.analytics_database_id || '',
            import_prd: response.data.import_prd || false,
            import_research: response.data.import_research || false,
            import_analytics: response.data.import_analytics || false,
          });
        }
      } catch (error) {
        console.error('Error fetching settings:', error);
        setMessage({ type: 'error', text: 'Failed to load settings.' });
      } finally {
        setIsLoading(false);
      }
    };
    fetchSettings();
  }, []);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setSettings(prev => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const handleTestConnection = async () => {
    if (!settings.notion_token) {
      setMessage({ type: 'error', text: 'Notion token is required to test the connection.' });
      return;
    }
    setIsTesting(true);
    setMessage(null);
    try {
      // Pass the whole settings object, let the backend handle it
      const response = await notionAPI.testConnection(settings);
      if (response.data.connected) {
        setMessage({ type: 'success', text: 'Connection successful!' });
      } else {
        setMessage({ type: 'error', text: `Connection failed: ${response.data.message}` });
      }
    } catch (error) {
      console.error('Error testing connection:', error);
      setMessage({ type: 'error', text: 'An error occurred while testing the connection.' });
    } finally {
      setIsTesting(false);
    }
  };

  const handleSaveChanges = async () => {
    setIsSaving(true);
    setMessage(null);
    try {
      await notionAPI.updateSettings(settings);
      setMessage({ type: 'success', text: 'Settings saved successfully!' });
    } catch (error) {
      console.error('Error saving settings:', error);
      setMessage({ type: 'error', text: 'Failed to save settings.' });
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return <div>Loading settings...</div>;
  }

  return (
    <div className="settings-page">
      <div className="settings-container">
        <div className="settings-header">
          <h1>Settings</h1>
          <p>Configure your Notion integration and manage your knowledge base imports</p>
        </div>
        
        {message && (
          <div className={`message ${message.type}`}>
            {message.text}
          </div>
        )}

        <div className="settings-content">
          <div className="settings-card">
            <div className="card-header">
              <span className="card-icon">🔗</span>
              <div>
                <h2 className="card-title">Notion API Connection</h2>
                <p className="card-description">Connect your Notion workspace to import documents</p>
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="notion_token">Notion API Token</label>
              <div className="input-group">
                <input
                  type="password"
                  id="notion_token"
                  name="notion_token"
                  value={settings.notion_token || ''}
                  onChange={handleInputChange}
                  placeholder="Enter your Notion API token (secret_...)"
                />
                <button 
                  className="btn-secondary" 
                  onClick={handleTestConnection} 
                  disabled={isTesting}
                >
                  {isTesting ? 'Testing...' : 'Test Connection'}
                </button>
              </div>
            </div>
          </div>

          <div className="settings-card">
            <div className="card-header">
              <span className="card-icon">📊</span>
              <div>
                <h2 className="card-title">Database Configuration</h2>
                <p className="card-description">Select which Notion databases to import from</p>
              </div>
            </div>

            <div className="database-section">
              <div className={`database-group ${settings.import_prd ? 'enabled' : ''}`}>
                <div className="database-checkbox">
                  <input 
                    type="checkbox"
                    id="import_prd"
                    name="import_prd"
                    checked={settings.import_prd || false}
                    onChange={handleInputChange}
                  />
                  <label htmlFor="import_prd">Import Product Requirements Documents (PRDs)</label>
                </div>
                <input
                  type="text"
                  name="prd_database_id"
                  value={settings.prd_database_id || ''}
                  onChange={handleInputChange}
                  placeholder="Enter PRDs database ID"
                  disabled={!settings.import_prd}
                />
              </div>

              <div className={`database-group ${settings.import_research ? 'enabled' : ''}`}>
                <div className="database-checkbox">
                  <input 
                    type="checkbox"
                    id="import_research"
                    name="import_research"
                    checked={settings.import_research || false}
                    onChange={handleInputChange}
                  />
                  <label htmlFor="import_research">Import User Research Documents</label>
                </div>
                <input
                  type="text"
                  name="research_database_id"
                  value={settings.research_database_id || ''}
                  onChange={handleInputChange}
                  placeholder="Enter User Research database ID"
                  disabled={!settings.import_research}
                />
              </div>

              <div className={`database-group ${settings.import_analytics ? 'enabled' : ''}`}>
                <div className="database-checkbox">
                  <input 
                    type="checkbox"
                    id="import_analytics"
                    name="import_analytics"
                    checked={settings.import_analytics || false}
                    onChange={handleInputChange}
                  />
                  <label htmlFor="import_analytics">Import Data Analytics Reports</label>
                </div>
                <input
                  type="text"
                  name="analytics_database_id"
                  value={settings.analytics_database_id || ''}
                  onChange={handleInputChange}
                  placeholder="Enter Data Analytics database ID"
                  disabled={!settings.import_analytics}
                />
              </div>
            </div>

            <div className="button-group">
              <button className="btn-primary" onClick={handleSaveChanges} disabled={isSaving}>
                {isSaving ? 'Saving...' : 'Save Configuration'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage; 