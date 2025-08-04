import React, { useState, useEffect } from 'react';
import { notionAPI, prdAPI, prdAnalysisAPI, PRDCreate, PRDUpdate, PRDResponse, AnalysisSection, AnalysisEvent } from '../services/api';
import { NotionPage, PRDDocument, PageType } from '../types';
import './PRDReviewPage.css';

const PRDReviewPage: React.FC = () => {
  // State management
  const [notionPRDs, setNotionPRDs] = useState<PRDDocument[]>([]);
  const [userPRDs, setUserPRDs] = useState<PRDDocument[]>([]);
  const [selectedPRD, setSelectedPRD] = useState<PRDDocument | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editorContent, setEditorContent] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [showNewPRDModal, setShowNewPRDModal] = useState(false);
  const [newPRDTitle, setNewPRDTitle] = useState('');
  
  // Analysis state
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisResults, setAnalysisResults] = useState<Record<string, AnalysisSection>>({});
  const [analysisLogs, setAnalysisLogs] = useState<string[]>([]);
  const [finalReport, setFinalReport] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'results' | 'logs'>('results');
  const [analysisError, setAnalysisError] = useState<string>('');

  // Load PRDs on component mount
  useEffect(() => {
    loadAllPRDs();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Load all PRDs (both Notion and user-created)
  const loadAllPRDs = async () => {
    setLoading(true);
    try {
      await Promise.all([loadNotionPRDs(), loadUserPRDs()]);
    } catch (error) {
      console.error('Failed to load PRDs:', error);
    } finally {
      setLoading(false);
    }
  };

  // Load PRDs from Notion
  const loadNotionPRDs = async () => {
    try {
      const response = await notionAPI.getPages(PageType.prd, 100, 0);
      const prdDocs: PRDDocument[] = response.data.map((page: NotionPage) => ({
        id: `notion-${page.id}`,
        title: page.title,
        content: page.content || '',
        created_at: page.created_at,
        updated_at: page.updated_at,
        is_local: false,
        notion_url: page.notion_url,
        file_type: 'text' as const,
      }));
      setNotionPRDs(prdDocs);
    } catch (error) {
      console.error('Failed to load Notion PRDs:', error);
    }
  };

  // Load user-created PRDs from database
  const loadUserPRDs = async () => {
    try {
      const response = await prdAPI.getPRDs();
      const prdDocs: PRDDocument[] = response.data.map((prd: PRDResponse) => ({
        id: `user-${prd.id}`,
        title: prd.title,
        content: prd.content || '',
        created_at: prd.created_at,
        updated_at: prd.updated_at,
        is_local: true,
        file_type: 'markdown' as const,
      }));
      setUserPRDs(prdDocs);
    } catch (error) {
      console.error('Failed to load user PRDs:', error);
    }
  };

  // Create new PRD in database
  const createNewPRD = async () => {
    if (!newPRDTitle.trim()) return;

    setSaving(true);
    try {
      const prdData: PRDCreate = {
        title: newPRDTitle.trim(),
        content: `# ${newPRDTitle.trim()}\n\n## Overview\n\nWrite your PRD content here...\n\n## Features\n\n## User Stories\n\n## Success Metrics\n\n`,
      };

      const response = await prdAPI.createPRD(prdData);
      
      // Convert to PRDDocument format
      const newPRD: PRDDocument = {
        id: `user-${response.data.id}`,
        title: response.data.title,
        content: response.data.content || '',
        created_at: response.data.created_at,
        updated_at: response.data.updated_at,
        is_local: true,
        file_type: 'markdown',
      };

      // Add to user PRDs and select it
      setUserPRDs(prev => [newPRD, ...prev]);
      setSelectedPRD(newPRD);
      setEditorContent(newPRD.content || '');
      setIsEditing(true);
      setShowNewPRDModal(false);
      setNewPRDTitle('');
    } catch (error) {
      console.error('Failed to create PRD:', error);
      alert('Failed to create PRD. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  // Select a PRD document
  const selectPRD = async (prd: PRDDocument) => {
    setSelectedPRD(prd);
    setIsEditing(prd.is_local);

    if (prd.is_local) {
      // For user-created PRDs, content is already available
      setEditorContent(prd.content || '');
    } else {
      // Load detailed content for Notion PRDs
      try {
        const notionId = parseInt(prd.id.replace('notion-', ''));
        const response = await notionAPI.getPageDetails(notionId);
        setEditorContent(response.data.content || '');
      } catch (error) {
        console.error('Failed to load PRD details:', error);
        setEditorContent(prd.content || '');
      }
    }
  };

  // Save PRD changes to database
  const savePRDChanges = async () => {
    if (!selectedPRD?.is_local) return;

    setSaving(true);
    try {
      const prdId = parseInt(selectedPRD.id.replace('user-', ''));
      const updateData: PRDUpdate = {
        content: editorContent,
      };

      const response = await prdAPI.updatePRD(prdId, updateData);
      
      // Update the PRD in state
      const updatedPRD: PRDDocument = {
        ...selectedPRD,
        content: response.data.content || '',
        updated_at: response.data.updated_at,
      };

      setSelectedPRD(updatedPRD);
      setUserPRDs(prev => 
        prev.map(prd => 
          prd.id === selectedPRD.id ? updatedPRD : prd
        )
      );

      alert('PRD saved successfully!');
    } catch (error) {
      console.error('Failed to save PRD:', error);
      alert('Failed to save PRD. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  // Delete a PRD
  const deletePRD = async (prd: PRDDocument) => {
    if (!prd.is_local) return;
    
    if (!window.confirm(`Are you sure you want to delete "${prd.title}"?`)) return;

    try {
      const prdId = parseInt(prd.id.replace('user-', ''));
      await prdAPI.deletePRD(prdId);
      
      // Remove from state
      setUserPRDs(prev => prev.filter(p => p.id !== prd.id));
      
      // Clear selection if this PRD was selected
      if (selectedPRD?.id === prd.id) {
        setSelectedPRD(null);
        setEditorContent('');
        setIsEditing(false);
      }
      
      alert('PRD deleted successfully!');
    } catch (error) {
      console.error('Failed to delete PRD:', error);
      alert('Failed to delete PRD. Please try again.');
    }
  };

  // Parse final report into individual sections
  const parseFinalReport = (reportContent: string) => {
    const sections: { [key: string]: AnalysisSection } = {};
    
    // Split by section headers (## Section Name)
    const sectionRegex = /## (.+?) \(Score: (\d+)\/5\)\n([\s\S]*?)(?=\n## |$)/g;
    let match;
    
    while ((match = sectionRegex.exec(reportContent)) !== null) {
      const [, sectionName, score, content] = match;
      
      // Extract analysis (between ### Analysis and ### Recommendations)
      const analysisMatch = content.match(/### Analysis\n([\s\S]*?)(?=\n### |$)/);
      const analysis = analysisMatch ? analysisMatch[1].trim() : '';
      
      // Extract recommendations (bulleted list after ### Recommendations)
      const recommendationsMatch = content.match(/### Recommendations\n((?:- .+\n?)*)/);
      const recommendations = recommendationsMatch 
        ? recommendationsMatch[1].split('\n').filter(line => line.startsWith('- ')).map(line => line.substring(2).trim())
        : [];
      
      // Extract sources (bulleted list after ### Sources Referenced)
      const sourcesMatch = content.match(/### Sources Referenced\n((?:- .+\n?)*)/);
      const sources = sourcesMatch 
        ? sourcesMatch[1].split('\n').filter(line => line.startsWith('- ')).map(line => line.substring(2).trim())
        : [];
      
      sections[sectionName] = {
        section_name: sectionName,
        analysis,
        recommendations,
        score: parseInt(score),
        sources
      };
    }
    
    return sections;
  };

  // Start PRD analysis
  const startAnalysis = () => {
    if (!selectedPRD) return;

    setIsAnalyzing(true);
    setAnalysisResults({});
    setAnalysisLogs([]);
    setFinalReport('');
    setAnalysisError('');
    setActiveTab('results');

    const prdId = selectedPRD.id; // ID already contains the proper prefix (user-X or notion-X)
    
    const eventSource = prdAnalysisAPI.analyzePRD(
      prdId,
      (event: AnalysisEvent) => {
        switch (event.type) {
          case 'final_report':
            if (event.content) {
              setFinalReport(event.content);
              // Parse final report into sections
              const parsedSections = parseFinalReport(event.content);
              setAnalysisResults(parsedSections);
            }
            break;
            
          case 'log':
          case 'status':
            if (event.message) {
              setAnalysisLogs(prev => [...prev, event.message!]);
              // Check if analysis is complete
              if (event.message.includes('Analysis completed successfully')) {
                setIsAnalyzing(false);
                if (eventSource) {
                  eventSource.close();
                }
              }
            }
            break;
            
          case 'error':
            if (event.message) {
              setAnalysisError(event.message);
              setIsAnalyzing(false);
            }
            break;
            
          default:
            if (event.message) {
              setAnalysisLogs(prev => [...prev, event.message!]);
            }
        }
        
        // Check if analysis is complete
        if (event.type === 'final_report') {
          setIsAnalyzing(false);
        }
      },
      (error: string) => {
        setAnalysisError(error);
        setIsAnalyzing(false);
      }
    );

    // Cleanup function
    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  };

  // Get all PRDs sorted by update time
  const allPRDs = [...userPRDs, ...notionPRDs].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
  );

  return (
    <div className="prd-review-page">
      {/* Left Sidebar - PRD List */}
      <div className="prd-sidebar">
        <div className="sidebar-header">
          <h3>PRD Documents</h3>
          <button 
            className="new-prd-btn"
            onClick={() => setShowNewPRDModal(true)}
            disabled={saving}
          >
            + New PRD
          </button>
        </div>

        <div className="prd-list">
          {loading && <div className="loading">Loading PRDs...</div>}
          
          {allPRDs.map((prd) => (
            <div
              key={prd.id}
              className={`prd-item ${selectedPRD?.id === prd.id ? 'selected' : ''}`}
              onClick={() => selectPRD(prd)}
            >
              <div className="prd-item-header">
                <h4>{prd.title}</h4>
                <div className="prd-badges">
                  {prd.is_local && <span className="badge local">Local</span>}
                  {!prd.is_local && <span className="badge notion">Notion</span>}
                </div>
              </div>
              <div className="prd-item-meta">
                <span className="date">
                  {new Date(prd.updated_at).toLocaleDateString()}
                </span>
                {prd.is_local && (
                  <button
                    className="delete-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      deletePRD(prd);
                    }}
                    title="Delete PRD"
                  >
                    🗑️
                  </button>
                )}
              </div>
            </div>
          ))}

          {allPRDs.length === 0 && !loading && (
            <div className="empty-state">
              <p>No PRDs found.</p>
              <p>Create a new PRD or import from Notion.</p>
            </div>
          )}
        </div>
      </div>

      {/* Central Editor Area */}
      <div className="prd-editor">
        {selectedPRD ? (
          <>
            <div className="editor-header">
              <h2>{selectedPRD.title}</h2>
              <div className="editor-actions">
                {selectedPRD.is_local && (
                  <>
                    <button
                      className="save-btn"
                      onClick={savePRDChanges}
                      disabled={!isEditing || saving}
                    >
                      {saving ? 'Saving...' : 'Save'}
                    </button>
                    <button
                      className="edit-btn"
                      onClick={() => setIsEditing(!isEditing)}
                      disabled={saving}
                    >
                      {isEditing ? 'Preview' : 'Edit'}
                    </button>
                  </>
                )}
                {selectedPRD.notion_url && (
                  <a
                    href={selectedPRD.notion_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="notion-link"
                  >
                    Open in Notion
                  </a>
                )}
              </div>
            </div>

            <div className="editor-content">
              {isEditing && selectedPRD.is_local ? (
                <textarea
                  className="markdown-editor"
                  value={editorContent}
                  onChange={(e) => setEditorContent(e.target.value)}
                  placeholder="Write your PRD content in Markdown..."
                  disabled={saving}
                />
              ) : (
                <div className="markdown-preview">
                  <pre>{editorContent}</pre>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="no-selection">
            <h3>Select a PRD to view or edit</h3>
            <p>Choose a PRD from the sidebar or create a new one to get started.</p>
          </div>
        )}
      </div>

      {/* Right Sidebar - Analysis */}
              <div className="prd-analysis">
        <div className="analysis-header">
          <h3>PRD Analysis</h3>
          <button 
            className="analyze-btn"
            onClick={startAnalysis}
            disabled={!selectedPRD || isAnalyzing}
          >
            {isAnalyzing ? 'Analyzing...' : 'Run Analysis'}
          </button>
        </div>

        {analysisError && (
          <div className="error-message">
            <p>{analysisError}</p>
          </div>
        )}

        {(Object.keys(analysisResults).length > 0 || analysisLogs.length > 0) && (
          <div className="analysis-content">
            <div className="analysis-tabs">
              <button 
                className={`tab-btn ${activeTab === 'results' ? 'active' : ''}`}
                onClick={() => setActiveTab('results')}
              >
                Analysis Results
              </button>
              <button 
                className={`tab-btn ${activeTab === 'logs' ? 'active' : ''}`}
                onClick={() => setActiveTab('logs')}
              >
                Graph Logs
              </button>
            </div>

            {activeTab === 'results' && (
              <div className="analysis-results">
                {!finalReport && (
                  <div className="no-analysis">
                    {isAnalyzing ? 'Analysis in progress...' : 'No analysis results yet.'}
                  </div>
                )}
                
                {finalReport && Object.keys(analysisResults).length > 0 && (
                  <>
                    {/* Score Summary Bar */}
                    <div className="score-summary">
                      <h4>Analysis Scores</h4>
                      <div className="scores-bar">
                        {Object.entries(analysisResults).map(([sectionName, section]) => (
                          <div key={sectionName} className="score-item">
                            <span className="score-label">{sectionName}</span>
                            <span className={`score-badge score-${section.score}`}>
                              {section.score}/5
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                    
                    {/* Full Final Report */}
                    <div className="final-report-display">
                      <div className="markdown-content">
                        {finalReport.split('\n').map((line, index) => {
                          if (line.startsWith('# ')) {
                            return <h1 key={index}>{line.substring(2)}</h1>;
                          } else if (line.startsWith('## ')) {
                            return <h2 key={index}>{line.substring(3)}</h2>;
                          } else if (line.startsWith('### ')) {
                            return <h3 key={index}>{line.substring(4)}</h3>;
                          } else if (line.startsWith('**') && line.endsWith('**')) {
                            return <p key={index}><strong>{line.slice(2, -2)}</strong></p>;
                          } else if (line.startsWith('- ')) {
                            return <li key={index}>{line.substring(2)}</li>;
                          } else if (line.trim() === '---') {
                            return <hr key={index} />;
                          } else if (line.trim()) {
                            return <p key={index}>{line}</p>;
                          }
                          return <br key={index} />;
                        })}
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}

            {activeTab === 'logs' && (
              <div className="analysis-logs">
                {analysisLogs.length === 0 ? (
                  <div className="no-analysis">No logs yet.</div>
                ) : (
                  analysisLogs.map((log, index) => (
                    <div key={index} className="log-entry">
                      <span className="log-timestamp">
                        {new Date().toLocaleTimeString()}
                      </span>
                      <span className="log-message">{log}</span>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        )}

        {!isAnalyzing && Object.keys(analysisResults).length === 0 && !finalReport && !analysisError && (
          <div className="no-analysis">
            <p>Select a PRD and click "Run Analysis" to get started.</p>
          </div>
        )}
      </div>

      {/* New PRD Modal */}
      {showNewPRDModal && (
        <div className="modal-overlay">
          <div className="modal">
            <div className="modal-header">
              <h3>Create New PRD</h3>
              <button
                className="close-btn"
                onClick={() => setShowNewPRDModal(false)}
                disabled={saving}
              >
                ×
              </button>
            </div>
            <div className="modal-content">
              <input
                type="text"
                className="prd-title-input"
                placeholder="Enter PRD title..."
                value={newPRDTitle}
                onChange={(e) => setNewPRDTitle(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && !saving && createNewPRD()}
                autoFocus
                disabled={saving}
              />
            </div>
            <div className="modal-actions">
              <button
                className="cancel-btn"
                onClick={() => setShowNewPRDModal(false)}
                disabled={saving}
              >
                Cancel
              </button>
              <button
                className="create-btn"
                onClick={createNewPRD}
                disabled={!newPRDTitle.trim() || saving}
              >
                {saving ? 'Creating...' : 'Create PRD'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PRDReviewPage; 