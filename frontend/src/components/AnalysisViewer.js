/**
 * AnalysisViewer Component
 * 
 * This React component provides a user interface for uploading and analyzing experiment data from a subject folder.
 * It supports selecting biometric metrics, configuring analysis comparison groups, and running analysis via backend API endpoints.
 * 
 * @component
 * 
 * @example
 * <AnalysisViewer />
 * 
 * @returns {JSX.Element} The rendered AnalysisViewer UI.
 * 
 * @description
 * - Allows users to select a subject folder containing experiment data files.
 * - Scans the folder for required files (EmotiBit data, respiration data, event markers, SER/transcription).
 * - Displays detected files and available biometric metrics.
 * - Enables selection/deselection of metrics and configuration of comparison groups for analysis.
 * - Supports custom time window configuration for each comparison group.
 * - Handles uploading selected files and analysis configuration to the backend for processing.
 * - Displays status messages and redirects to results upon successful analysis.
 * 
 * @state
 * @property {string|null} selectedFolder - Name of the selected folder.
 * @property {Object|null} fileStructure - Structure containing detected files and their metadata.
 * @property {string[]} availableMetrics - List of available biometric metrics detected in the folder.
 * @property {string[]} availableEventMarkers - List of available event markers.
 * @property {string[]} availableConditions - List of available condition markers.
 * @property {Object} selectedMetrics - Object mapping metric names to boolean selection state.
 * @property {string} uploadStatus - Status message for upload and analysis operations.
 * @property {boolean} isScanning - Indicates if folder scanning is in progress.
 * @property {boolean} isAnalyzing - Indicates if analysis is in progress.
 * @property {Object|null} results - Analysis results returned from the backend.
 * @property {Array<Object>} comparisonGroups - Array of analysis comparison group configurations.
 * @property {number} nextGroupId - Next available ID for a new comparison group.
 * 
 * @functions
 * @function addComparisonGroup - Adds a new comparison group to the configuration.
 * @function removeComparisonGroup - Removes a comparison group by ID.
 * @function updateComparisonGroup - Updates a field in a comparison group.
 * @function handleFolderSelect - Handles folder selection and scans for required files.
 * @function scanFolderData - Sends folder data to backend to detect metrics, event markers, and conditions.
 * @function handleMetricToggle - Toggles selection state for a biometric metric.
 * @function handleSelectAll - Selects all available metrics.
 * @function handleDeselectAll - Deselects all metrics.
 * @function uploadAndAnalyze - Uploads selected files and configuration to backend and runs analysis.
 * @function getSelectedCount - Returns the count of selected metrics.
 * 
 * @api
 * - POST /api/scan-folder-data: Scans folder for metrics, event markers, and conditions.
 * - POST /api/upload-folder-and-analyze: Uploads files and configuration, runs analysis.
 * 
 * @css
 * - Uses styles from 'AnalysisViewer.css'.
 * 
 * @see
 * - Backend API endpoints for scanning and analysis.
 * - Results page at '/results' for viewing analysis output.
 */

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
  const [showWizard, setShowWizard] = useState(true);
  const [currentStep, setCurrentStep] = useState(0);
  // const [isTesting, setIsTesting] = useState(false);
  // const [testResults, setTestResults] = useState(null);

  // Analysis Configuration State
  const [analyzeHRV, setAnalyzeHRV] = useState(false);
  const [comparisonGroups, setComparisonGroups] = useState([
    {
      id: 1,
      label: 'Group 1',
      eventMarker: '',
      conditionMarker: '',
      plotType: 'line',         
      analysisMethod: 'raw',    
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
      plotType: 'line',
      analysisMethod: 'raw',
      timeWindowType: 'full',
      customStart: -5,
      customEnd: 30
    };
    setComparisonGroups([...comparisonGroups, newGroup]);
    setNextGroupId(nextGroupId + 1);
  };

  const removeComparisonGroup = (id) => {
    if (comparisonGroups.length <= 1) {
      alert('You must have at least one Analysis Window');
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

      console.log('Checking file:', fileName);
      if (fileName.includes('_pi.csv')) {
        console.log('Found PPG file!');
        structure.hasPPGFiles = true;
        console.log('hasPPGFiles:', structure.hasPPGFiles);
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
      setUploadStatus('Please add at least 1 Analysis Window');
      return;
    }

    const missingMarkers = comparisonGroups.filter(g => !g.eventMarker);
    if (missingMarkers.length > 0) {
      setUploadStatus('Please select event markers for all Analysis Windows');
      return;
    }

    const selectedMetricsList = Object.keys(selectedMetrics).filter(m => selectedMetrics[m]);
    if (selectedMetricsList.length === 0 && !analyzeHRV) {
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

    if (analyzeHRV) {
      ['PI', 'PR', 'PG'].forEach(ppgType => {
        const ppgFile = fileStructure.emotibitFiles.find(f => 
          f.name.includes(`_${ppgType}.csv`)
        );
        if (ppgFile) {
          filesToUpload.push(ppgFile.file);
          pathsToUpload.push(ppgFile.path);
        }
      });
    }

    console.log(`Uploading ${filesToUpload.length} files for analysis:`, pathsToUpload.map(p => p.split('/').pop()));
    
    filesToUpload.forEach((file, index) => {
      formData.append('files', file);
      formData.append('paths', pathsToUpload[index]);
    });

    formData.append('folder_name', selectedFolder);
    formData.append('selected_metrics', JSON.stringify(selectedMetricsList));
    formData.append('comparison_groups', JSON.stringify(comparisonGroups));
    formData.append('analyze_hrv', JSON.stringify(analyzeHRV));

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

  const plotTypes = [
    { id: 'lineplot', label: 'Line Plot' },
    { id: 'boxplot', label: 'Box Plot' },
    { id: 'histogram', label: 'Histogram' },
    { id: 'poincare', label: 'Poincaré Plot' },
    { id: 'scatter', label: 'Scatter Plot' },
    { id: 'barchart', label: 'Bar Chart' }
  ];

  const methodTypes = [
    { id: 'raw_data', label: 'Raw Data Analysis' },
    { id: 'event_locked', label: 'Average Signal Around Event' },
    { id: 'peak_detection', label: 'Identify Peaks' },
    { id: 'rolling_average', label: 'Time Domain Analysis' },
    { id: 'baseline_correction', label: 'Normalize to Pre-Event Baseline' }
  ]

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
  const wizardSteps = [
    {
      title: "Select Subject Folder",
      description: "Start by clicking the 'Browse' button to select a subject folder containing your biometric data files.",
      details: "The system will scan for required files including CSV data files, event markers, and experimental conditions."
    },
    {
      title: "Review File Structure",
      description: "After selecting a folder, verify that all required files were found.",
      details: "Check the file structure panel to ensure CSV files, event markers (events.txt), and conditions (conditions.txt) are present. Missing files will be highlighted in red."
    },
    {
      title: "Select Metrics to Analyze",
      description: "Choose which biometric metrics you want to analyze from the available options.",
      details: "Use 'Select All' or 'Deselect All' for quick selection, or individually check the metrics you need. The selected count will be displayed."
    },
    {
      title: "Configure Analysis Windows",
      description: "Set up baseline and analysis time windows for your data.",
      details: "Choose from preset options (Baseline/Post-Injection) or define custom time ranges. Configure both baseline and analysis windows according to your experimental protocol."
    },
    {
      title: "Set Up Comparison Groups",
      description: "Define comparison groups for statistical analysis.",
      details: "Add groups by clicking the '+ Add Comparison Group' button. For each group, provide a label and select the conditions to include. You can add multiple groups for comprehensive comparisons."
    },
    {
      title: "Run Analysis",
      description: "Click 'Run Analysis' to process your data and generate results.",
      details: "The system will perform statistical analysis and generate visualizations. Results will open in a new tab automatically."
    }
  ];

  const handleNextStep = () => {
    if (currentStep < wizardSteps.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handlePrevStep = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleBreadcrumbClick = (stepIndex) => {
    setCurrentStep(stepIndex);
  };

  return (
    <div className="container">
      <div className="header-card">
        <h1 className="main-title">Experiment Data Analysis</h1>
        
        <div className="folder-select-section">
          <label className="input-label">
           
          </label>
          <input 
            type="file" 
            id="folder-input-hidden"
            className="folder-input-hidden"
            webkitdirectory="true"
            directory="true"
            multiple
            onChange={handleFolderSelect}
          />
          <label htmlFor="folder-input-hidden" className="browse-button">
            Browse For Subject Folder
          </label>
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
            {console.log('availableMetrics.length:', availableMetrics.length)}
            {console.log('Inside metrics-grid, hasPPGFiles:', fileStructure.hasPPGFiles)}
            {console.log('fileStructure.hasPPGFiles:', fileStructure?.hasPPGFiles)}
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
                  {fileStructure.hasPPGFiles && (
                    <>
                      {console.log('RENDERING HRV CHECKBOX NOW')}
                      <label className="metric-checkbox" >
                        <input
                          type="checkbox"
                          checked={analyzeHRV}
                          onChange={(e) => setAnalyzeHRV(e.target.checked)}
                        />
                        <span className="metric-label">HRV</span>
                      </label>
                    </>
                  )}
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

            {/* Plot Types Selection
            {availableMetrics.length > 0 && (
              <div className="metrics-section">
                <div className="metrics-header">
                  <h3 className="structure-title">Select Plot Types</h3>
                  <div className="metrics-controls">
                    <span className="selected-count">
                      Choose visualization methods for your analysis
                    </span>
                  </div>
                </div>
                
                <div className="metrics-grid">
                  {plotTypes.map(plotType => (
                    <label key={plotType.id} className="metric-checkbox">
                      <input
                        type="checkbox"
                        checked={selectedPlotTypes[plotType.id] || false}
                        onChange={() => {
                          setSelectedPlotTypes(prev => ({
                            ...prev,
                            [plotType.id]: !prev[plotType.id]
                          }));
                        }}
                      />
                      <span className="metric-label">{plotType.label}</span>
                    </label>
                  ))}
                </div>
              </div>
            )} */}

            {/* Analysis Configuration */}
            {availableEventMarkers.length > 0 && (
              <div className="analysis-config-section">
                <h3 className="structure-title">Analysis Configuration</h3>
                
                <div className="comparison-groups-container">
                  {comparisonGroups.map((group, index) => (
                    <div key={group.id} className="comparison-group-card">
                      <div className="card-header">
                        <h4 className="group-title">Analysis Window {index + 1}</h4>
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
                      
                      {/* Available metric dropdown */}
                      <div className="window-config">
                        <label className="config-label">Biometric Tag</label>
                        <select
                          className="config-select"
                          value={window.metric}
                          onChange={(e) => updateComparisonGroup(window.id, 'metric', e.target.value)}
                        >
                          <option value="">Select Metric</option>
                          {availableMetrics.map(metric => (
                            <option key={metric} value={metric}>
                              {metric}
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* Plot Type Dropdown */}
                      <div className="window-config">
                        <label className="config-label">Plot Type</label>
                        <select
                          className="config-select"
                          value={window.plotType}
                          onChange={(e) => updateComparisonGroup(window.id, 'plotType', e.target.value)}
                        >
                          {plotTypes.map((type) => (
                            <option key={type.value} value={type.value}>
                              {type.label}
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* Analysis Method Dropdown */}
                      <div className="window-config">
                        <label className="config-label">Analysis Method</label>
                        <select
                          className="config-select"
                          value={group.analysisMethod}
                          onChange={(e) => updateComparisonGroup(group.id, 'analysisMethod', e.target.value)}
                        >
                          {methodTypes.map((method) => (
                            <option key={method.value} value={method.value}>
                              {method.label}
                            </option>
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
                    + Analysis Window
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
      {/* Processing Overlay */}
      {isAnalyzing && (
        <div className="processing-overlay">
          <div className="spinner-container">
            <div className="spinner"></div>
            <p className="processing-text">Analyzing Your Data</p>
            <p className="processing-subtext">
              This may take a few moments...<br />
              Please do not close this window
            </p>
          </div>
        </div>
      )}

      {/* Instruction Wizard */}
      {showWizard ? (
        <div className="instruction-wizard">
          <div className="wizard-header">
            <h3 className="wizard-title">User Guide</h3>
            <button 
              className="wizard-close-btn"
              onClick={() => setShowWizard(false)}
              aria-label="Close wizard"
            >
              ×
            </button>
          </div>
          
          <div className="wizard-breadcrumbs">
            {wizardSteps.map((step, index) => (
              <div
                key={index}
                className={`breadcrumb-item ${currentStep === index ? 'active' : ''}`}
                onClick={() => handleBreadcrumbClick(index)}
              >
                Step {index + 1}
              </div>
            ))}
          </div>
          
          <div className="wizard-content">
            <div className="wizard-step-number">{currentStep + 1}</div>
            <h4 className="wizard-step-title">{wizardSteps[currentStep].title}</h4>
            <p className="wizard-step-description">
              {wizardSteps[currentStep].description}
            </p>
            <div className="wizard-highlight">
              <strong>Details:</strong> {wizardSteps[currentStep].details}
            </div>
          </div>
          
          <div className="wizard-footer">
            <button
              className="wizard-nav-btn prev"
              onClick={handlePrevStep}
              disabled={currentStep === 0}
            >
              ← Back
            </button>
            
            <div className="wizard-progress">
              Step {currentStep + 1} of {wizardSteps.length}
            </div>
            
            <button
              className="wizard-nav-btn next"
              onClick={handleNextStep}
              disabled={currentStep === wizardSteps.length - 1}
            >
              Next →
            </button>
          </div>
        </div>
      ) : (
        <button
          className="wizard-toggle-btn"
          onClick={() => setShowWizard(true)}
          aria-label="Open instruction wizard"
        />
      )}
    </div>
  );
}

export default AnalysisViewer;