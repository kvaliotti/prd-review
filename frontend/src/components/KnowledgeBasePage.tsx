import React, { useState, useEffect } from 'react';
import { notionAPI } from '../services/api';
import { KnowledgeBaseStats, NotionPage, PageType } from '../types';
import FileUpload from './FileUpload';
import './KnowledgeBasePage.css';

const KnowledgeBasePage: React.FC = () => {
  const [stats, setStats] = useState<KnowledgeBaseStats | null>(null);
  const [pages, setPages] = useState<NotionPage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isImporting, setIsImporting] = useState(false);
  const [importProgress, setImportProgress] = useState<any>(null);

  const fetchStats = async () => {
    try {
      const response = await notionAPI.getStats();
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  const fetchPages = async (pageType?: PageType) => {
    try {
      const response = await notionAPI.getPages(pageType);
      setPages(response.data);
    } catch (error) {
      console.error('Error fetching pages:', error);
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setIsLoading(true);
      await Promise.all([fetchStats(), fetchPages()]);
      setIsLoading(false);
    };
    loadData();
  }, []);

  const handleUploadComplete = () => {
    // Refresh data after upload
    fetchStats();
    fetchPages();
  };

  const handleStartImport = async (forceUpdate: boolean) => {
    setIsImporting(true);
    setImportProgress({ status: 'starting' });
    try {
      const response = await notionAPI.startImport(forceUpdate);
      const reader = response.data.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n\n').filter(Boolean);
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.substring(6));
            setImportProgress(data);
          }
        }
      }
    } catch (error) {
      console.error('Error during import:', error);
      setImportProgress({ status: 'error', error: 'An unexpected error occurred.' });
    } finally {
      setIsImporting(false);
      await fetchStats();
      await fetchPages();
    }
  };
  
  const renderImportProgress = () => {
    if (!isImporting || !importProgress) return null;
    
    switch (importProgress.status) {
      case 'starting':
        return <p>Starting import...</p>;
      case 'fetching_pages':
        return <p>Fetching pages from {importProgress.database_type} database...</p>;
      case 'pages_fetched':
        return <p>Fetched {importProgress.pages_count} pages. Processing...</p>;
      case 'page_processed':
        return (
          <p>
            Processing page {importProgress.page_index}/{importProgress.total_pages}: {importProgress.page_title}
            <br />
            Chunks created: {importProgress.chunks_created}, Embeddings: {importProgress.embeddings_created}
          </p>
        );
      case 'completed':
        return (
          <p>
            Import completed!
            <br />
            Pages imported: {importProgress.total_pages_imported}, 
            Chunks created: {importProgress.total_chunks_created}, 
            Embeddings generated: {importProgress.total_embeddings_generated}
          </p>
        );
      case 'error':
        return <p style={{ color: 'red' }}>Error: {importProgress.error}</p>;
      default:
        return null;
    }
  };

  if (isLoading) {
    return (
      <div className="knowledge-base-page">
        <div className="kb-container">
          <div className="loading-spinner">
            <div className="spinner"></div>
            Loading knowledge base...
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="knowledge-base-page">
      <div className="kb-container">
        <div className="kb-header">
          <h1>Knowledge Base</h1>
          <p>Manage your imported documents and track integration progress</p>
        </div>

        <div className="kb-content">
          <div className="kb-sidebar">
            <div className="kb-card">
              <div className="card-header">
                <span className="card-icon">📊</span>
                <div>
                  <h2 className="card-title">Overview</h2>
                  <p className="card-description">Your knowledge base statistics</p>
                </div>
              </div>

              {stats ? (
                <div className="stats-grid">
                  <div className="stat-item">
                    <span className="stat-number">{stats.total_pages}</span>
                    <span className="stat-label">Total Pages</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-number">{stats.by_type.prd || 0}</span>
                    <span className="stat-label">PRDs</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-number">{stats.by_type.research || 0}</span>
                    <span className="stat-label">Research</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-number">{stats.by_type.analytics || 0}</span>
                    <span className="stat-label">Analytics</span>
                  </div>
                  <div className="stat-item">
                    <span className="stat-number">{stats.total_chunks}</span>
                    <span className="stat-label">Text Chunks</span>
                  </div>
                </div>
              ) : (
                <div className="empty-state">
                  <span className="empty-state-icon">📝</span>
                  <h3>No Data Available</h3>
                  <p>Import from Notion to get started</p>
                </div>
              )}
            </div>

            <div className="kb-card">
              <div className="card-header">
                <span className="card-icon">⚡</span>
                <div>
                  <h2 className="card-title">Import Controls</h2>
                  <p className="card-description">Sync data from Notion</p>
                </div>
              </div>

              <div className="import-controls">
                <div className="button-group">
                  <button 
                    className="btn-primary" 
                    onClick={() => handleStartImport(false)} 
                    disabled={isImporting}
                  >
                    {isImporting ? 'Importing...' : 'Start Import'}
                  </button>
                  <button 
                    className="btn-secondary" 
                    onClick={() => handleStartImport(true)} 
                    disabled={isImporting}
                  >
                    {isImporting ? 'Importing...' : 'Force Re-import'}
                  </button>
                </div>
                
                {renderImportProgress() && (
                  <div className="progress-section">
                    <div className="progress-text">
                      {renderImportProgress()}
                    </div>
                  </div>
                )}
              </div>
            </div>

            <FileUpload onUploadComplete={handleUploadComplete} />
          </div>

          <div className="kb-main">
            <div className="card-header">
              <span className="card-icon">📚</span>
              <div>
                <h2 className="card-title">Imported Pages</h2>
                <p className="card-description">Browse and filter your knowledge base content</p>
              </div>
            </div>

            <div className="filter-section">
              <div className="filter-buttons">
                <button 
                  className="filter-btn" 
                  onClick={() => fetchPages()}
                >
                  All Pages
                </button>
                <button 
                  className="filter-btn" 
                  onClick={() => fetchPages(PageType.prd)}
                >
                  PRDs
                </button>
                <button 
                  className="filter-btn" 
                  onClick={() => fetchPages(PageType.research)}
                >
                  Research
                </button>
                <button 
                  className="filter-btn" 
                  onClick={() => fetchPages(PageType.analytics)}
                >
                  Analytics
                </button>
              </div>
            </div>
            
            {pages.length > 0 ? (
              <div className="pages-table-container">
                <table className="pages-table">
                  <thead>
                    <tr>
                      <th>Title</th>
                      <th>Type</th>
                      <th>Last Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pages.map(page => (
                      <tr key={page.id}>
                        <td>
                          {page.notion_url ? (
                            <a 
                              href={page.notion_url} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="page-link"
                            >
                              {page.title}
                            </a>
                          ) : (
                            <span className="page-link">{page.title}</span>
                          )}
                        </td>
                        <td>
                          <span className={`page-type-badge page-type-${page.page_type.toLowerCase()}`}>
                            {page.page_type}
                          </span>
                        </td>
                        <td>{new Date(page.updated_at).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state">
                <span className="empty-state-icon">📄</span>
                <h3>No Pages Found</h3>
                <p>No documents have been imported yet. Use the import controls to sync your Notion content.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default KnowledgeBasePage; 