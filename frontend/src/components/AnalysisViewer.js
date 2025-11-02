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
  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('studentId'));
  const [loginStudentId, setLoginStudentId] = useState('');
  const [loginError, setLoginError] = useState('');
  const [showRegister, setShowRegister] = useState(false);
  const [registerName, setRegisterName] = useState('');
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerStudentId, setRegisterStudentId] = useState('');
  const [availableSubjects, setAvailableSubjects] = useState([]);
  const [selectedSubjects, setSelectedSubjects] = useState({});
  const [isBatchMode, setIsBatchMode] = useState(false);
  const [subjectAvailability, setSubjectAvailability] = useState({});
  const [batchStatusMessage, setBatchStatusMessage] = useState('');
  
  // Wizard state
  const [showConfigWizard, setShowConfigWizard] = useState(false);
  const [wizardStep, setWizardStep] = useState(0);
  const [analysisType, setAnalysisType] = useState('inter');
  const [tagMode, setTagMode] = useState('union');
  const [eventMode, setEventMode] = useState('union');
  const [conditionMode, setConditionMode] = useState('union');
  const [selectedEvents, setSelectedEvents] = useState([{ event: '', condition: 'all' }]);
  const [selectedAnalysisMethod, setSelectedAnalysisMethod] = useState('raw');
  const [selectedPlotType, setSelectedPlotType] = useState('lineplot');
  const [configIssues, setConfigIssues] = useState([]);
  const [lastAnalysisStatus, setLastAnalysisStatus] = useState(null);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoginError('');
    
    const trimmedId = loginStudentId.trim().toLowerCase();
    if (!trimmedId) {
      setLoginError('Please enter your student ID');
      return;
    }

    try {
      const response = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ student_id: trimmedId })
      });

      const data = await response.json();

      if (response.ok) {
        localStorage.setItem('studentId', trimmedId);
        localStorage.setItem('studentName', data.name);
        setIsLoggedIn(true);
      } else {
        setLoginError(data.error || 'Student ID not found');
      }
    } catch (error) {
      setLoginError('Unable to connect to server');
    }
  };

  const handleLogout = () => {
    localStorage.clear();
    setIsLoggedIn(false);
    setLoginStudentId('');
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
      serFiles: [],
      eventMarkersFiles: [],
      allFiles: files,
      hasPPGFiles: false
    };

    files.forEach(file => {
      const path = file.webkitRelativePath;
      const fileName = file.name.toLowerCase();

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
      } else if (fileName.endsWith('_event_markers.csv')) {
        structure.eventMarkersFiles.push({
          name: file.name,
          path: path,
          file: file
        });
      } else if (fileName.includes('ser') || fileName.includes('transcription')) {
        structure.serFiles.push({
          name: file.name,
          path: path,
          file: file
        });
      }
    });

    structure.hasPPGFiles = structure.emotibitFiles.some(f => 
      f.name.includes('_PI.csv') || f.name.includes('_PR.csv') || f.name.includes('_PG.csv')
    );

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
    
    const emotibitFileList = structure.emotibitFiles.map(f => f.path);
    formData.append('emotibit_filenames', JSON.stringify(emotibitFileList));

    const allPaths = structure.allFiles.map(f => f.webkitRelativePath);
    const subjectFolders = new Set();
    allPaths.forEach(path => {
      const parts = path.split('/');
      if (parts.length >= 3) {
        subjectFolders.add(parts[1]);
      }
    });
    
    const detectedSubjects = Array.from(subjectFolders).sort();
    
    if (detectedSubjects.length > 1) {
      formData.append('detected_subjects', JSON.stringify(detectedSubjects));
      setIsBatchMode(true);
      
      structure.eventMarkersFiles.forEach((emFile, index) => {
        formData.append('event_markers_files', emFile.file);
        formData.append('event_markers_paths', emFile.path);
      });
    } else {
      setIsBatchMode(false);
      if (structure.eventMarkersFiles && structure.eventMarkersFiles.length > 0) {
        formData.append('event_markers_file', structure.eventMarkersFiles[0].file);
      }
    }

    try {
      const response = await fetch('/api/scan-folder-data', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      
      if (response.ok) {
        const metrics = data.metrics || [];
        if (structure.hasPPGFiles && !metrics.includes('HRV')) {
          metrics.push('HRV');
        }
        setAvailableMetrics(metrics);
        
        setAvailableEventMarkers(data.event_markers || []);
        setAvailableConditions(data.conditions || []);

        if (data.subjects && data.subjects.length > 0) {
          setAvailableSubjects(data.subjects);
          const initialSelection = {};
          data.subjects.forEach(subject => {
            initialSelection[subject] = true;
          });
          setSelectedSubjects(initialSelection);
        }

        const initialSelection = {};
        metrics.forEach(metric => {
          initialSelection[metric] = false;
        });
        setSelectedMetrics(initialSelection);
        
        if (data.subject_availability) {
          setSubjectAvailability(data.subject_availability);
        }

        const eventMarkersMsg = data.event_markers && data.event_markers.length > 0 
          ? `, ${data.event_markers.length} event markers` 
          : '';
        const conditionsMsg = data.conditions && data.conditions.length > 0
          ? `, ${data.conditions.length} conditions`
          : '';
        const subjectsMsg = data.subjects && data.subjects.length > 0
          ? `, ${data.subjects.length} subjects detected`
          : '';

        if (data.batch_mode && data.subjects && data.subjects.length > 1) {
          const intersectionMsg = `📊 Showing ${data.metrics.length} common metrics, ${data.event_markers.length} common markers, ${data.conditions.length} common conditions across ${data.subjects.length} subjects`;
          setBatchStatusMessage(intersectionMsg);
        }
        setUploadStatus(`Found ${metrics.length} metrics${eventMarkersMsg}${conditionsMsg}${subjectsMsg}`);
      } else {
        setUploadStatus(`Error scanning folder: ${data.error}`);
      }
    } catch (error) {
      setUploadStatus(`Error: ${error.message}`);
    } finally {
      setIsScanning(false);
    }
  };

  const updateIntersection = (selectedSubjectsList) => {
    if (!isBatchMode || Object.keys(subjectAvailability).length === 0) {
      return;
    }

    if (selectedSubjectsList.length === 0) {
      setAvailableMetrics([]);
      setAvailableEventMarkers([]);
      setAvailableConditions([]);
      setBatchStatusMessage('⚠️ No subjects selected');
      return;
    }

    if (selectedSubjectsList.length === 1) {
      const subject = selectedSubjectsList[0];
      const subjectData = subjectAvailability[subject];
      setAvailableMetrics(subjectData.metrics || []);
      setAvailableEventMarkers(subjectData.event_markers || []);
      setAvailableConditions(subjectData.conditions || []);
      setBatchStatusMessage(`Showing all markers from ${subject}`);
    } else {
      const firstSubject = selectedSubjectsList[0];
      let commonMetrics = new Set(subjectAvailability[firstSubject].metrics || []);
      let commonMarkers = new Set(subjectAvailability[firstSubject].event_markers || []);
      let commonConditions = new Set(subjectAvailability[firstSubject].conditions || []);

      selectedSubjectsList.slice(1).forEach(subject => {
        const subjectData = subjectAvailability[subject];
        commonMetrics = new Set([...commonMetrics].filter(m => (subjectData.metrics || []).includes(m)));
        commonMarkers = new Set([...commonMarkers].filter(m => (subjectData.event_markers || []).includes(m)));
        commonConditions = new Set([...commonConditions].filter(c => (subjectData.conditions || []).includes(c)));
      });

      setAvailableMetrics(Array.from(commonMetrics).sort());
      setAvailableEventMarkers(Array.from(commonMarkers).sort());
      setAvailableConditions(Array.from(commonConditions).sort());
      
      setBatchStatusMessage(
        `📊 ${commonMetrics.size} common metrics, ${commonMarkers.size} common markers, ${commonConditions.size} common conditions across ${selectedSubjectsList.length} subjects`
      );
    }
  };

  const handleMetricToggle = (metric) => {
    setSelectedMetrics(prev => ({
      ...prev,
      [metric]: !prev[metric]
    }));
  };

  const handleSubjectToggle = (subject) => {
    const newSelection = {
      ...selectedSubjects,
      [subject]: !selectedSubjects[subject]
    };
    setSelectedSubjects(newSelection);
    
    const selectedList = Object.keys(newSelection).filter(s => newSelection[s]);
    updateIntersection(selectedList);
  };

  const getSelectedSubjectsCount = () => {
    return Object.values(selectedSubjects).filter(Boolean).length;
  };

  const openConfigWizard = () => {
    setWizardStep(0);
    setShowConfigWizard(true);
    validateConfiguration();
  };

  const closeConfigWizard = () => {
    setShowConfigWizard(false);
  };

  const nextWizardStep = () => {
    if (wizardStep < 7) {
      setWizardStep(wizardStep + 1);
      if (wizardStep === 6) {
        validateConfiguration();
      }
    }
  };

  const prevWizardStep = () => {
    if (wizardStep > 0) {
      setWizardStep(wizardStep - 1);
    }
  };

  const goToWizardStep = (step) => {
    setWizardStep(step);
    if (step === 6) {
      validateConfiguration();
    }
  };

  const addEventMarker = () => {
    setSelectedEvents([...selectedEvents, { event: '', condition: 'all' }]);
  };

  const removeEventMarker = (index) => {
    if (selectedEvents.length > 1) {
      setSelectedEvents(selectedEvents.filter((_, i) => i !== index));
    }
  };

  const updateEventMarker = (index, field, value) => {
    const updated = [...selectedEvents];
    updated[index][field] = value;
    setSelectedEvents(updated);
  };

  const validateConfiguration = () => {
    const issues = [];
    
    const selectedSubjectsList = Object.keys(selectedSubjects).filter(s => selectedSubjects[s]);
    if (selectedSubjectsList.length === 0) {
      issues.push('No subjects selected');
    }
    
    const selectedMetricsList = Object.keys(selectedMetrics).filter(m => selectedMetrics[m]);
    if (selectedMetricsList.length === 0) {
      issues.push('No biometric tags selected');
    }
    
    const hasValidEvent = selectedEvents.some(e => e.event !== '');
    if (!hasValidEvent) {
      issues.push('No event markers selected');
    }
    
    if (subjectAvailability && selectedSubjectsList.length > 0) {
      selectedSubjectsList.forEach(subject => {
        const subjectData = subjectAvailability[subject];
        if (!subjectData) return;
        
        selectedMetricsList.forEach(metric => {
          if (metric === 'HRV') return;
          if (!subjectData.metrics.includes(metric)) {
            issues.push(`Subject ${subject} missing metric: ${metric}`);
          }
        });
        
        selectedEvents.forEach((evt, idx) => {
          if (evt.event && !subjectData.event_markers.includes(evt.event)) {
            issues.push(`Subject ${subject} missing event: ${evt.event}`);
          }
          if (evt.condition !== 'all' && !subjectData.conditions.includes(evt.condition)) {
            issues.push(`Subject ${subject} missing condition: ${evt.condition}`);
          }
        });
      });
    }
    
    setConfigIssues(issues);
  };

  const uploadAndAnalyze = async () => {
    if (!fileStructure || !fileStructure.allFiles) {
      setUploadStatus('Please select a subject folder');
      return;
    }

    const selectedSubjectsList = Object.keys(selectedSubjects).filter(s => selectedSubjects[s]);
    if (selectedSubjectsList.length === 0) {
      setUploadStatus('Please select at least one subject to analyze');
      return;
    }

    const selectedMetricsList = Object.keys(selectedMetrics).filter(m => selectedMetrics[m]);
    if (selectedMetricsList.length === 0) {
      setUploadStatus('Please select at least one biometric metric');
      return;
    }

    const hasValidEvent = selectedEvents.some(e => e.event !== '');
    if (!hasValidEvent) {
      setUploadStatus('Please select at least one event marker');
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
      if (metric === 'HRV') {
        ['PI', 'PR', 'PG'].forEach(ppgType => {
          const ppgFile = fileStructure.emotibitFiles.find(f => 
            f.name.includes(`_${ppgType}.csv`)
          );
          if (ppgFile && !filesToUpload.includes(ppgFile.file)) {
            filesToUpload.push(ppgFile.file);
            pathsToUpload.push(ppgFile.path);
          }
        });
      } else {
        const metricFile = fileStructure.emotibitFiles.find(f => 
          f.name.includes(`_${metric}.csv`)
        );
        if (metricFile) {
          filesToUpload.push(metricFile.file);
          pathsToUpload.push(metricFile.path);
        }
      }
      if (fileStructure.eventMarkersFiles && fileStructure.eventMarkersFiles.length > 0) {
        filesToUpload.push(fileStructure.eventMarkersFiles[0].file);
        pathsToUpload.push(fileStructure.eventMarkersFiles[0].path);
      }
    });

    console.log(`Uploading ${filesToUpload.length} files for analysis:`, pathsToUpload.map(p => p.split('/').pop()));
    
    filesToUpload.forEach((file, index) => {
      formData.append('files', file);
      formData.append('paths', pathsToUpload[index]);
    });

    formData.append('folder_name', selectedFolder);
    formData.append('selected_metrics', JSON.stringify(selectedMetricsList));
    formData.append('selected_events', JSON.stringify(selectedEvents));
    formData.append('analysis_method', selectedAnalysisMethod);
    formData.append('plot_type', selectedPlotType);
    formData.append('analyze_hrv', JSON.stringify(selectedMetricsList.includes('HRV')));
    formData.append('student_id', localStorage.getItem('studentId'));

    if (selectedSubjectsList.length > 1) {
      formData.append('selected_subjects', JSON.stringify(selectedSubjectsList));
      formData.append('batch_mode', 'true');
    }

    try {
      setIsAnalyzing(true);
      setUploadStatus('Uploading folder and running analysis...');
      setResults(null);
      closeConfigWizard();

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
        setLastAnalysisStatus({ success: false, message: 'Invalid server response' });
        return;
      }
      
      if (response.ok) {
        setUploadStatus('Analysis completed successfully!');
        setResults(data.results);
        setLastAnalysisStatus({ success: true, message: 'Analysis completed successfully!' });

        sessionStorage.setItem('analysisResults', JSON.stringify(data.results));

        const resultsWindow = window.open('/results', '_blank');

        if (!resultsWindow) {
          setUploadStatus('Analysis completed! Please allow pop-ups to view results.');
        }
      } else {
        setUploadStatus(`Error: ${data.error}`);
        setLastAnalysisStatus({ success: false, message: data.error });
      }
    } catch (error) {
      console.error('Fetch error:', error);
      setUploadStatus(`Error: ${error.message}`);
      setLastAnalysisStatus({ success: false, message: error.message });
    } finally {
      setIsAnalyzing(false);
    }
  };

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

  if (!isLoggedIn) {
    const handleRegister = async (e) => {
      e.preventDefault();
      setLoginError('');
      
      if (!registerName.trim() || !registerEmail.trim() || !registerStudentId.trim()) {
        setLoginError('First name, last name, and email are required');
        return;
      }

      try {
        const response = await fetch('/api/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            first_name: registerName.trim(),
            last_name: registerEmail.trim(),
            email: registerStudentId.trim()
          })
        });

        const data = await response.json();

        if (response.ok) {
          alert(`Registration successful!\n\nYour Student ID is: ${data.student_id}\n\nPlease use this ID to login.`);
          setShowRegister(false);
          setRegisterName('');
          setRegisterEmail('');
          setRegisterStudentId('');
          setLoginError('');
        } else {
          setLoginError(data.error || 'Registration failed');
        }
      } catch (error) {
        setLoginError('Unable to connect to server');
      }
    };
    
    return (
      <div className="container">
        <div className="header-card login-card">
          <h2 className="main-title">UCSD XRLab</h2>
          <p className="login-subtitle">Data Analysis Platform</p>
          
          {!showRegister ? (
            <form onSubmit={handleLogin} className="folder-select-section">
              <label className="input-label">Student ID</label>
              <input
                type="text"
                className="folder-input"
                value={loginStudentId}
                onChange={(e) => setLoginStudentId(e.target.value)}
                placeholder="e.g., jsmith2024"
                autoFocus
              />
              
              {loginError && (
                <div className="status-message error">{loginError}</div>
              )}
              
              <button type="submit" className="browse-button">Login</button>
              
              <div className="login-divider">
                <p className="login-help-text">Don't have a Student ID?</p>
                <button 
                  type="button"
                  onClick={() => setShowRegister(true)}
                  className="browse-button create-id-btn"
                >
                  Create New ID
                </button>
              </div>
            </form>
          ) : (
            <form onSubmit={handleRegister} className="folder-select-section">
              <div className="form-input-group">
                <label className="input-label">First Name *</label>
                <input
                  type="text"
                  className="folder-input"
                  value={registerName}
                  onChange={(e) => setRegisterName(e.target.value)}
                  placeholder="e.g., John"
                  autoFocus
                />
              </div>
              
              <div className="form-input-group">
                <label className="input-label">Last Name *</label>
                <input
                  type="text"
                  className="folder-input"
                  value={registerEmail}
                  onChange={(e) => setRegisterEmail(e.target.value)}
                  placeholder="e.g., Smith"
                />
              </div>
              
              <div className="form-input-group">
                <label className="input-label">Email *</label>
                <input
                  type="email"
                  className="folder-input"
                  value={registerStudentId}
                  onChange={(e) => setRegisterStudentId(e.target.value)}
                  placeholder="e.g., jsmith@university.edu"
                />
              </div>
              
              {loginError && (
                <div className="status-message error">{loginError}</div>
              )}
              
              <div className="register-buttons">
                <button type="submit" className="browse-button register-btn">
                  Register
                </button>
                <button 
                  type="button"
                  onClick={() => {
                    setShowRegister(false);
                    setRegisterName('');
                    setRegisterEmail('');
                    setRegisterStudentId('');
                    setLoginError('');
                  }}
                  className="browse-button back-to-login-btn"
                >
                  Back to Login
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="student-header">
        <span className="student-info-text">
          Logged in as: <strong>{localStorage.getItem('studentName')}</strong> ({localStorage.getItem('studentId')})
        </span>
        <button onClick={handleLogout} className="logout-btn">Logout</button>
      </div>
      
      <div className="header-card">
        <h1 className="main-title">Experiment Data Analysis</h1>
        <div className="folder-select-section">
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
            Browse For Subject Data
          </label>
          {selectedFolder && (
            <div className="folder-selected">
              ✓ Folder: <strong>{selectedFolder}</strong>
            </div>
          )}
        </div>
      </div>

      {fileStructure && (
        <div className="main-content-area">
          <div className="file-structure-card">
            <h3 className="structure-title">Detected Files</h3>
            
            <div className="file-category">
              <strong>EmotiBit Data:</strong>
              <span className="file-count">{fileStructure.emotibitFiles.length} file(s)</span>
            </div>
            
            <div className="file-category">
              <strong>Respiration Data:</strong>
              <span className="file-count">{fileStructure.respirationFiles.length} file(s)</span>
            </div>
            
            <div className="file-category">
              <strong>Event Markers:</strong>
              {fileStructure.eventMarkersFiles.length > 0 ? (
                <span className="file-count">{fileStructure.eventMarkersFiles.length} file(s)</span>
              ) : (
                <span className="file-count">❌ No files found</span>
              )}
            </div>
            
            <div className="file-category">
              <strong>SER/Transcription:</strong>
              {fileStructure.serFiles.length > 0 ? (
                <span className="file-count">{fileStructure.serFiles.length} file(s)</span>
              ) : (
                <span style={{ color: '#666', fontSize: '14px' }}>⚠️ No files (optional)</span>
              )}
            </div>

            {batchStatusMessage && isBatchMode && (
              <div className="file-category" style={{ 
                marginTop: '15px', 
                paddingTop: '15px', 
                borderTop: '1px solid #ddd' 
              }}>
                <div style={{ 
                  padding: '10px', 
                  backgroundColor: batchStatusMessage.includes('⚠️') ? '#fff3cd' : '#d4edda',
                  border: `1px solid ${batchStatusMessage.includes('⚠️') ? '#ffc107' : '#28a745'}`,
                  borderRadius: '4px',
                  fontSize: '13px',
                  lineHeight: '1.5',
                  whiteSpace: 'pre-line'
                }}>
                  {batchStatusMessage}
                </div>
              </div>
            )}
          </div>

          <div className="config-action-area">
            <button 
              onClick={openConfigWizard}
              disabled={isScanning || !fileStructure}
              className="config-analysis-btn"
            >
              ⚙️ Configure Analysis
            </button>

            {uploadStatus && (
              <div className={`status-message ${uploadStatus.includes('Error') || uploadStatus.includes('⚠️') ? 'error' : 'success'}`}>
                {uploadStatus}
              </div>
            )}

            {lastAnalysisStatus && (
              <div className={`analysis-status ${lastAnalysisStatus.success ? 'success' : 'error'}`}>
                {lastAnalysisStatus.success ? '✅' : '❌'} {lastAnalysisStatus.message}
              </div>
            )}

            {results && (
              <div className="results-redirect-section">
                <p className="results-redirect-text">
                  ✅ Results opened in new tab
                </p>
                <button 
                  onClick={() => {
                    sessionStorage.setItem('analysisResults', JSON.stringify(results));
                    window.open('/results', '_blank');
                  }}
                  className="reopen-results-btn"
                >
                  🔄 Re-open Results
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {showConfigWizard && (
        <div className="config-wizard-overlay">
          <div className="config-wizard-panel">
            <div className="wizard-header">
              <h2 className="wizard-title">Analysis Configuration</h2>
              <button onClick={closeConfigWizard} className="wizard-close-btn">×</button>
            </div>

            <div className="wizard-breadcrumbs">
              {['Type', 'Tags', 'Events', 'Conditions', 'Method', 'Plot', 'Review', 'Run'].map((label, idx) => (
                <div
                  key={idx}
                  className={`breadcrumb ${wizardStep === idx ? 'active' : ''} ${wizardStep > idx ? 'completed' : ''}`}
                  onClick={() => goToWizardStep(idx)}
                >
                  {label}
                </div>
              ))}
            </div>

            <div className="wizard-content">
              {wizardStep === 0 && (
                <div className="wizard-section">
                  <h3 className="wizard-section-title">Analysis Type</h3>
                  <p className="wizard-section-description">
                    Choose whether you want to analyze a single subject (inter-subject) or compare across multiple subjects (intra-subject).
                  </p>
                  
                  <div className="analysis-type-options">
                    <label className="analysis-type-option">
                      <input
                        type="radio"
                        name="analysisType"
                        value="inter"
                        checked={analysisType === 'inter'}
                        onChange={(e) => setAnalysisType(e.target.value)}
                      />
                      <div className="option-content">
                        <strong>Inter-Subject</strong>
                        <span>Single subject analysis</span>
                      </div>
                    </label>
                    
                    <label className="analysis-type-option">
                      <input
                        type="radio"
                        name="analysisType"
                        value="intra"
                        checked={analysisType === 'intra'}
                        onChange={(e) => setAnalysisType(e.target.value)}
                      />
                      <div className="option-content">
                        <strong>Intra-Subject</strong>
                        <span>Multi-subject comparison</span>
                      </div>
                    </label>
                  </div>

                  {availableSubjects.length > 0 && (
                    <div className="subject-selection">
                      <h4 className="subsection-title">Select Subjects</h4>
                      <div className="subject-checklist">
                        {availableSubjects.map(subject => (
                          <label key={subject} className="subject-checkbox">
                            <input
                              type="checkbox"
                              checked={selectedSubjects[subject] || false}
                              onChange={() => handleSubjectToggle(subject)}
                            />
                            <span>{subject}</span>
                          </label>
                        ))}
                      </div>
                      <div className="selection-summary">
                        {getSelectedSubjectsCount()} of {availableSubjects.length} subjects selected
                      </div>
                    </div>
                  )}
                </div>
              )}

              {wizardStep === 1 && (
                <div className="wizard-section">
                  <h3 className="wizard-section-title">Biometric Tags</h3>
                  <p className="wizard-section-description">
                    Select the biometric metrics you want to analyze.
                  </p>

                  {getSelectedSubjectsCount() > 1 && (
                    <div className="mode-toggle">
                      <label className="toggle-option">
                        <input
                          type="radio"
                          name="tagMode"
                          value="union"
                          checked={tagMode === 'union'}
                          onChange={(e) => setTagMode(e.target.value)}
                        />
                        <span>Union (all tags across subjects)</span>
                      </label>
                      <label className="toggle-option">
                        <input
                          type="radio"
                          name="tagMode"
                          value="intersection"
                          checked={tagMode === 'intersection'}
                          onChange={(e) => setTagMode(e.target.value)}
                        />
                        <span>Intersection (common tags only)</span>
                      </label>
                    </div>
                  )}

                  <div className="tag-grid">
                    {availableMetrics.map(metric => (
                      <label key={metric} className="tag-checkbox">
                        <input
                          type="checkbox"
                          checked={selectedMetrics[metric] || false}
                          onChange={() => handleMetricToggle(metric)}
                        />
                        <span>{metric}</span>
                      </label>
                    ))}
                  </div>
                  
                  <div className="selection-summary">
                    {Object.values(selectedMetrics).filter(Boolean).length} tags selected
                  </div>
                </div>
              )}

              {wizardStep === 2 && (
                <div className="wizard-section">
                  <h3 className="wizard-section-title">Event Markers</h3>
                  <p className="wizard-section-description">
                    Select event markers to analyze. You can add multiple event windows for comparison.
                  </p>

                  {getSelectedSubjectsCount() > 1 && (
                    <div className="mode-toggle">
                      <label className="toggle-option">
                        <input
                          type="radio"
                          name="eventMode"
                          value="union"
                          checked={eventMode === 'union'}
                          onChange={(e) => setEventMode(e.target.value)}
                        />
                        <span>Union</span>
                      </label>
                      <label className="toggle-option">
                        <input
                          type="radio"
                          name="eventMode"
                          value="intersection"
                          checked={eventMode === 'intersection'}
                          onChange={(e) => setEventMode(e.target.value)}
                        />
                        <span>Intersection</span>
                      </label>
                    </div>
                  )}

                  <div className="event-list">
                    {selectedEvents.map((evt, idx) => (
                      <div key={idx} className="event-item">
                        <select
                          value={evt.event}
                          onChange={(e) => updateEventMarker(idx, 'event', e.target.value)}
                          className="event-select"
                        >
                          <option value="">Select event...</option>
                          <option value="all">All (entire experiment)</option>
                          {availableEventMarkers.map(marker => (
                            <option key={marker} value={marker}>{marker}</option>
                          ))}
                        </select>
                        
                        {selectedEvents.length > 1 && (
                          <button
                            onClick={() => removeEventMarker(idx)}
                            className="remove-event-btn"
                          >
                            ×
                          </button>
                        )}
                      </div>
                    ))}
                  </div>

                  <button onClick={addEventMarker} className="add-event-btn">
                    + Add Event Window
                  </button>
                </div>
              )}

              {wizardStep === 3 && (
                <div className="wizard-section">
                  <h3 className="wizard-section-title">Condition Markers</h3>
                  <p className="wizard-section-description">
                    Select conditions to filter your analysis.
                  </p>

                  {getSelectedSubjectsCount() > 1 && (
                    <div className="mode-toggle">
                      <label className="toggle-option">
                        <input
                          type="radio"
                          name="conditionMode"
                          value="union"
                          checked={conditionMode === 'union'}
                          onChange={(e) => setConditionMode(e.target.value)}
                        />
                        <span>Union</span>
                      </label>
                      <label className="toggle-option">
                        <input
                          type="radio"
                          name="conditionMode"
                          value="intersection"
                          checked={conditionMode === 'intersection'}
                          onChange={(e) => setConditionMode(e.target.value)}
                        />
                        <span>Intersection</span>
                      </label>
                    </div>
                  )}

                  <div className="condition-list">
                    {selectedEvents.map((evt, idx) => (
                      <div key={idx} className="condition-item">
                        <label className="condition-label">
                          Event {idx + 1}: {evt.event || '(not selected)'}
                        </label>
                        <select
                          value={evt.condition}
                          onChange={(e) => updateEventMarker(idx, 'condition', e.target.value)}
                          className="condition-select"
                        >
                          <option value="all">All conditions</option>
                          {availableConditions.map(condition => (
                            <option key={condition} value={condition}>{condition}</option>
                          ))}
                        </select>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {wizardStep === 4 && (
                <div className="wizard-section">
                  <h3 className="wizard-section-title">Analysis Method</h3>
                  <p className="wizard-section-description">
                    Choose the statistical method for your analysis.
                  </p>

                  <div className="method-grid">
                    <label className="method-option">
                      <input
                        type="radio"
                        name="analysisMethod"
                        value="raw"
                        checked={selectedAnalysisMethod === 'raw'}
                        onChange={(e) => setSelectedAnalysisMethod(e.target.value)}
                      />
                      <div className="method-content">
                        <strong>Raw Data</strong>
                        <span>Direct signal values</span>
                      </div>
                    </label>

                    <label className="method-option">
                      <input
                        type="radio"
                        name="analysisMethod"
                        value="mean"
                        checked={selectedAnalysisMethod === 'mean'}
                        onChange={(e) => setSelectedAnalysisMethod(e.target.value)}
                      />
                      <div className="method-content">
                        <strong>Mean</strong>
                        <span>Average value</span>
                      </div>
                    </label>

                    <label className="method-option">
                      <input
                        type="radio"
                        name="analysisMethod"
                        value="moving_average"
                        checked={selectedAnalysisMethod === 'moving_average'}
                        onChange={(e) => setSelectedAnalysisMethod(e.target.value)}
                      />
                      <div className="method-content">
                        <strong>Moving Average</strong>
                        <span>Smoothed signal</span>
                      </div>
                    </label>

                    <label className="method-option">
                      <input
                        type="radio"
                        name="analysisMethod"
                        value="rmssd"
                        checked={selectedAnalysisMethod === 'rmssd'}
                        onChange={(e) => setSelectedAnalysisMethod(e.target.value)}
                      />
                      <div className="method-content">
                        <strong>RMSSD</strong>
                        <span>Root mean square of successive differences</span>
                      </div>
                    </label>
                  </div>
                </div>
              )}

              {wizardStep === 5 && (
                <div className="wizard-section">
                  <h3 className="wizard-section-title">Plot Type</h3>
                  <p className="wizard-section-description">
                    Select how you want to visualize your data.
                  </p>

                  <div className="plot-grid">
                    <label className="plot-option">
                      <input
                        type="radio"
                        name="plotType"
                        value="lineplot"
                        checked={selectedPlotType === 'lineplot'}
                        onChange={(e) => setSelectedPlotType(e.target.value)}
                      />
                      <div className="plot-content">
                        <strong>Line Plot</strong>
                        <span>Time series visualization</span>
                      </div>
                    </label>

                    <label className="plot-option">
                      <input
                        type="radio"
                        name="plotType"
                        value="boxplot"
                        checked={selectedPlotType === 'boxplot'}
                        onChange={(e) => setSelectedPlotType(e.target.value)}
                      />
                      <div className="plot-content">
                        <strong>Box Plot</strong>
                        <span>Distribution summary</span>
                      </div>
                    </label>

                    <label className="plot-option">
                      <input
                        type="radio"
                        name="plotType"
                        value="poincare"
                        checked={selectedPlotType === 'poincare'}
                        onChange={(e) => setSelectedPlotType(e.target.value)}
                      />
                      <div className="plot-content">
                        <strong>Poincaré Plot</strong>
                        <span>HRV analysis</span>
                      </div>
                    </label>

                    <label className="plot-option">
                      <input
                        type="radio"
                        name="plotType"
                        value="scatter"
                        checked={selectedPlotType === 'scatter'}
                        onChange={(e) => setSelectedPlotType(e.target.value)}
                      />
                      <div className="plot-content">
                        <strong>Scatter Plot</strong>
                        <span>Point distribution</span>
                      </div>
                    </label>
                  </div>
                </div>
              )}

              {wizardStep === 6 && (
                <div className="wizard-section">
                  <h3 className="wizard-section-title">Configuration Review</h3>
                  <p className="wizard-section-description">
                    Review your analysis configuration before running.
                  </p>

                  <div className="config-summary">
                    <div className="summary-item">
                      <strong>Analysis Type:</strong> {analysisType === 'inter' ? 'Inter-Subject (Single)' : 'Intra-Subject (Multi)'}
                    </div>
                    <div className="summary-item">
                      <strong>Subjects:</strong> {getSelectedSubjectsCount()} selected
                    </div>
                    <div className="summary-item">
                      <strong>Biometric Tags:</strong> {Object.values(selectedMetrics).filter(Boolean).length} selected
                    </div>
                    <div className="summary-item">
                      <strong>Event Windows:</strong> {selectedEvents.filter(e => e.event).length} configured
                    </div>
                    <div className="summary-item">
                      <strong>Analysis Method:</strong> {selectedAnalysisMethod}
                    </div>
                    <div className="summary-item">
                      <strong>Plot Type:</strong> {selectedPlotType}
                    </div>
                  </div>

                  {configIssues.length > 0 && (
                    <div className="config-issues">
                      <h4 className="issues-title">⚠️ Configuration Issues:</h4>
                      <ul className="issues-list">
                        {configIssues.map((issue, idx) => (
                          <li key={idx}>{issue}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {configIssues.length === 0 && (
                    <div className="config-ready">
                      ✅ Configuration looks good! Ready to run analysis.
                    </div>
                  )}
                </div>
              )}

              {wizardStep === 7 && (
                <div className="wizard-section wizard-final">
                  <h3 className="wizard-section-title">Run Analysis</h3>
                  <p className="wizard-section-description">
                    Click the button below to start processing your data. This may take a few moments.
                  </p>

                  <button
                    onClick={uploadAndAnalyze}
                    disabled={configIssues.length > 0 || isAnalyzing}
                    className="run-analysis-btn"
                  >
                    {isAnalyzing ? '⏳ Analyzing...' : '🚀 Run Analysis'}
                  </button>

                  {configIssues.length > 0 && (
                    <div className="final-warning">
                      Please resolve configuration issues before running analysis.
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="wizard-footer">
              <button
                onClick={prevWizardStep}
                disabled={wizardStep === 0}
                className="wizard-nav-btn prev"
              >
                ← Previous
              </button>

              <div className="wizard-progress">
                Step {wizardStep + 1} of 8
              </div>

              <button
                onClick={nextWizardStep}
                disabled={wizardStep === 7}
                className="wizard-nav-btn next"
              >
                Next →
              </button>
            </div>
          </div>
        </div>
      )}

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

      {showWizard && !showConfigWizard && (
        <div className="instruction-wizard">
          <div className="wizard-header">
            <h3 className="wizard-title">User Guide</h3>
            <button 
              className="wizard-close-btn"
              onClick={() => setShowWizard(false)}
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
      )}

      {!showWizard && !showConfigWizard && (
        <button
          className="wizard-toggle-btn"
          onClick={() => setShowWizard(true)}
        />
      )}
    </div>
  );
}

export default AnalysisViewer;