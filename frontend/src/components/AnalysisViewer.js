import React, { useState } from 'react';

function AnalysisViewer() {
  const [groundTruthFile, setGroundTruthFile] = useState(null);
  const [markersFile, setMarkersFile] = useState(null);
  const [uploadStatus, setUploadStatus] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [results, setResults] = useState(null);

  const handleGroundTruthChange = (e) => {
    setGroundTruthFile(e.target.files[0]);
  };

  const handleMarkersChange = (e) => {
    setMarkersFile(e.target.files[0]);
  };

  const uploadAndAnalyze = async () => {
    if (!groundTruthFile || !markersFile) {
      setUploadStatus('Please select both files');
      return;
    }

    const formData = new FormData();
    formData.append('ground_truth', groundTruthFile);
    formData.append('markers', markersFile);

    try {
      setIsAnalyzing(true);
      setUploadStatus('Uploading files and running analysis...');
      setResults(null);

      const response = await fetch('/api/upload-and-analyze', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      
      if (response.ok) {
        setUploadStatus('Analysis completed successfully!');
        setResults(data.results);
      } else {
        setUploadStatus(`Error: ${data.error}`);
      }
    } catch (error) {
      setUploadStatus(`Error: ${error.message}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div style={{ 
      minHeight: '100vh', 
      backgroundColor: '#f5f5f5',
      padding: '20px'
    }}>
      {/* Header */}
      <div style={{ 
        maxWidth: '1200px', 
        margin: '0 auto',
        backgroundColor: 'white',
        borderRadius: '8px',
        padding: '30px',
        marginBottom: '20px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
      }}>
        <h1 style={{ margin: '0 0 20px 0', color: '#333' }}>
          EmotiBit Data Analysis
        </h1>
        
        <div style={{ marginBottom: '20px' }}>
          <label style={{ 
            display: 'block', 
            marginBottom: '8px', 
            fontWeight: 'bold',
            color: '#555'
          }}>
            Ground Truth Data (CSV):
          </label>
          <input 
            type="file" 
            accept=".csv"
            onChange={handleGroundTruthChange}
            style={{ marginBottom: '5px' }}
          />
          {groundTruthFile && (
            <div style={{ color: '#4CAF50', fontSize: '14px' }}>
              ✓ {groundTruthFile.name}
            </div>
          )}
        </div>

        <div style={{ marginBottom: '20px' }}>
          <label style={{ 
            display: 'block', 
            marginBottom: '8px', 
            fontWeight: 'bold',
            color: '#555'
          }}>
            Event Markers (CSV):
          </label>
          <input 
            type="file" 
            accept=".csv"
            onChange={handleMarkersChange}
            style={{ marginBottom: '5px' }}
          />
          {markersFile && (
            <div style={{ color: '#4CAF50', fontSize: '14px' }}>
              ✓ {markersFile.name}
            </div>
          )}
        </div>

        <button 
          onClick={uploadAndAnalyze}
          disabled={isAnalyzing}
          style={{
            padding: '12px 30px',
            backgroundColor: isAnalyzing ? '#ccc' : '#2196F3',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: isAnalyzing ? 'not-allowed' : 'pointer',
            fontSize: '16px',
            fontWeight: 'bold'
          }}
        >
          {isAnalyzing ? '⏳ Analyzing...' : '🚀 Upload & Analyze'}
        </button>

        {uploadStatus && (
          <div style={{ 
            marginTop: '15px', 
            padding: '12px', 
            backgroundColor: uploadStatus.includes('Error') ? '#ffebee' : '#e8f5e9',
            color: uploadStatus.includes('Error') ? '#c62828' : '#2e7d32',
            borderRadius: '4px',
            fontSize: '14px'
          }}>
            {uploadStatus}
          </div>
        )}
      </div>

      {/* Results Display */}
      {results && (
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
          
          {/* Ground Truth Data */}
          <div style={{ 
            backgroundColor: 'white',
            borderRadius: '8px',
            padding: '25px',
            marginBottom: '20px',
            boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
          }}>
            <h2 style={{ marginTop: 0, color: '#333' }}>Ground Truth Data</h2>
            <p style={{ color: '#666' }}>
              <strong>Shape:</strong> {results.ground_truth.shape[0]} rows × {results.ground_truth.shape[1]} columns
            </p>
            
            {results.ground_truth.stats && (
              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                gap: '15px',
                marginBottom: '20px'
              }}>
                <div style={{ padding: '15px', backgroundColor: '#e3f2fd', borderRadius: '4px' }}>
                  <div style={{ fontSize: '12px', color: '#666' }}>Mean</div>
                  <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#1976d2' }}>
                    {results.ground_truth.stats.mean.toFixed(2)}
                  </div>
                </div>
                <div style={{ padding: '15px', backgroundColor: '#e8f5e9', borderRadius: '4px' }}>
                  <div style={{ fontSize: '12px', color: '#666' }}>Std Dev</div>
                  <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#388e3c' }}>
                    {results.ground_truth.stats.std.toFixed(2)}
                  </div>
                </div>
                <div style={{ padding: '15px', backgroundColor: '#fff3e0', borderRadius: '4px' }}>
                  <div style={{ fontSize: '12px', color: '#666' }}>Min</div>
                  <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#f57c00' }}>
                    {results.ground_truth.stats.min.toFixed(2)}
                  </div>
                </div>
                <div style={{ padding: '15px', backgroundColor: '#fce4ec', borderRadius: '4px' }}>
                  <div style={{ fontSize: '12px', color: '#666' }}>Max</div>
                  <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#c2185b' }}>
                    {results.ground_truth.stats.max.toFixed(2)}
                  </div>
                </div>
              </div>
            )}

            <h3 style={{ color: '#555' }}>First 10 Rows</h3>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ 
                width: '100%', 
                borderCollapse: 'collapse',
                fontSize: '13px'
              }}>
                <thead>
                  <tr style={{ backgroundColor: '#f5f5f5' }}>
                    {results.ground_truth.columns.map((col, idx) => (
                      <th key={idx} style={{ 
                        padding: '10px', 
                        textAlign: 'left',
                        borderBottom: '2px solid #ddd',
                        fontWeight: 'bold'
                      }}>
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {results.ground_truth.head.map((row, idx) => (
                    <tr key={idx} style={{ 
                      borderBottom: '1px solid #eee',
                      backgroundColor: idx % 2 === 0 ? 'white' : '#fafafa'
                    }}>
                      {results.ground_truth.columns.map((col, colIdx) => (
                        <td key={colIdx} style={{ padding: '8px' }}>
                          {typeof row[col] === 'number' ? row[col].toFixed(3) : row[col]}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Markers Data */}
          <div style={{ 
            backgroundColor: 'white',
            borderRadius: '8px',
            padding: '25px',
            marginBottom: '20px',
            boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
          }}>
            <h2 style={{ marginTop: 0, color: '#333' }}>Event Markers</h2>
            <p style={{ color: '#666' }}>
              <strong>Shape:</strong> {results.markers.shape[0]} rows × {results.markers.shape[1]} columns
            </p>

            {results.markers.conditions && (
              <div style={{ marginBottom: '20px' }}>
                <h3 style={{ color: '#555' }}>Conditions</h3>
                <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                  {Object.entries(results.markers.conditions).map(([condition, count]) => (
                    <div key={condition} style={{
                      padding: '8px 16px',
                      backgroundColor: '#e3f2fd',
                      borderRadius: '20px',
                      fontSize: '14px'
                    }}>
                      <strong>{condition}:</strong> {count}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <h3 style={{ color: '#555' }}>First 10 Rows</h3>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ 
                width: '100%', 
                borderCollapse: 'collapse',
                fontSize: '13px'
              }}>
                <thead>
                  <tr style={{ backgroundColor: '#f5f5f5' }}>
                    {results.markers.columns.map((col, idx) => (
                      <th key={idx} style={{ 
                        padding: '10px', 
                        textAlign: 'left',
                        borderBottom: '2px solid #ddd',
                        fontWeight: 'bold'
                      }}>
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {results.markers.head.map((row, idx) => (
                    <tr key={idx} style={{ 
                      borderBottom: '1px solid #eee',
                      backgroundColor: idx % 2 === 0 ? 'white' : '#fafafa'
                    }}>
                      {results.markers.columns.map((col, colIdx) => (
                        <td key={colIdx} style={{ padding: '8px' }}>
                          {row[col]}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Matplotlib Plots */}
          {results.plots && results.plots.length > 0 && (
            <div style={{ 
              backgroundColor: 'white',
              borderRadius: '8px',
              padding: '25px',
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
            }}>
              <h2 style={{ marginTop: 0, color: '#333' }}>Visualizations</h2>
              {results.plots.map((plot, idx) => (
                <div key={idx} style={{ marginBottom: '30px' }}>
                  <h3 style={{ color: '#555', marginBottom: '10px' }}>{plot.name}</h3>
                  <img 
                    src={plot.url} 
                    alt={plot.name}
                    style={{ 
                      width: '100%', 
                      height: 'auto',
                      borderRadius: '4px',
                      border: '1px solid #eee'
                    }}
                  />
                </div>
              ))}
            </div>
          )}

        </div>
      )}
    </div>
  );
}

export default AnalysisViewer;