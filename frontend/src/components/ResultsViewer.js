/**
 * ResultsViewer component displays the results of an analysis, including metrics, visualizations, and event markers.
 * 
 * Features:
 * - Loads analysis results from sessionStorage on mount.
 * - Displays analysis metrics, plots, and event markers summary.
 * - Allows users to save all figures (plots) as image files.
 * - Allows users to export the full results as a JSON file.
 * - Handles loading state and error cases for saving figures.
 * 
 * State:
 * @typedef {Object} Results
 * @property {Object} analysis - Analysis metrics grouped by metric and group.
 * @property {Array<Object>} plots - Array of plot objects with { name, url, filename }.
 * @property {Object} markers - Event markers summary with shape and conditions.
 * @property {string|number} timestamp - Timestamp of analysis generation.
 * 
 * @component
 * @returns {JSX.Element} The rendered ResultsViewer component.
 * 
 * @example
 * // Usage in a parent component
 * <ResultsViewer />
 */

import React, { useEffect, useState } from 'react';
import './ResultsViewer.css';

function ResultsViewer() {
  const [results, setResults] = useState(null);
  const [timestamp, setTimestamp] = useState('');
  const [isSavingFigures, setIsSavingFigures] = useState(false);

  useEffect(() => {
    const storedResults = sessionStorage.getItem('analysisResults');
    if (storedResults) {
      try {
        const parsed = JSON.parse(storedResults);
        setResults(parsed);
        setTimestamp(new Date(parsed.timestamp).toLocaleString());
      } catch (error) {
        console.error('Failed to parse analysis results:', error);
        sessionStorage.removeItem('analysisResults');
      }
    }
  }, []);

  const handleSaveFigures = async () => {
    if (!results || !results.plots || results.plots.length === 0) {
      alert('No figures available to save');
      return;
    }

    setIsSavingFigures(true);

    try {
      for (let i = 0; i < results.plots.length; i++) {
        const plot = results.plots[i];
        
        if (i > 0) {
          await new Promise(resolve => setTimeout(resolve, 300)); // prevent blocking
        }

        try {
          const response = await fetch(plot.url);
          const blob = await response.blob();
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = plot.filename;
          link.style.display = 'none';
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          URL.revokeObjectURL(url);
        } catch (error) {
          console.error(`Failed to download ${plot.filename}:`, error);
        }
      }

      alert(`Successfully initiated download of ${results.plots.length} figure(s). Check your Downloads folder.`);

    } catch (error) {
      console.error('Error saving figures:', error);
      alert('Failed to save figures. Please try again.');
    } finally {
      setIsSavingFigures(false);
    }
  };

  const handleExportJSON = () => {
    const dataStr = JSON.stringify(results, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `analysis_results_${Date.now()}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (!results) {
    return (
      <div className="container">
        <div className="header-card">
          <h2>No results available</h2>
          <p>Please run an analysis first.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="results-viewer-container">
      <div className="results-header-section no-print">
        <h1 className="results-page-title">Analysis Results</h1>
        <div className="results-action-bar">
          <button 
            onClick={handleSaveFigures} 
            className="results-btn results-save-btn"
            disabled={isSavingFigures || !results.plots || results.plots.length === 0}
          >
            {isSavingFigures ? '💾 Saving...' : '📊 Save Figures'}
          </button>
          <button onClick={handleExportJSON} className="results-btn results-export-btn">
            💾 Export JSON
          </button>
          <span className="results-timestamp">Generated: {timestamp}</span>
        </div>
      </div>

      <div className="results-container">
        {/* HRV Analysis Results */}
        {results.hrv && (
          <div className="result-card hrv-card">
            <h2 className="card-title">HRV Analysis</h2>
            
            <div className="hrv-summary">
              <h3 className="section-title">Summary Statistics</h3>
              <div className="stats-grid">
                <div className="stat-card">
                  <div className="stat-label">Peaks Detected</div>
                  <div className="stat-value">{results.hrv.num_peaks}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Duration</div>
                  <div className="stat-value">{results.hrv.duration_minutes.toFixed(2)}</div>
                  <div className="stat-detail">minutes</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Average HR</div>
                  <div className="stat-value">{results.hrv.average_hr_bpm.toFixed(2)}</div>
                  <div className="stat-detail">bpm</div>
                </div>
              </div>
            </div>

            {results.hrv.indices && Object.keys(results.hrv.indices).length > 0 && (
              <div className="hrv-indices">
                <h3 className="section-title">HRV Indices</h3>
                <div className="indices-grid">
                  {Object.entries(results.hrv.indices).map(([key, value]) => (
                    <div key={key} className="index-item">
                      <span className="index-name">{key}:</span>
                      <span className="index-value">
                        {value !== null && value !== undefined 
                          ? typeof value === 'number' ? value.toFixed(4) : value
                          : 'N/A'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {results.plots?.filter(p => p.filename.startsWith('HRV_')).map((plot, idx) => (
              <div key={idx} className="plot-container">
                <h4 className="plot-title">{plot.name}</h4>
                <img src={plot.url} alt={plot.name} className="plot-image" />
              </div>
            ))}
          </div>
        )}
        {/* Analysis Results */}
        {results.analysis && Object.keys(results.analysis).length > 0 && (
        <div className="result-card">
            <h2 className="card-title">Analysis Results</h2>
            {Object.entries(results.analysis).map(([metric, groupData]) => {
              // Check if this is a flat structure (Respiratory/External) or nested (EmotiBit)
              const isFlat = groupData.hasOwnProperty('mean') && groupData.hasOwnProperty('std');
              
              if (isFlat) {
                // Flat structure: key is "Respiratory: Subject - RR - baseline", value is stats
                return (
                  <div key={metric} className="metric-analysis">
                    <h3 className="section-title">{metric}</h3>
                    <div className="stats-grid">
                      <div className="stat-card">
                        <div className="stat-value">{groupData.mean.toFixed(2)}</div>
                        <div className="stat-detail">
                          ±{groupData.std.toFixed(2)} | n={groupData.count}
                        </div>
                        <div className="stat-range">
                          Range: {groupData.min.toFixed(2)} - {groupData.max.toFixed(2)}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              } else {
                // Nested structure: standard EmotiBit format
                return (
                  <div key={metric} className="metric-analysis">
                    <h3 className="section-title">{metric}</h3>
                    <div className="stats-grid">
                      {Object.entries(groupData).map(([groupLabel, stats]) => (
                        <div key={groupLabel} className="stat-card">
                          <div className="stat-label">{groupLabel}</div>
                          <div className="stat-value">{stats.mean.toFixed(2)}</div>
                          <div className="stat-detail">
                            ±{stats.std.toFixed(2)} | n={stats.count}
                          </div>
                          <div className="stat-range">
                            Range: {stats.min.toFixed(2)} - {stats.max.toFixed(2)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              }
            })}
        </div>
        )}

        {/* Visualizations */}
        {results.plots?.filter(p => !p.filename.startsWith('HRV_')).length > 0 && (
          <div className="result-card">
            <h2 className="card-title">Visualizations</h2>
            {results.plots.filter(p => !p.filename.startsWith('HRV_')).map((plot, idx) => (
              <div key={idx} className="plot-container">
                <h3 className="plot-title">{plot.name}</h3>
                <img 
                  src={plot.url} 
                  alt={plot.name}
                  className="plot-image"
                />
              </div>
            ))}
          </div>
        )}

        {/* Event Markers Summary */}
        {results.markers && results.markers.shape && (
          <div className="result-card">
            <h2 className="card-title">Event Markers Summary</h2>
            <p className="data-info">
              <strong>Total Events:</strong> {results.markers.shape[0]}
            </p>
            {results.markers.conditions && (
              <div className="conditions-section">
                <h3 className="section-title">Conditions</h3>
                <div className="conditions-container">
                  {Object.entries(results.markers.conditions).map(([condition, count]) => (
                    <div key={condition} className="condition-badge">
                      <strong>{condition}:</strong> {count}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}

export default ResultsViewer;