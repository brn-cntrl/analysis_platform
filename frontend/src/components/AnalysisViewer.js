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

  // Analysis Configuration State
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
      serFiles: [],
      eventMarkersFiles: [],
      allFiles: files
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

      structure.hasPPGFiles = structure.emotibitFiles.some(f => 
        f.name.includes('_PI.csv') || f.name.includes('_PR.csv') || f.name.includes('_PG.csv')
      );
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
    
    const emotibitFileList = structure.emotibitFiles.map(f => f.path);
    formData.append('emotibit_filenames', JSON.stringify(emotibitFileList));

    const allPaths = structure.allFiles.map(f => f.webkitRelativePath);
    const subjectFolders = new Set();
    allPaths.forEach(path => {
      const parts = path.split('/');
      if (parts.length >= 3) {
        // Path like: root/subject_001/emotibit_data/file.csv
        subjectFolders.add(parts[1]);
      }
    });
    
    const detectedSubjects = Array.from(subjectFolders).sort();
    
    if (detectedSubjects.length > 1) {
      formData.append('detected_subjects', JSON.stringify(detectedSubjects));
      setIsBatchMode(true);
      
      // Send all event markers files (one per subject)
      structure.eventMarkersFiles.forEach((emFile, index) => {
        formData.append('event_markers_files', emFile.file);
        formData.append('event_markers_paths', emFile.path);
      });
    } else {
      setIsBatchMode(false);
      // Single subject - send single event markers file
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
        // Add HRV to metrics if PPG files are available
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
            initialSelection[subject] = true; // Default to all selected
          });
          setSelectedSubjects(initialSelection);
        }

        const initialSelection = {};

        data.metrics.forEach(metric => {
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

        let intersectionMsg = '';
        if (data.batch_mode && data.subjects && data.subjects.length > 1) {
          intersectionMsg = `\n📊 Showing ${data.metrics.length} common metrics, ${data.event_markers.length} common markers, ${data.conditions.length} common conditions across ${data.subjects.length} subjects`;
        }

        setUploadStatus(`Found ${data.metrics.length} metrics${eventMarkersMsg}${conditionsMsg}${subjectsMsg}${intersectionMsg}`);
      
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
      setUploadStatus('⚠️ No subjects selected');
      return;
    }

    if (selectedSubjectsList.length === 1) {
      // Single subject selected - show all from that subject
      const subject = selectedSubjectsList[0];
      const subjectData = subjectAvailability[subject];
      setAvailableMetrics(subjectData.metrics || []);
      setAvailableEventMarkers(subjectData.event_markers || []);
      setAvailableConditions(subjectData.conditions || []);
      setUploadStatus(`Showing all markers from ${subject}`);
    } else {
      // Multiple subjects - calculate intersection
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
      
      setUploadStatus(
        `${commonMetrics.size} common metrics, ${commonMarkers.size} common markers, ${commonConditions.size} common conditions across ${selectedSubjectsList.length} subjects`
      );
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

  const handleSubjectToggle = (subject) => {
    const newSelection = {
      ...selectedSubjects,
      [subject]: !selectedSubjects[subject]
    };
    setSelectedSubjects(newSelection);
    
    // Recalculate intersection based on new selection
    const selectedList = Object.keys(newSelection).filter(s => newSelection[s]);
    updateIntersection(selectedList);
  };

  const handleSelectAllSubjects = () => {
    const allSelected = {};
    availableSubjects.forEach(subject => {
      allSelected[subject] = true;
    });
    setSelectedSubjects(allSelected);
    updateIntersection(availableSubjects);
  };

  const handleDeselectAllSubjects = () => {
    const noneSelected = {};
    availableSubjects.forEach(subject => {
      noneSelected[subject] = false;
    });
    setSelectedSubjects(noneSelected);
    updateIntersection([]);
  };

  const getSelectedSubjectsCount = () => {
    return Object.values(selectedSubjects).filter(Boolean).length;
  };

  const uploadAndAnalyze = async () => {
    if (!fileStructure || !fileStructure.allFiles) {
      setUploadStatus('Please select a subject folder');
      return;
    }

    if (isBatchMode) {
      const selectedSubjectsList = Object.keys(selectedSubjects).filter(s => selectedSubjects[s]);
      if (selectedSubjectsList.length === 0) {
        setUploadStatus('Please select at least one subject to analyze');
        return;
      }
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
      // HRV requires PPG files, not a direct metric file
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
        // Regular metric file
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
    formData.append('comparison_groups', JSON.stringify(comparisonGroups));
    formData.append('analyze_hrv', JSON.stringify(selectedMetricsList.includes('HRV')));
    formData.append('student_id', localStorage.getItem('studentId'));

    const selectedSubjectsList = Object.keys(selectedSubjects).filter(s => selectedSubjects[s]);
    if (selectedSubjectsList.length > 1) {
      formData.append('selected_subjects', JSON.stringify(selectedSubjectsList));
      formData.append('batch_mode', 'true');
    }

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
            // LOGIN FORM
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
            // REGISTRATION FORM
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
        <div className="two-column-layout">
          {/* LEFT COLUMN */}
          <div className="left-column">
            {/* Detected Files */}
            <div className="file-structure">
              <h3 className="structure-title">📋 Detected Files</h3>
              
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
                  <span className="file-count"> {fileStructure.serFiles.length} file(s)</span>
                ) : (
                  <span style={{ color: '#666', fontSize: '14px' }}>⚠️ No files (optional)</span>
                )}
              </div>

              {/* Batch Mode Status Message */}
              {uploadStatus && isBatchMode && (
                <div className="file-category" style={{ 
                  marginTop: '15px', 
                  paddingTop: '15px', 
                  borderTop: '1px solid #ddd' 
                }}>
                  <div style={{ 
                    padding: '10px', 
                    // backgroundColor: uploadStatus.includes('⚠️') ? '#fff3cd' : '#d4edda',
                    // border: `1px solid ${uploadStatus.includes('⚠️') ? '#ffc107' : '#28a745'}`,
                    borderRadius: '4px',
                    fontSize: '13px',
                    lineHeight: '1.5',
                    whiteSpace: 'pre-line'
                  }}>
                    {uploadStatus}
                  </div>
                </div>
              )}
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

            {/* Subject Selection Section - Only show in batch mode */}
            {isBatchMode && availableSubjects.length > 0 && (
              <div className="subjects-section">
                <div className="subjects-header">
                  <h3 className="section-title">Select Subjects to Analyze</h3>
                  <div className="subjects-controls">
                    <button onClick={handleSelectAllSubjects} className="metric-control-btn">
                      Select All
                    </button>
                    <button onClick={handleDeselectAllSubjects} className="metric-control-btn">
                      Deselect All
                    </button>
                    <span className="selected-count">
                      {getSelectedSubjectsCount()} selected
                    </span>
                  </div>
                </div>

                <div className="subjects-grid">
                  {availableSubjects.map((subject) => (
                    <label key={subject} className="metric-checkbox">
                      <input
                        type="checkbox"
                        checked={selectedSubjects[subject] || false}
                        onChange={() => handleSubjectToggle(subject)}
                      />
                      <span className="metric-label">{subject}</span>
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
            {/* {uploadStatus && (
              <div className={`status-message ${uploadStatus.includes('Error') ? 'error' : 'success'}`}>
                {uploadStatus}
              </div>
            )} */}

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