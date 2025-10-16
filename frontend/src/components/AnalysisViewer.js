import React, { useState } from 'react';
import './AnalysisViewer.css';

function AnalysisViewer() {
  const [selectedFolder, setSelectedFolder] = useState(null);
  const [fileStructure, setFileStructure] = useState(null);
  const [availableMetrics, setAvailableMetrics] = useState([]);
  const [availableEventMarkers, setAvailableEventMarkers] = useState([]);
  const [availableConditions, setAvailableConditions] = useState([]);
  const [selectedMetrics, setSelectedMetrics] = useState({});
  const [uploadStatus, setUploadStatus] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [results, setResults] = useState(null);
  // const [isTesting, setIsTesting] = useState(false);
  // const [testResults, setTestResults] = useState(null);

  // Analysis Configuration State
  const [comparisonGroups, setComparisonGroups] = useState([
    {
      id: 1,
      label: 'Group 1',
      eventMarker: '',
      conditionMarker: '',
      timeWindowType: 'full',
      customStart: -5,
      customEnd: 30
    }
  ]);
  const [nextGroupId, setNextGroupId] = useState(2);

  const addComparisonGroup = () => {
    const newGroup = {
      id: nextGroupId,
      label: `Group ${nextGroupId}`,
      eventMarker: '',
      conditionMarker: '',
      timeWindowType: 'full',
      customStart: -5,
      customEnd: 30
    };
    setComparisonGroups([...comparisonGroups, newGroup]);
    setNextGroupId(nextGroupId + 1);
  };

  const removeComparisonGroup = (id) => {
    if (comparisonGroups.length <= 1) {
      alert('You must have at least one comparison group');
      return;
    }
    setComparisonGroups(comparisonGroups.filter(group => group.id !== id));
  };

  const updateComparisonGroup = (id, field, value) => {
    setComparisonGroups(comparisonGroups.map(group => 
      group.id === id ? { ...group, [field]: value } : group
    ));
  };

  const handleFolderSelect = async (e) => {
    const files = Array.from(e.target.files);
    
    if (files.length === 0) {
      setUploadStatus('No folder selected');
      return;
    }

    const folderName = files[0].webkitRelativePath.split('/')[0];
    setSelectedFolder(folderName);

    const structure = {
      emotibitFiles: [],
      respirationFiles: [],
      serFile: null,
      eventMarkersFile: null,
      allFiles: files
    };

    files.forEach(file => {
      const path = file.webkitRelativePath;
      const fileName = file.name.toLowerCase();
      const pathDepth = path.split('/').length;

      if (path.includes('emotibit_data/') && fileName.endsWith('.csv')) {
        structure.emotibitFiles.push({
          name: file.name,
          path: path,
          file: file
        });
      } else if (path.includes('respiration_data/') && fileName.endsWith('.csv')) {
        structure.respirationFiles.push({
          name: file.name,
          path: path,
          file: file
        });
      } else if (pathDepth === 2 && fileName.endsWith('_event_markers.csv')) {
        structure.eventMarkersFile = {
          name: file.name,
          path: path,
          file: file
        };
      } else if (fileName.includes('ser') || fileName.includes('transcription')) {
        structure.serFile = {
          name: file.name,
          path: path,
          file: file
        };
      }
    });

    setFileStructure(structure);
    setUploadStatus(`Folder "${folderName}" selected with ${files.length} files`);

    await scanFolderData(structure);
  };

  const scanFolderData = async (structure) => {
    if (!structure.emotibitFiles || structure.emotibitFiles.length === 0) {
      setUploadStatus('No EmotiBit files found');
      return;
    }

    setIsScanning(true);
    setUploadStatus('Scanning folder data...');

    const formData = new FormData();
    
    const emotibitFileList = structure.emotibitFiles.map(f => f.name);
    formData.append('emotibit_filenames', JSON.stringify(emotibitFileList));

    if (structure.eventMarkersFile) {
      formData.append('event_markers_file', structure.eventMarkersFile.file);
    }

    try {
      const response = await fetch('/api/scan-folder-data', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      
      if (response.ok) {
        setAvailableMetrics(data.metrics);
        setAvailableEventMarkers(data.event_markers || []);
        setAvailableConditions(data.conditions || []);
        
        const initialSelection = {};
        data.metrics.forEach(metric => {
          initialSelection[metric] = false;
        });
        setSelectedMetrics(initialSelection);
        
        const eventMarkersMsg = data.event_markers && data.event_markers.length > 0 
          ? `, ${data.event_markers.length} event markers` 
          : '';
        const conditionsMsg = data.conditions && data.conditions.length > 0
          ? `, ${data.conditions.length} conditions`
          : '';
        setUploadStatus(`Found ${data.metrics.length} metrics${eventMarkersMsg}${conditionsMsg}`);
      } else {
        setUploadStatus(`Error scanning folder: ${data.error}`);
      }
    } catch (error) {
      setUploadStatus(`Error: ${error.message}`);
    } finally {
      setIsScanning(false);
    }
  };

  const handleMetricToggle = (metric) => {
    setSelectedMetrics(prev => ({
      ...prev,
      [metric]: !prev[metric]
    }));
  };

  const handleSelectAll = () => {
    const allSelected = {};
    availableMetrics.forEach(metric => {
      allSelected[metric] = true;
    });
    setSelectedMetrics(allSelected);
  };

  const handleDeselectAll = () => {
    const noneSelected = {};
    availableMetrics.forEach(metric => {
      noneSelected[metric] = false;
    });
    setSelectedMetrics(noneSelected);
  };

  const uploadAndAnalyze = async () => {
    if (!fileStructure || !fileStructure.allFiles) {
      setUploadStatus('Please select a subject folder');
      return;
    }

    if (comparisonGroups.length < 1) {
      setUploadStatus('Please add at least 1 comparison group');
      return;
    }

    const missingMarkers = comparisonGroups.filter(g => !g.eventMarker);
    if (missingMarkers.length > 0) {
      setUploadStatus('Please select event markers for all comparison groups');
      return;
    }

    const selectedMetricsList = Object.keys(selectedMetrics).filter(m => selectedMetrics[m]);
    if (selectedMetricsList.length === 0) {
      setUploadStatus('Please select at least one biometric metric');
      return;
    }

    const formData = new FormData();

    const filesToUpload = [];
    const pathsToUpload = [];
    
    if (fileStructure.eventMarkersFile) {
      filesToUpload.push(fileStructure.eventMarkersFile.file);
      pathsToUpload.push(fileStructure.eventMarkersFile.path);
    }
    
    selectedMetricsList.forEach(metric => {
      const metricFile = fileStructure.emotibitFiles.find(f => 
        f.name.includes(`_${metric}.csv`)
      );
      if (metricFile) {
        filesToUpload.push(metricFile.file);
        pathsToUpload.push(metricFile.path);
      }
    });
    
    console.log(`Uploading ${filesToUpload.length} files for analysis:`, pathsToUpload.map(p => p.split('/').pop()));
    
    filesToUpload.forEach((file, index) => {
      formData.append('files', file);
      formData.append('paths', pathsToUpload[index]);
    });

    formData.append('folder_name', selectedFolder);
    formData.append('selected_metrics', JSON.stringify(selectedMetricsList));
    formData.append('comparison_groups', JSON.stringify(comparisonGroups));

    try {
      setIsAnalyzing(true);
      setUploadStatus('Uploading folder and running analysis...');
      setResults(null);

      const response = await fetch('/api/upload-folder-and-analyze', {
        method: 'POST',
        body: formData,
      });

      const responseText = await response.text();
      console.log('Raw response:', responseText);
      
      let data;
      try {
        data = JSON.parse(responseText);
      } catch (parseError) {
        console.error('JSON parse error:', parseError);
        console.error('Response text:', responseText);
        setUploadStatus(`Error: Invalid JSON response from server. Check console for details.`);
        return;
      }
      
      if (response.ok) {
        setUploadStatus('Analysis completed successfully!');
        setResults(data.results);

        sessionStorage.setItem('analysisResults', JSON.stringify(data.results));

        const resultsWindow = window.open('/results', '_blank');

        if (!resultsWindow) {
          setUploadStatus('Analysis completed! Please allow pop-ups to view results.');
        }

      } else {
        setUploadStatus(`Error: ${data.error}`);
      }
    } catch (error) {
      console.error('Fetch error:', error);
      setUploadStatus(`Error: ${error.message}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const getSelectedCount = () => {
    return Object.values(selectedMetrics).filter(val => val).length;
  };

  // const testTimestampMatching = async () => {
  //   const selectedMetricsList = Object.keys(selectedMetrics).filter(m => selectedMetrics[m]);
    
  //   if (selectedMetricsList.length === 0) {
  //     setUploadStatus('Please select at least one biometric metric to test');
  //     return;
  //   }

  //   if (!fileStructure || !fileStructure.allFiles) {
  //     setUploadStatus('Please select a subject folder first');
  //     return;
  //   }

  //   // Use the first selected metric for testing
  //   const metricToTest = selectedMetricsList[0];

  //   try {
  //     setIsTesting(true);
  //     setUploadStatus(`Testing timestamp matching for ${metricToTest}...`);
  //     setTestResults(null);

  //     const formData = new FormData();
      
  //     // Only upload the files we need for testing
  //     const filesToUpload = [];
  //     const pathsToUpload = [];
      
  //     // Find and add the event markers file
  //     if (fileStructure.eventMarkersFile) {
  //       filesToUpload.push(fileStructure.eventMarkersFile.file);
  //       pathsToUpload.push(fileStructure.eventMarkersFile.path);
  //     }
      
  //     // Find and add the specific metric file
  //     const metricFile = fileStructure.emotibitFiles.find(f => 
  //       f.name.includes(`_${metricToTest}.csv`)
  //     );
      
  //     if (metricFile) {
  //       filesToUpload.push(metricFile.file);
  //       pathsToUpload.push(metricFile.path);
  //     }
      
  //     if (filesToUpload.length !== 2) {
  //       setUploadStatus(`Error: Could not find required files (event markers and ${metricToTest})`);
  //       setIsTesting(false);
  //       return;
  //     }
      
  //     console.log(`Uploading ${filesToUpload.length} files for testing:`, pathsToUpload);
      
  //     // Add only the necessary files
  //     filesToUpload.forEach((file, index) => {
  //       formData.append('files', file);
  //       formData.append('paths', pathsToUpload[index]);
  //     });
      
  //     formData.append('selected_metric', metricToTest);

  //     const response = await fetch('/api/test-timestamp-matching', {
  //       method: 'POST',
  //       body: formData,
  //     });

  //     const data = await response.json();
      
  //     if (response.ok) {
  //       setUploadStatus(`Test completed! Found ${data.total_matches} matches. Check terminal for details.`);
  //       setTestResults(data);
  //     } else {
  //       setUploadStatus(`Error: ${data.error}`);
  //     }
  //   } catch (error) {
  //     setUploadStatus(`Error: ${error.message}`);
  //   } finally {
  //     setIsTesting(false);
  //   }
  // };

  return (
    <div className="container">
      <div className="header-card">
        <h1 className="main-title">Experiment Data Analysis</h1>
        
        <div className="folder-select-section">
          <label className="input-label">
            Select Subject Folder:
          </label>
          <input 
            type="file" 
            webkitdirectory="true"
            directory="true"
            multiple
            onChange={handleFolderSelect}
            className="folder-input"
          />
          {selectedFolder && (
            <div className="folder-selected">
              ✓ Folder: <strong>{selectedFolder}</strong>
            </div>
          )}
        </div>
      </div>

      {fileStructure && (
        <div className="two-column-layout">
          
          {/* LEFT COLUMN */}
          <div className="left-column">
            
            {/* Detected Files */}
            <div className="file-structure">
              <h3 className="structure-title">Detected Files:</h3>
              
              <div className="file-category">
                <strong>EmotiBit Data:</strong>
                <span className="file-count">{fileStructure.emotibitFiles.length} files</span>
              </div>

              <div className="file-category">
                <strong>Respiration Data:</strong>
                <span className="file-count">{fileStructure.respirationFiles.length} files</span>
              </div>

              <div className="file-category">
                <strong>Event Markers:</strong>
                <span className={fileStructure.eventMarkersFile ? "file-found" : "file-missing"}>
                  {fileStructure.eventMarkersFile ? `✓ ${fileStructure.eventMarkersFile.name}` : '✗ Not found'}
                </span>
              </div>

              <div className="file-category">
                <strong>SER/Transcription:</strong>
                <span className={fileStructure.serFile ? "file-found" : "file-missing"}>
                  {fileStructure.serFile ? `✓ ${fileStructure.serFile.name}` : '✗ Not found'}
                </span>
              </div>
            </div>

          </div>

          {/* RIGHT COLUMN */}
          <div className="right-column">
            
            {/* Metrics Selection */}
            {availableMetrics.length > 0 && (
              <div className="metrics-section">
                <div className="metrics-header">
                  <h3 className="structure-title">Available Biometric Metrics ({availableMetrics.length})</h3>
                  <div className="metrics-controls">
                    <button onClick={handleSelectAll} className="metric-control-btn">
                      Select All
                    </button>
                    <button onClick={handleDeselectAll} className="metric-control-btn">
                      Deselect All
                    </button>
                    <span className="selected-count">
                      {getSelectedCount()} selected
                    </span>
                  </div>
                </div>
                
                <div className="metrics-grid">
                  {availableMetrics.map(metric => (
                    <label key={metric} className="metric-checkbox">
                      <input
                        type="checkbox"
                        checked={selectedMetrics[metric] || false}
                        onChange={() => handleMetricToggle(metric)}
                      />
                      <span className="metric-label">{metric}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {/* Analysis Configuration */}
            {availableEventMarkers.length > 0 && (
              <div className="analysis-config-section">
                <h3 className="structure-title">Analysis Configuration</h3>
                
                <div className="comparison-groups-container">
                  {comparisonGroups.map((group, index) => (
                    <div key={group.id} className="comparison-group-card">
                      <div className="card-header">
                        <h4 className="group-title">Comparison Group {index + 1}</h4>
                        {comparisonGroups.length > 1 && (
                          <button 
                            onClick={() => removeComparisonGroup(group.id)}
                            className="remove-group-btn"
                            title="Remove this group"
                          >
                            ✖️
                          </button>
                        )}
                      </div>

                      <div className="group-config">
                        <label className="config-label">Label:</label>
                        <input
                          type="text"
                          className="label-input"
                          value={group.label}
                          onChange={(e) => updateComparisonGroup(group.id, 'label', e.target.value)}
                          placeholder="Enter group name..."
                        />
                      </div>

                      <div className="group-config">
                        <label className="config-label">Event Marker:</label>
                        <select 
                          className="config-select"
                          value={group.eventMarker}
                          onChange={(e) => updateComparisonGroup(group.id, 'eventMarker', e.target.value)}
                        >
                          <option value="">Select event marker...</option>
                          {availableEventMarkers.map(marker => (
                            <option key={marker} value={marker}>{marker}</option>
                          ))}
                        </select>
                      </div>

                      <div className="group-config">
                        <label className="config-label">Condition Marker:</label>
                        <select 
                          className="config-select"
                          value={group.conditionMarker}
                          onChange={(e) => updateComparisonGroup(group.id, 'conditionMarker', e.target.value)}
                        >
                          <option value="">All conditions</option>
                          {availableConditions.map(condition => (
                            <option key={condition} value={condition}>{condition}</option>
                          ))}
                        </select>
                      </div>

                      <div className="group-config">
                        <label className="config-label">Time Window:</label>
                        <div className="radio-group">
                          <label className="radio-label">
                            <input
                              type="radio"
                              checked={group.timeWindowType === 'full'}
                              onChange={() => updateComparisonGroup(group.id, 'timeWindowType', 'full')}
                            />
                            <span>Full event duration</span>
                          </label>
                          <label className="radio-label">
                            <input
                              type="radio"
                              checked={group.timeWindowType === 'custom'}
                              onChange={() => updateComparisonGroup(group.id, 'timeWindowType', 'custom')}
                            />
                            <span>Custom offset</span>
                          </label>
                        </div>
                        
                        {group.timeWindowType === 'custom' && (
                          <div className="custom-time-inputs">
                            <div className="time-input-group">
                              <label>Start:</label>
                              <input
                                type="number"
                                value={group.customStart}
                                onChange={(e) => updateComparisonGroup(group.id, 'customStart', parseFloat(e.target.value))}
                                className="time-input"
                              />
                              <span>seconds</span>
                            </div>
                            <div className="time-input-group">
                              <label>End:</label>
                              <input
                                type="number"
                                value={group.customEnd}
                                onChange={(e) => updateComparisonGroup(group.id, 'customEnd', parseFloat(e.target.value))}
                                className="time-input"
                              />
                              <span>seconds</span>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}

                  <button 
                    onClick={addComparisonGroup}
                    className="add-group-btn"
                  >
                    + Add Comparison Group
                  </button>
                </div>
              </div>
            )}

            {/* Run Analysis Button */}
            <button 
              onClick={uploadAndAnalyze}
              disabled={isAnalyzing || !fileStructure || isScanning}
              className={`analyze-button ${isAnalyzing || !fileStructure || isScanning ? 'disabled' : ''}`}
            >
              {isAnalyzing ? '⏳ Analyzing...' : isScanning ? '🔍 Scanning...' : 'Run Analysis'}
            </button>

            {/* Status Messages */}
            {uploadStatus && (
              <div className={`status-message ${uploadStatus.includes('Error') ? 'error' : 'success'}`}>
                {uploadStatus}
              </div>
            )}

            {/* Results Redirect */}
            {results && (
              <div className="results-redirect-message">
                <div className="redirect-card">
                  <h2 className="redirect-title">✅ Analysis Complete!</h2>
                  <p className="redirect-text">
                    Your analysis results have been opened in a new tab. 
                    If the tab did not open automatically, please check your browser's pop-up settings.
                  </p>
                  <button 
                    onClick={() => {
                      sessionStorage.setItem('analysisResults', JSON.stringify(results));
                      window.open('/results', '_blank');
                    }}
                    className="reopen-results-button"
                  >
                    🔄 Re-open Results Tab
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default AnalysisViewer;