import React, { useState, useEffect } from 'react';
import { ragasAPI } from '../services/api';  // Changed from api to ragasAPI
import './RagasEvaluationPage.css';

interface EvaluationStatus {
  status: string;
  progress: number;
  current_step: string;
  message: string;
}

interface EvaluationResults {
  evaluation_id: string;
  user_id: number;
  testset_size: number;
  dataset_samples: number;
  evaluations: {
    naive: {
      retriever_type: string;
      metrics: Record<string, number>;
      samples_evaluated: number;
    };
    contextual_compression: {
      retriever_type: string;
      metrics: Record<string, number>;
      samples_evaluated: number;
    };
  };
  comparison: {
    winner: string;
    metrics_comparison: Record<string, {
      naive: number;
      compression: number;
      difference: number;
      winner: string;
    }>;
    summary: string;
  };
  start_time: string;
  end_time: string;
}

const RagasEvaluationPage: React.FC = () => {
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [status, setStatus] = useState<EvaluationStatus | null>(null);
  const [results, setResults] = useState<EvaluationResults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [testsetSize, setTestsetSize] = useState(10);
  const [userId, setUserId] = useState<number>(4); // Default to demo user

  // Poll for status updates when evaluation is running
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;

    if (isEvaluating) {
      interval = setInterval(async () => {
        try {
          const response = await ragasAPI.getStatus();  // Changed from api.get to ragasAPI.getStatus
          const statusData = response.data;
          setStatus(statusData);

          // Check if evaluation is complete or failed
          if (statusData.status === 'completed') {
            setIsEvaluating(false);
            // Fetch results
            const resultsResponse = await ragasAPI.getResults();  // Changed from api.get to ragasAPI.getResults
            if (resultsResponse.data.results) {
              setResults(resultsResponse.data.results);
            }
          } else if (statusData.status === 'failed') {
            setIsEvaluating(false);
            setError(statusData.message || 'Evaluation failed');
          }
        } catch (err) {
          console.error('Error fetching status:', err);
        }
      }, 2000); // Poll every 2 seconds
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isEvaluating]);

  const startEvaluation = async () => {
    try {
      setError(null);
      setResults(null);
      setIsEvaluating(true);

      const response = await ragasAPI.startEvaluation({  // Changed from api.post to ragasAPI.startEvaluation
        user_id: userId,
        testset_size: testsetSize
      });

      setStatus({
        status: 'pending',
        progress: 0,
        current_step: 'Evaluation queued',
        message: response.data.message
      });

    } catch (err: any) {
      setIsEvaluating(false);
      setError(err.response?.data?.detail || 'Failed to start evaluation');
    }
  };

  const resetEvaluation = async () => {
    try {
      await ragasAPI.resetEvaluation();  // Changed from api.delete to ragasAPI.resetEvaluation
      setIsEvaluating(false);
      setStatus(null);
      setResults(null);
      setError(null);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to reset evaluation');
    }
  };

  const formatMetricName = (metric: string) => {
    return metric.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase());
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return '#28a745';
      case 'failed': return '#dc3545';
      case 'pending': return '#6c757d';
      default: return '#007bff';
    }
  };

  const formatCurrentStep = (currentStep: string) => {
    // Make technical messages more user-friendly
    if (currentStep.includes("Initializing RAGAS components in separate thread")) {
      return "🧵 Initializing evaluation system (thread-safe mode)";
    } else if (currentStep.includes("Generating synthetic dataset")) {
      return "🔬 Creating test questions from your research data";
    } else if (currentStep.includes("full pipeline")) {
      return `🎯 ${currentStep.replace("full pipeline", "complete system")}`;
    } else if (currentStep.includes("Evaluating") && currentStep.includes("retriever")) {
      return currentStep.replace("retriever", "pipeline");
    }
    return currentStep;
  };

  return (
    <div className="ragas-evaluation-page">
      <div className="page-header">
        <h1>RAGAS Evaluation</h1>
        <p>Evaluate and compare RAG retrieval systems using RAGAS metrics</p>
      </div>

      {/* Configuration Section */}
      <div className="evaluation-config">
        <h2>🔧 Configuration</h2>
        <div className="config-form">
          <div className="form-group">
            <label htmlFor="userId">User ID (data source):</label>
            <select
              id="userId"
              value={userId}
              onChange={(e) => setUserId(Number(e.target.value))}
              disabled={isEvaluating}
            >
              <option value={4}>User 4 (Demo Data)</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="testsetSize">Test Set Size:</label>
            <input
              type="number"
              id="testsetSize"
              min="5"
              max="20"
              value={testsetSize}
              onChange={(e) => setTestsetSize(Number(e.target.value))}
              disabled={isEvaluating}
            />
            <small>Number of synthetic test samples to generate (5-20)</small>
          </div>

          <div className="action-buttons">
            <button
              onClick={startEvaluation}
              disabled={isEvaluating}
              className="btn-primary"
            >
              {isEvaluating ? 'Evaluation Running...' : 'Start RAGAS Evaluation'}
            </button>

            {status && (
              <button
                onClick={resetEvaluation}
                disabled={isEvaluating}
                className="btn-secondary"
              >
                Reset
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Status Section */}
      {status && (
        <div className="evaluation-status">
          <h2>📊 Evaluation Status</h2>
          <div className="status-card">
            <div className="status-header">
              <span 
                className="status-badge"
                style={{ backgroundColor: getStatusColor(status.status) }}
              >
                {status.status.toUpperCase()}
              </span>
              <span className="progress-text">{status.progress}%</span>
            </div>
            
            <div className="progress-bar">
              <div 
                className="progress-fill"
                style={{ width: `${status.progress}%` }}
              ></div>
            </div>
            
            <div className="status-details">
              <p><strong>Current Step:</strong> {formatCurrentStep(status.current_step)}</p>
              <p><strong>Message:</strong> {status.message}</p>
            </div>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="error-section">
          <h2>❌ Error</h2>
          <div className="error-card">
            <p>{error}</p>
          </div>
        </div>
      )}

      {/* Results Section */}
      {results && (
        <div className="evaluation-results">
          <h2>🎯 Evaluation Results</h2>
          
          {/* Summary Card */}
          <div className="results-summary">
            <h3>Summary</h3>
            <div className="summary-stats">
              <div className="stat">
                <span className="stat-label">Evaluation ID:</span>
                <span className="stat-value">{results.evaluation_id}</span>
              </div>
              <div className="stat">
                <span className="stat-label">Dataset Size:</span>
                <span className="stat-value">{results.dataset_samples} samples</span>
              </div>
              <div className="stat">
                <span className="stat-label">Winner:</span>
                <span className={`stat-value winner-${results.comparison.winner}`}>
                  {results.comparison.winner === 'compression' ? 'Contextual Compression' : 'Naive'} Retriever
                </span>
              </div>
              <div className="stat">
                <span className="stat-label">Duration:</span>
                <span className="stat-value">
                  {Math.round((new Date(results.end_time).getTime() - new Date(results.start_time).getTime()) / 1000)}s
                </span>
              </div>
            </div>
            <p className="comparison-summary">{results.comparison.summary}</p>
          </div>

          {/* Metrics Comparison */}
          <div className="metrics-comparison">
            <h3>📈 Metrics Comparison</h3>
            <div className="metrics-table">
              <div className="table-header">
                <div className="metric-name">Metric</div>
                <div className="metric-naive">Naive</div>
                <div className="metric-compression">Compression</div>
                <div className="metric-difference">Difference</div>
                <div className="metric-winner">Winner</div>
              </div>
              
              {Object.entries(results.comparison.metrics_comparison).map(([metric, comparison]) => (
                <div key={metric} className="table-row">
                  <div className="metric-name">{formatMetricName(metric)}</div>
                  <div className="metric-naive">{comparison.naive.toFixed(3)}</div>
                  <div className="metric-compression">{comparison.compression.toFixed(3)}</div>
                  <div className={`metric-difference ${comparison.difference >= 0 ? 'positive' : 'negative'}`}>
                    {comparison.difference >= 0 ? '+' : ''}{comparison.difference.toFixed(3)}
                  </div>
                  <div className={`metric-winner winner-${comparison.winner}`}>
                    {comparison.winner === 'tie' ? 'Tie' : 
                     comparison.winner === 'compression' ? 'Compression' : 'Naive'}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Individual Results */}
          <div className="individual-results">
            <div className="result-card">
              <h4>🔍 Naive Retriever</h4>
              <div className="metrics-grid">
                {Object.entries(results.evaluations.naive.metrics).map(([metric, score]) => (
                  <div key={metric} className="metric-item">
                    <span className="metric-label">{formatMetricName(metric)}</span>
                    <span className="metric-score">{score.toFixed(3)}</span>
                  </div>
                ))}
              </div>
              <p className="samples-count">
                Evaluated: {results.evaluations.naive.samples_evaluated} samples
              </p>
            </div>

            <div className="result-card">
              <h4>🎯 Contextual Compression</h4>
              <div className="metrics-grid">
                {Object.entries(results.evaluations.contextual_compression.metrics).map(([metric, score]) => (
                  <div key={metric} className="metric-item">
                    <span className="metric-label">{formatMetricName(metric)}</span>
                    <span className="metric-score">{score.toFixed(3)}</span>
                  </div>
                ))}
              </div>
              <p className="samples-count">
                Evaluated: {results.evaluations.contextual_compression.samples_evaluated} samples
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Information Section */}
      <div className="info-section">
        <h2>ℹ️ About RAGAS Evaluation</h2>
        <div className="info-content">
          <p>
            This evaluation tests your <strong>complete PRD review pipeline</strong> using RAGAS (Retrieval Augmented Generation Assessment) metrics.
            Unlike simple retrieval testing, this evaluates the entire end-to-end system performance.
          </p>
          
          <div className="approach-comparison">
            <div className="approach">
              <h4>🔍 Naive Pipeline</h4>
              <p>Complete PRD analysis using standard similarity-based document retrieval.</p>
            </div>
            <div className="approach">
              <h4>🎯 Contextual Compression Pipeline</h4>
              <p>Complete PRD analysis with enhanced retrieval using Cohere rerank-v3.5 for improved relevance.</p>
            </div>
          </div>

          <div className="metrics-info">
            <h4>🔄 Full Pipeline Testing Process:</h4>
            <ol>
              <li><strong>Synthetic Question Generation:</strong> Creates test questions from your research data</li>
              <li><strong>Mock PRD Creation:</strong> Converts questions into PRD analysis requests</li>
              <li><strong>Complete Pipeline Execution:</strong> Runs through your entire PRD review agent:
                <ul>
                  <li>Query generation for relevant research</li>
                  <li>Document retrieval (naive vs. contextual compression)</li>
                  <li>LLM analysis and reasoning</li>
                  <li>Structured report generation</li>
                </ul>
              </li>
              <li><strong>End-to-End Evaluation:</strong> Compares pipeline outputs against ground truth</li>
            </ol>
            
            <h4>📊 Evaluated Metrics:</h4>
            <ul>
              <li><strong>Context Precision:</strong> How relevant are the retrieved contexts to the question?</li>
              <li><strong>Context Recall:</strong> How well does the pipeline capture important information?</li>
              <li><strong>Faithfulness:</strong> How faithful is the analysis to the retrieved context?</li>
              <li><strong>Factual Correctness:</strong> How factually correct is the generated analysis?</li>
              <li><strong>Response Relevancy:</strong> How relevant is the analysis to the original question?</li>
            </ul>
            
            <div className="evaluation-note">
              <strong>🎯 Key Advantage:</strong> This evaluation tests your real system performance, including:
              retrieval quality, LLM reasoning, structured output generation, and overall analysis coherence.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RagasEvaluationPage; 