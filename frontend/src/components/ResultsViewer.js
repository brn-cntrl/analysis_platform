import React, { useEffect, useState } from 'react';
import './ResultsViewer.css';

function ResultsViewer() {
  const [results, setResults] = useState(null);
  const [timestamp, setTimestamp] = useState('');
  const [isSavingFigures, setIsSavingFigures] = useState(false);

  useEffect(() => {
    const storedResults = sessionStorage.getItem('analysisResults');
    if (storedResults) {
      const parsed = JSON.parse(storedResults);
      setResults(parsed);
      setTimestamp(new Date(parsed.timestamp).toLocaleString());
    }
  }, []);

  const handleSaveFigures = async () => {
    if (!results || !results.plots || results.plots.length === 0) {
      alert('No figures available to save');
      return;
    }

    setIsSavingFigures(true);

    try {
      // Download each figure individually
      for (let i = 0; i < results.plots.length; i++) {
        const plot = results.plots[i];
        
        // Small delay between downloads to prevent browser from blocking
        if (i > 0) {
          await new Promise(resolve => setTimeout(resolve, 300));
        }

        try {
          const response = await fetch(plot.url);
          const blob = await response.blob();
          
          // Create download link
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
        
        {/* Analysis Results */}
        {results.analysis && Object.keys(results.analysis).length > 0 && (
        <div className="result-card">
            <h2 className="card-title">Analysis Results</h2>
            {Object.entries(results.analysis).map(([metric, groupData]) => (
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
            ))}
        </div>
        )}

        {/* Visualizations */}
        {results.plots && results.plots.length > 0 && (
          <div className="result-card">
            <h2 className="card-title">Visualizations</h2>
            {results.plots.map((plot, idx) => (
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