import React, { useState, useEffect, useRef } from 'react';
import './AnalysisViewer.css';
import ExternalConfigStep from './ExternalConfigStep';
import './ExternalConfigStep.css';

const DATA_SOURCE_CAPABILITIES = {
  'emotibit': {
    compatible_methods: ['raw', 'mean', 'moving_average', 'rmssd'],
    compatible_plots: ['lineplot', 'boxplot', 'scatter', 'poincare', 'barchart']
  },
  'respiratory': {
    compatible_methods: ['raw', 'mean', 'moving_average'],
    compatible_plots: ['lineplot', 'boxplot', 'barchart']
  },
  'cardiac': {
    compatible_methods: ['raw', 'mean', 'moving_average'],
    compatible_plots: ['lineplot', 'boxplot', 'barchart']
  },
  'external': {
    compatible_methods: ['raw', 'mean', 'moving_average'],
    compatible_plots: ['lineplot', 'boxplot', 'barchart']
  }
};

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
  
  // External data file state - UPDATED FOR MULTIPLE FILES
  const [externalFilesBySubject, setExternalFilesBySubject] = useState({});
  const [hasExternalFiles, setHasExternalFiles] = useState(false);
  const [subjectsWithExternal, setsubjectsWithExternal] = useState([]);
  const [externalConfigs, setExternalConfigs] = useState({});

  const [needsDataParser, setNeedsDataParser] = useState(false);
  const [subjectsNeedingParser, setSubjectsNeedingParser] = useState([]);
  const [parserLaunchStatus, setParserLaunchStatus] = useState('');
  const [parseLSLStatus, setParseLSLStatus] = useState('');

  // Respiratory data state
  const [hasRespiratoryData, setHasRespiratoryData] = useState(false);
  const [subjectsWithRespiratory, setSubjectsWithRespiratory] = useState([]);
  const [respiratoryConfigs, setRespiratoryConfigs] = useState({});

  // Cardiac data state
  const [hasCardiacData, setHasCardiacData] = useState(false);
  const [subjectsWithCardiac, setSubjectsWithCardiac] = useState([]);
  const [cardiacConfigs, setCardiacConfigs] = useState({});

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

  // REFS
  const fileInputRef = useRef(null);

  // Data cleaning state
  const [cleaningEnabled, setCleaningEnabled] = useState(false);
  const [cleaningStages, setCleaningStages] = useState({
    remove_invalid: true,
    remove_physiological_outliers: true,
    remove_statistical_outliers: false,
    remove_sudden_changes: true,
    interpolate: true,
    smooth: false
  });

  // Calculate compatible analysis methods and plot types based on selected data sources
  const getCompatibleOptions = React.useCallback(() => {
    const selectedSources = [];
    
    // Check EmotiBit metrics
    const hasEmotiBitSelected = Object.values(selectedMetrics).some(v => v);
    if (hasEmotiBitSelected) {
      selectedSources.push('emotibit');
    }
    
    // Check Respiratory data
    if (hasRespiratoryData) {
      const hasRespiratorySelected = Object.values(respiratoryConfigs).some(c => c.selected);
      if (hasRespiratorySelected) {
        selectedSources.push('respiratory');
      }
    }
    
    // Check Cardiac data
    if (hasCardiacData) {
      const hasCardiacSelected = Object.values(cardiacConfigs).some(c => c.selected);
      if (hasCardiacSelected) {
        selectedSources.push('cardiac');
      }
    }
    
    // Check External data
    if (hasExternalFiles) {
      const selectedSubjectsList = Object.keys(selectedSubjects).filter(s => selectedSubjects[s]);
      const hasExternalSelected = selectedSubjectsList.some(subject => {
        if (subjectsWithExternal.includes(subject) && externalConfigs[subject]) {
          return Object.values(externalConfigs[subject]).some(config => config.selected !== false);
        }
        return false;
      });
      if (hasExternalSelected) {
        selectedSources.push('external');
      }
    }
    
    // If nothing selected, return all options
    if (selectedSources.length === 0) {
      return {
        compatibleMethods: ['raw', 'mean', 'moving_average', 'rmssd'],
        compatiblePlots: ['lineplot', 'boxplot', 'scatter', 'poincare', 'barchart'],
        selectedSources: []
      };
    }
    
    // Find intersection of compatible options
    const allMethods = ['raw', 'mean', 'moving_average', 'rmssd'];
    const allPlots = ['lineplot', 'boxplot', 'scatter', 'poincare', 'barchart'];
    
    const compatibleMethods = allMethods.filter(method =>
      selectedSources.every(source =>
        DATA_SOURCE_CAPABILITIES[source].compatible_methods.includes(method)
      )
    );
    
    const compatiblePlots = allPlots.filter(plot =>
      selectedSources.every(source =>
        DATA_SOURCE_CAPABILITIES[source].compatible_plots.includes(plot)
      )
    );
    
    return { compatibleMethods, compatiblePlots, selectedSources };
  }, [selectedMetrics, hasRespiratoryData, respiratoryConfigs, hasCardiacData, 
      cardiacConfigs, hasExternalFiles, selectedSubjects, subjectsWithExternal, externalConfigs]);

  const validateConfiguration = React.useCallback(() => {
    const issues = [];
    
    const selectedSubjectsList = Object.keys(selectedSubjects).filter(s => selectedSubjects[s]);
    if (selectedSubjectsList.length === 0) {
      issues.push('No subjects selected');
    }

    // Check if ANY data type is selected (not just biometric tags)
    const selectedMetricsList = Object.keys(selectedMetrics).filter(m => selectedMetrics[m]);
    const hasRespiratorySelected = hasRespiratoryData && Object.values(respiratoryConfigs).some(c => c.selected);
    const hasCardiacSelected = hasCardiacData && Object.values(cardiacConfigs).some(c => c.selected);
    const hasExternalSelected = hasExternalFiles && selectedSubjectsList.some(subject => {
      if (subjectsWithExternal.includes(subject) && externalConfigs[subject]) {
        return Object.values(externalConfigs[subject]).some(config => config.selected !== false);
      }
      return false;
    });

    const hasAnyDataSelected = selectedMetricsList.length > 0 || hasRespiratorySelected || hasCardiacSelected || hasExternalSelected;

    if (!hasAnyDataSelected) {
      issues.push('No data selected for analysis (select EmotiBit metrics, respiratory, cardiac, or external data)');
    }

    const hasValidEvent = selectedEvents.some(e => e.event !== '');
    if (!hasValidEvent) {
      issues.push('No event markers selected');
    }
    
    if (hasExternalFiles) {
      selectedSubjectsList.forEach(subject => {
        if (subjectsWithExternal.includes(subject)) {
          const subjectConfigs = externalConfigs[subject] || {};
          Object.entries(subjectConfigs).forEach(([filename, config]) => {
            if (config.selected === false) return;
            
            if (!config.timestampColumn) {
              issues.push(`External (${subject}/${filename}): No timestamp column selected`);
            }
            
            const validDataColumns = config.dataColumns?.filter(dc => dc.column && dc.displayName) || [];
            if (validDataColumns.length === 0) {
              issues.push(`External (${subject}/${filename}): No data columns configured`);
            }
          });
        }
      });
    }
    // Validate respiratory data configuration
    if (hasRespiratoryData) {
      selectedSubjectsList.forEach(subject => {
        if (subjectsWithRespiratory.includes(subject)) {
          const config = respiratoryConfigs[subject];
          if (config && config.selected) {
            if (!config.analyzeRR && !config.analyzeForce) {
              issues.push(`Respiratory (${subject}): No metrics selected (select RR or Force)`);
            }
          }
        }
      });
    }

    // Validate cardiac data configuration
    if (hasCardiacData) {
      selectedSubjectsList.forEach(subject => {
        if (subjectsWithCardiac.includes(subject)) {
          const config = cardiacConfigs[subject];
          if (config && config.selected) {
            if (!config.analyzeHR && !config.analyzeHRV) {
              issues.push(`Cardiac (${subject}): No metrics selected (select HR or HRV)`);
            }
          }
        }
      });
    }

    if (subjectAvailability && Object.keys(subjectAvailability).length > 0 && selectedSubjectsList.length > 0) {
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
          if (evt.event && evt.event !== 'all' && !subjectData.event_markers.includes(evt.event)) {
            issues.push(`Subject ${subject} missing event: ${evt.event}`);
          }
          if (evt.condition !== 'all' && !subjectData.conditions.includes(evt.condition)) {
            issues.push(`Subject ${subject} missing condition: ${evt.condition}`);
          }
        });
      });
    }
    
    console.log('Validation complete. Issues found:', issues);
    setConfigIssues(issues);
  }, [selectedSubjects, selectedMetrics, selectedEvents, hasExternalFiles, subjectsWithExternal, externalConfigs, hasRespiratoryData, subjectsWithRespiratory, respiratoryConfigs, hasCardiacData, subjectsWithCardiac, cardiacConfigs, subjectAvailability]);

  useEffect(() => {
    console.log('availableMetrics changed:', availableMetrics);
    console.log('HRV included:', availableMetrics.includes('HRV'));
  }, [availableMetrics]);

  useEffect(() => {
    // Calculate review step dynamically
    const reviewStep = (() => {
      let step = 5; // Base steps before review
      if (hasRespiratoryData) step++;
      if (hasCardiacData) step++;
      if (hasExternalFiles) step++;
      return step;
    })();
    
    if (wizardStep === reviewStep && showConfigWizard) {
      console.log('Reached review step, validating configuration...');
      validateConfiguration();
    }
  }, [wizardStep, showConfigWizard, hasExternalFiles, hasRespiratoryData, hasCardiacData, validateConfiguration]);

  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (isLoggedIn) {
        localStorage.clear();
        e.preventDefault();
        e.returnValue = ''; 
        return ''; 
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [isLoggedIn]);

  useEffect(() => {
    if (!isLoggedIn) return;

    const handleUnload = () => {
      localStorage.clear();
    };

    window.addEventListener('unload', handleUnload);
    return () => {
      window.removeEventListener('unload', handleUnload);
    };
  }, [isLoggedIn]);

  useEffect(() => {
    const incompatibleCombos = {
      'mean': ['lineplot', 'scatter', 'boxplot', 'poincare'],
      'rmssd': ['poincare'],
      'moving_average': ['poincare']
    };
    
    const invalidPlots = incompatibleCombos[selectedAnalysisMethod] || [];
    
    if (invalidPlots.includes(selectedPlotType)) {
      console.log(`Auto-correcting: ${selectedPlotType} is incompatible with ${selectedAnalysisMethod}`);
      
      const allPlots = ['lineplot', 'boxplot', 'scatter', 'poincare', 'barchart'];
      const validPlot = allPlots.find(plot => !invalidPlots.includes(plot));
      
      if (validPlot) {
        setSelectedPlotType(validPlot);
        setUploadStatus(`Plot type auto-corrected to ${validPlot}: ${selectedPlotType} is not compatible with ${selectedAnalysisMethod} analysis`);
      }
    }
  }, [selectedAnalysisMethod, selectedPlotType, setUploadStatus]);

  // Auto-correct selections when compatible options change
  useEffect(() => {
    const { compatibleMethods, compatiblePlots } = getCompatibleOptions();
    
    // Auto-correct analysis method if current selection is incompatible
    if (!compatibleMethods.includes(selectedAnalysisMethod)) {
      const newMethod = compatibleMethods[0] || 'raw';
      console.log(`Auto-correcting analysis method: ${selectedAnalysisMethod} → ${newMethod}`);
      setSelectedAnalysisMethod(newMethod);
      setUploadStatus(`Analysis method auto-corrected to ${newMethod} (compatible with selected data sources)`);
    }
    
    // Auto-correct plot type if current selection is incompatible
    if (!compatiblePlots.includes(selectedPlotType)) {
      const newPlot = compatiblePlots[0] || 'lineplot';
      console.log(`Auto-correcting plot type: ${selectedPlotType} → ${newPlot}`);
      setSelectedPlotType(newPlot);
      setUploadStatus(`Plot type auto-corrected to ${newPlot} (compatible with selected data sources)`);
    }
  }, [selectedMetrics, hasRespiratoryData, respiratoryConfigs, hasCardiacData, 
      cardiacConfigs, hasExternalFiles, selectedSubjects, subjectsWithExternal, 
      externalConfigs, getCompatibleOptions, selectedAnalysisMethod, selectedPlotType]);

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

  const handleLSLFileSelect = async (e) => {
    const file = e.target.files[0];
    if (!file) {
      setParseLSLStatus('No file selected');
      return;
    }
    
    try {
      const formData = new FormData();
      formData.append('file', file);  // Add the file!
      
      const response = await fetch('/api/extract_lsl_markers', {
        method: 'POST',
        body: formData  // NOT JSON - send FormData
        // Do NOT set Content-Type header - let browser set it with boundary
      });
      
      const data = await response.json();
      if (response.ok) {
        // Use markers_count from endpoint response
        setParseLSLStatus(`✓ LSL markers extracted: ${data.markers_count} markers found`);
      } else {
        setParseLSLStatus(`Error: ${data.error}`);
      }
    } catch (error) {
      setParseLSLStatus(`Error: ${error.message}`);
    }
  };

  const handleLaunchDataParser = async () => {
    setParserLaunchStatus('Launching DataParser...');
    
    try {
      const response = await fetch('/api/launch-emotibit-parser', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setParserLaunchStatus('✓ DataParser launched! Please parse your files and then re-select the folder.');
      } else {
        setParserLaunchStatus(`Error: ${data.error}`);
      }
    } catch (error) {
      setParserLaunchStatus(`Error: ${error.message}`);
    }
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
      cardiacFiles: [],
      serFiles: [],
      eventMarkersFiles: [],
      externalFiles: [],
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
      } else if ((path.includes('respiratory_data/') || path.includes('respiration_data/') || path.includes('vernier_data/')) && fileName.endsWith('.csv')) {
        structure.respirationFiles.push({
          name: file.name,
          path: path,
          file: file
        });
      } else if ((path.includes('cardiac_data/') || path.includes('polar_data/')) && fileName.endsWith('.csv')) {
        structure.cardiacFiles.push({
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
      } else if (path.includes('external_data/') && fileName.endsWith('.csv')) {
        structure.externalFiles.push({
          name: file.name,
          path: path,
          file: file
        });
      }
    });

    structure.hasPPGFiles = structure.emotibitFiles.some(f => 
      f.name.includes('_PI.csv') || f.name.includes('_PR.csv') || f.name.includes('_PG.csv')
    );

    console.log('=== Folder Structure Analysis ===');
    console.log('Total EmotiBit files:', structure.emotibitFiles.length);
    console.log('EmotiBit filenames:', structure.emotibitFiles.map(f => f.name));
    console.log('Total Respiratory files:', structure.respirationFiles.length);
    console.log('Respiratory filenames:', structure.respirationFiles.map(f => f.name));
    console.log('Total Cardiac files:', structure.cardiacFiles.length);
    console.log('Cardiac filenames:', structure.cardiacFiles.map(f => f.name));
    console.log('PPG files detected:', structure.hasPPGFiles);
    console.log('=================================');

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

    const readExternalFile = (file) => {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => {
          try {
            const text = e.target.result;
            const lines = text.split('\n');
            
            const headers = lines[0].split(',')
              .map(h => h.trim())
              .filter(h => h && !h.startsWith('Unnamed:'));
            
            const sampleData = [];
            for (let i = 1; i < Math.min(6, lines.length); i++) {
              if (lines[i].trim()) {
                const values = lines[i].split(',');
                const rowObj = {};
                headers.forEach((header, idx) => {
                  rowObj[header] = values[idx]?.trim() || null;
                });
                sampleData.push(rowObj);
              }
            }
            
            const columnTypes = headers.map(header => {
              const sampleValues = sampleData
                .map(row => row[header])
                .filter(v => v !== null && v !== '' && v !== undefined);
              
              if (sampleValues.length === 0) return 'string';
              
              let numericCount = 0;
              for (const value of sampleValues) {
                if (!isNaN(parseFloat(value)) && isFinite(value)) {
                  numericCount++;
                }
              }
              
              return (numericCount / sampleValues.length >= 0.5) ? 'numeric' : 'string';
            });
            
            resolve({
              columns: headers,
              column_types: columnTypes,
              sample_data: sampleData,
              row_count: lines.length - 1
            });
          } catch (error) {
            reject(error);
          }
        };
        reader.onerror = reject;
        reader.readAsText(file);
      });
    };

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

    if (detectedSubjects.length > 0) {
      formData.append('detected_subjects', JSON.stringify(detectedSubjects));
      
      structure.eventMarkersFiles.forEach((emFile, index) => {
        formData.append('event_markers_files', emFile.file);
        formData.append('event_markers_paths', emFile.path);
      });
    }
    
    if (detectedSubjects.length > 1) {
      setIsBatchMode(true);
    } else {
      setIsBatchMode(false);
    }

    const externalMetadata = {};
    const externalPromises = [];

    structure.externalFiles.forEach(externalFile => {
      const parts = externalFile.path.split('/');
      if (parts.length >= 3) {
        const subject = parts[1];
        const filename = parts[parts.length - 1];
        const filenameparts = filename.replace('.csv', '').split('_');
        const experimentName = filenameparts.length >= 3 ? filenameparts[2] : 'Unknown';
        
        const promise = readExternalFile(externalFile.file).then(metadata => {
          if (!externalMetadata[subject]) {
            externalMetadata[subject] = [];
          }
          externalMetadata[subject].push({
            filename: filename,
            path: externalFile.path,
            experiment_name: experimentName,
            ...metadata
          });
        }).catch(error => {
          console.error(`Error reading external data file ${filename}:`, error);
        });
        
        externalPromises.push(promise);
      }
    });

    await Promise.all(externalPromises);

    if (Object.keys(externalMetadata).length > 0) {
      formData.append('external_metadata', JSON.stringify(externalMetadata));
    }

    if (structure.respirationFiles.length > 0) {
      const respiratoryPaths = structure.respirationFiles.map(f => f.path);
      formData.append('respiratory_filenames', JSON.stringify(respiratoryPaths));
      console.log(`Sending ${respiratoryPaths.length} respiratory file path(s) to backend`);
    }
    
    if (structure.cardiacFiles.length > 0) {
      const cardiacPaths = structure.cardiacFiles.map(f => f.path);
      formData.append('cardiac_filenames', JSON.stringify(cardiacPaths));
      console.log(`Sending ${cardiacPaths.length} cardiac file path(s) to backend`);
    }

    try { 
      const response = await fetch('/api/scan-folder-data', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      
      if (response.ok) {
        let metrics = [...(data.metrics || [])];
        
        const hasPPGFiles = structure.hasPPGFiles || 
                           structure.emotibitFiles.some(f => 
                             f.name.includes('_PI.csv') || 
                             f.name.includes('_PR.csv') || 
                             f.name.includes('_PG.csv')
                           );
        
        console.log('PPG Files detected:', hasPPGFiles);
        console.log('Metrics from backend:', metrics);
        
        if (hasPPGFiles && !metrics.includes('HRV')) {
          console.log('Adding HRV to metrics list');
          metrics.push('HRV');
        }
        
        console.log('Final metrics list:', metrics);
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

        const initialMetricSelection = {};
        metrics.forEach(metric => {
          initialMetricSelection[metric] = false;
        });
        console.log('Initializing selectedMetrics with:', Object.keys(initialMetricSelection));
        setSelectedMetrics(initialMetricSelection);
        
        if (data.subject_availability) {
          setSubjectAvailability(data.subject_availability);
        }
        
        if (data.external_data && data.external_data.has_files) {
          console.log('External data files detected:', data.external_data.files_by_subject);
          setExternalFilesBySubject(data.external_data.files_by_subject);
          setsubjectsWithExternal(data.external_data.subjects_with_external);
          setHasExternalFiles(true);
          
          const initialConfigs = {};
          Object.entries(data.external_data.files_by_subject).forEach(([subject, files]) => {
            initialConfigs[subject] = {};
            files.forEach(fileData => {
              initialConfigs[subject][fileData.filename] = {
                selected: true,
                timestampColumn: '',
                timestampFormat: 'seconds',
                dataColumns: [{
                  column: '',
                  displayName: '',
                  dataType: 'continuous',
                  units: ''
                }],
                eventSources: [],
                conditionColumns: []
              };
            });
          });
          setExternalConfigs(initialConfigs);
        } else {
          setHasExternalFiles(false);
          setExternalFilesBySubject({});
        }

        // Process respiratory data detection
        if (data.respiratory_data && data.respiratory_data.has_files) {
          console.log('Respiratory data files detected:', data.respiratory_data.files_by_subject);
          setSubjectsWithRespiratory(data.respiratory_data.subjects_with_respiratory);
          setHasRespiratoryData(true);
          
          // Initialize respiratory configs
          const initialRespConfigs = {};
          data.respiratory_data.subjects_with_respiratory.forEach(subject => {
            initialRespConfigs[subject] = {
              selected: true,
              analyzeRR: true,
              analyzeForce: true
            };
          });
          setRespiratoryConfigs(initialRespConfigs);
        } else {
          setHasRespiratoryData(false);
          setSubjectsWithRespiratory([]);
        }
        // Process cardiac data detection
        if (data.cardiac_data && data.cardiac_data.has_files) {
          console.log('Cardiac data files detected:', data.cardiac_data.files_by_subject);
          setSubjectsWithCardiac(data.cardiac_data.subjects_with_cardiac);
          setHasCardiacData(true);
          
          // Initialize cardiac configs
          const initialCardiacConfigs = {};
          data.cardiac_data.subjects_with_cardiac.forEach(subject => {
            initialCardiacConfigs[subject] = {
              selected: true,
              analyzeHR: true,
              analyzeHRV: true
            };
          });
          setCardiacConfigs(initialCardiacConfigs);
        } else {
          setHasCardiacData(false);
          setSubjectsWithCardiac([]);
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

        const externalMsg = data.external_data && data.external_data.has_files
        ? `, External data files found for ${data.external_data.subjects_with_external.length} subject(s)`
        : '';
        
        if (data.batch_mode && data.subjects && data.subjects.length > 1) {
          const intersectionMsg = `Showing ${data.metrics.length} common metrics, ${data.event_markers.length} common markers, ${data.conditions.length} common conditions across ${data.subjects.length} subjects`;
          setBatchStatusMessage(intersectionMsg);
        }
        setUploadStatus(`Found ${metrics.length} metrics${eventMarkersMsg}${conditionsMsg}${subjectsMsg}${externalMsg}`);

        if (data.subjects && data.subjects.length > 0) {
          const subjectsNeedingParserList = [];
          
          console.log('=== DETAILED DataParser Detection ===');
          console.log('Total subjects:', data.subjects);
          
          data.subjects.forEach(subject => {
            console.log(`\n--- Checking subject: ${subject} ---`);
            
            const subjectEmotibitFiles = structure.emotibitFiles.filter(f => 
              f.path.includes(`/${subject}/emotibit_data/`)
            );
            
            console.log(`  Files found:`, subjectEmotibitFiles.length);
            console.log(`  File names:`, subjectEmotibitFiles.map(f => f.name));
            
            const hasNoEmotibitFiles = subjectEmotibitFiles.length === 0;
            
            console.log(`  hasNoEmotibitFiles: ${hasNoEmotibitFiles}`);
            
            const parsedFileChecks = subjectEmotibitFiles.map(f => {
              const name = f.name;
              const isExcluded = name.includes('_ground_truth.csv') || 
                                name.includes('_biometrics.csv') || 
                                name.includes('_event_markers.csv') ||
                                name.endsWith('.h5');
              const matchesPattern = /_[A-Z]{2,4}\.csv$/.test(name);
              const isParsed = !isExcluded && matchesPattern;
              
              return {
                name: name,
                isExcluded: isExcluded,
                matchesPattern: matchesPattern,
                isParsed: isParsed
              };
            });
            
            console.log(`  Parsed file checks:`, parsedFileChecks);
            
            const hasParsedFiles = parsedFileChecks.some(check => check.isParsed);
            console.log(`  hasParsedFiles: ${hasParsedFiles}`);
            
            const needsParser = !hasParsedFiles && !hasNoEmotibitFiles;
            console.log(`  NEEDS PARSER: ${needsParser}`);
            
            if (needsParser) {
              subjectsNeedingParserList.push(subject);
            }
          });
          
          console.log('\n=== FINAL RESULTS ===');
          console.log('Subjects needing parser:', subjectsNeedingParserList);
          console.log('needsDataParser will be set to:', subjectsNeedingParserList.length > 0);
          console.log('====================\n');
          
          setSubjectsNeedingParser(subjectsNeedingParserList);
          setNeedsDataParser(subjectsNeedingParserList.length > 0);
        }
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
      let metrics = [...(subjectData.metrics || [])];
      
      const subjectHasPPG = subjectData.has_ppg_files || 
                           (fileStructure && fileStructure.hasPPGFiles) ||
                           false;
      
      console.log(`Subject ${subject}: has_ppg_files = ${subjectData.has_ppg_files}, fileStructure.hasPPGFiles = ${fileStructure?.hasPPGFiles}`);
      
      if (subjectHasPPG && !metrics.includes('HRV')) {
        metrics.push('HRV');
        console.log(`Adding HRV for subject ${subject} (has PPG files)`);
      }
      
      setAvailableMetrics(metrics);
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

      let finalMetrics = Array.from(commonMetrics).sort();
      
      const allHavePPG = selectedSubjectsList.every(subject => 
        subjectAvailability[subject]?.has_ppg_files || false
      ) || (fileStructure && fileStructure.hasPPGFiles);
      
      console.log(`Multi-subject: allHavePPG = ${allHavePPG}`);
      
      if (allHavePPG && !finalMetrics.includes('HRV')) {
        finalMetrics.push('HRV');
        console.log('Adding HRV to intersection (all subjects have PPG files)');
      }

      setAvailableMetrics(finalMetrics);
      setAvailableEventMarkers(Array.from(commonMarkers).sort());
      setAvailableConditions(Array.from(commonConditions).sort());
      
      setBatchStatusMessage(
        `📊 ${finalMetrics.length} common metrics, ${commonMarkers.size} common markers, ${commonConditions.size} common conditions across ${selectedSubjectsList.length} subjects`
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
    console.log('=== Opening Configuration Wizard ===');
    console.log('Available metrics:', availableMetrics);
    console.log('Selected metrics:', selectedMetrics);
    console.log('File structure hasPPGFiles:', fileStructure?.hasPPGFiles);
    console.log('Is batch mode:', isBatchMode);
    console.log('====================================');
    setWizardStep(0);
    setShowConfigWizard(true);
  };

  const closeConfigWizard = () => {
    setShowConfigWizard(false);
  };

  const nextWizardStep = () => {
    let maxStep = 8; // Base steps
    if (hasExternalFiles) maxStep++;
    if (hasRespiratoryData) maxStep++;
    if (wizardStep < maxStep) {
      setWizardStep(wizardStep + 1);
    }
  };

  const prevWizardStep = () => {
    if (wizardStep > 0) {
      setWizardStep(wizardStep - 1);
    }
  };

  const goToWizardStep = (step) => {
    setWizardStep(step);
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
    const hasRespiratorySelected = hasRespiratoryData && Object.values(respiratoryConfigs).some(c => c.selected);
    const hasCardiacSelected = hasCardiacData && Object.values(cardiacConfigs).some(c => c.selected);
    const hasExternalSelected = hasExternalFiles && selectedSubjectsList.some(subject => {
      if (subjectsWithExternal.includes(subject) && externalConfigs[subject]) {
        return Object.values(externalConfigs[subject]).some(config => config.selected !== false);
      }
      return false;
    });

    const hasAnyDataSelected = selectedMetricsList.length > 0 || hasRespiratorySelected || hasCardiacSelected || hasExternalSelected;

    if (!hasAnyDataSelected) {
      setUploadStatus('Please select at least one data type to analyze (EmotiBit metrics, respiratory, cardiac, or external data)');
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
    const addedFilePaths = new Set();

    // 1. Event markers
    if (fileStructure.eventMarkersFiles && fileStructure.eventMarkersFiles.length > 0) {
      fileStructure.eventMarkersFiles.forEach(emFile => {
        const belongsToSelected = selectedSubjectsList.some(subject => emFile.path.includes(subject));
        if (belongsToSelected && !addedFilePaths.has(emFile.path)) {
          filesToUpload.push(emFile.file);
          pathsToUpload.push(emFile.path);
          addedFilePaths.add(emFile.path);
        }
      });
    }
    
    // 2. EmotiBit files
    selectedMetricsList.forEach(metric => {
      if (metric === 'HRV') {
        ['PI', 'PR', 'PG'].forEach(ppgType => {
          fileStructure.emotibitFiles.forEach(emFile => {
            const isCorrectType = emFile.name.includes(`_${ppgType}.csv`);
            const belongsToSelected = selectedSubjectsList.some(subject => emFile.path.includes(subject));
            if (isCorrectType && belongsToSelected && !addedFilePaths.has(emFile.path)) {
              filesToUpload.push(emFile.file);
              pathsToUpload.push(emFile.path);
              addedFilePaths.add(emFile.path);
            }
          });
        });
      } else {
        fileStructure.emotibitFiles.forEach(emFile => {
          const isCorrectType = emFile.name.includes(`_${metric}.csv`);
          const belongsToSelected = selectedSubjectsList.some(subject => emFile.path.includes(subject));
          if (isCorrectType && belongsToSelected && !addedFilePaths.has(emFile.path)) {
            filesToUpload.push(emFile.file);
            pathsToUpload.push(emFile.path);
            addedFilePaths.add(emFile.path);
          }
        });
      }
    });

    // 3. Respiratory files
    if (fileStructure.respirationFiles && fileStructure.respirationFiles.length > 0) {
      fileStructure.respirationFiles.forEach(respFile => {
        const belongsToSelected = selectedSubjectsList.some(subject => respFile.path.includes(subject));
        if (belongsToSelected && !addedFilePaths.has(respFile.path)) {
          filesToUpload.push(respFile.file);
          pathsToUpload.push(respFile.path);
          addedFilePaths.add(respFile.path);
        }
      });
    }

    // 4. Cardiac files
    if (fileStructure.cardiacFiles && fileStructure.cardiacFiles.length > 0) {
      fileStructure.cardiacFiles.forEach(cardiacFile => {
        const belongsToSelected = selectedSubjectsList.some(subject => cardiacFile.path.includes(subject));
        if (belongsToSelected && !addedFilePaths.has(cardiacFile.path)) {
          filesToUpload.push(cardiacFile.file);
          pathsToUpload.push(cardiacFile.path);
          addedFilePaths.add(cardiacFile.path);
        }
      });
    }

    // 5. External files (with selection filtering)
    let totalExternalFiles = 0;
    let selectedExternalFiles = 0;
    
    if (hasExternalFiles) {
      selectedSubjectsList.forEach(subject => {
        if (subjectsWithExternal.includes(subject) && externalFilesBySubject[subject]) {
          externalFilesBySubject[subject].forEach(fileData => {
            totalExternalFiles++;
            
            const fileConfig = externalConfigs[subject]?.[fileData.filename];
            const isSelected = fileConfig?.selected !== false;
            
            if (isSelected) {
              selectedExternalFiles++;
              const externalFile = fileStructure.externalFiles.find(f => f.path === fileData.path);
              if (externalFile && !addedFilePaths.has(externalFile.path)) {
                filesToUpload.push(externalFile.file);
                pathsToUpload.push(externalFile.path);
                addedFilePaths.add(externalFile.path);
              }
            }
          });
        }
      });
      
      console.log(`External data: ${selectedExternalFiles}/${totalExternalFiles} files selected`);
    }

    // 6. Append all files to FormData
    console.log(`Uploading ${filesToUpload.length} files for analysis:`, pathsToUpload.map(p => p.split('/').pop()));
    filesToUpload.forEach((file, index) => {
      formData.append('files', file);
      formData.append('paths', pathsToUpload[index]);
    });

    // 7. Add configuration parameters
    formData.append('folder_name', selectedFolder);
    formData.append('selected_metrics', JSON.stringify(selectedMetricsList));
    formData.append('selected_events', JSON.stringify(selectedEvents));
    formData.append('analysis_method', selectedAnalysisMethod);
    formData.append('plot_type', selectedPlotType);
    formData.append('analyze_hrv', JSON.stringify(selectedMetricsList.includes('HRV')));
    formData.append('analysis_type', analysisType);  
    formData.append('student_id', localStorage.getItem('studentId'));
    formData.append('cleaning_enabled', JSON.stringify(cleaningEnabled));
    formData.append('cleaning_stages', JSON.stringify(cleaningStages));

    // 8a. Add external data config
    if (hasExternalFiles) {
      formData.append('external_configs', JSON.stringify(externalConfigs));
      formData.append('has_external_data', 'true');
    }

    // 8b. Add respiratory data config
    if (hasRespiratoryData) {
      formData.append('respiratory_configs', JSON.stringify(respiratoryConfigs));
      formData.append('has_respiratory_data', 'true');
      
      const selectedCount = Object.values(respiratoryConfigs).filter(c => c.selected).length;
      console.log(`Respiratory data: ${selectedCount} subjects selected`);
    }

    // 8c. Add cardiac data config
    if (hasCardiacData) {
      formData.append('cardiac_configs', JSON.stringify(cardiacConfigs));
      formData.append('has_cardiac_data', 'true');
      
      const selectedCount = Object.values(cardiacConfigs).filter(c => c.selected).length;
      console.log(`Cardiac data: ${selectedCount} subjects selected`);
    }

    // 9. Add batch mode parameters
    if (selectedSubjectsList.length > 1) {
      formData.append('selected_subjects', JSON.stringify(selectedSubjectsList));
      formData.append('batch_mode', 'true');
    }

    console.log('=== SENDING TO BACKEND ===');
    console.log('Analysis type:', analysisType);
    console.log('Batch mode:', selectedSubjectsList.length > 1);
    console.log('Selected subjects:', selectedSubjectsList);
    console.log('Selected metrics:', selectedMetricsList);
    console.log('Selected events:', selectedEvents);
    console.log('Analysis method:', selectedAnalysisMethod);
    console.log('Plot type:', selectedPlotType);
    console.log('Has external data:', hasExternalFiles);
    if (hasExternalFiles) {
      console.log('External files selected:', `${selectedExternalFiles}/${totalExternalFiles}`);
    }
    console.log('==========================');
    
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

  const wizardSteps = [
    {
      title: "Browse for Subject Data",
      description: "Click the 'Browse For Subject Data' button to select your experiment folder.",
      details: "The folder should contain subject subfolders with emotibit_data, event markers, and other experimental files. All available subject folders and data files will be detected automatically."
    },
    {
      title: "Review Detected Files",
      description: "After selecting a folder, review the detected files in the left panel.",
      details: "You'll see counts for EmotiBit data files, respiration data, event markers, and SER/transcription files. If multiple subjects are detected, you'll see a summary of common metrics and markers across all subjects."
    },
    {
      title: "Configure Analysis",
      description: "Click the 'Configure Analysis' button to open the configuration wizard.",
      details: "The wizard will guide you through 8 steps to set up your analysis. You can navigate using the Next/Previous buttons or click the breadcrumbs at the top to jump between steps."
    },
    {
      title: "Choose Respiratory Data",
      description: "Select respiratory data collected via the Vernier belt.",
      details: "Data collected by the Vernier Belt include Force and Respiratory Rate values."
    },
    {
      title: "Choose Cardiac Data (Polar H10)",
      description: "Select cardiac data collected by the Polar H10 Belt.",
      details: "Data collectedd by the Polar H10 Belt include HR and HRV."
    }, 
    {
      title: "Select Event Marker",
      description: "Filter analysis window by experimental events. You can add multiple event windows for comparison.",
      details: "Click '+ Add Event Window' to compare multiple events or time periods. Select 'All (entire experiment)' to analyze the full recording. The Union/Intersection toggle works the same as for tags."
    },
    {
      title: "Select Condition Marker",
      description: "Filter analysis window by experimental condition. You can add multiple condition windows for comparison.",
      details: "Click '+ Add Condition Window' to compare multiple events or time periods. Select 'All (entire experiment)' to analyze the full recording. The Union/Intersection toggle works the same as for tags."
    },
    {
      title: "Choose Biometric Tags",
      description: "Select which physiological metrics you want to analyze (HR, EDA, TEMP, etc.).",
      details: "If multiple subjects are selected, use the Union/Intersection toggle to show either all tags across subjects (Union) or only tags common to all subjects (Intersection). HRV will appear automatically if PPG files are detected. Note that selecting the HRV tag will produce HRV tags derived from the PPG data. If cardiac (Polar H10) data is selected, HRV calculated directly on the Polar H10 device will available."
    },
    {
      title: "Choose Respiratory Data",
      description: "Select respiratory data collected via the Vernier belt.",
      details: "Data collected by the Vernier Belt include Force and Respiratory Rate values."
    },
    {
      title: "Choose Cardiac Data (Polar H10)",
      description: "Select cardiac data collected by the Polar H10 Belt.",
      details: "Data collectedd by the Polar H10 Belt include HR and HRV."
    }, 
    {
      title: "Choose External Data",
      description: "Select external data files (e.g., data from other software platforms) to include in the analysis.",
      details: "For each external data file, select the timestamp column, data columns to analyze, and any event/condition markers present in the data. You can customize how each data column is displayed (name, type, units)."
    },
    {
      title: "Select Analysis Type & Subjects",
      description: "Choose between inter-subject (single) or intra-subject (multi) analysis, then select which subjects to include.",
      details: "Inter-subject analyzes one subject's data. Intra-subject compares data across multiple subjects. Check the boxes next to the subjects you want to analyze."
    },
    
{
      title: "Configure Methods",
      description: "Choose your analysis method, and select visualization type.",
      details: "Set conditions for each event window (or select 'All conditions'). Choose an analysis method (Raw Data, Mean, Moving Average, etc.) and plot type (Line Plot, Box Plot, etc.). Note that certain plot types will be filtered out by selecting certain methods"
    },
    {
      title: "Review & Run Analysis",
      description: "Review your configuration in the summary, then click 'Run Analysis' to process your data.",
      details: "The review step will show any configuration issues (like missing files or markers). Fix any issues by navigating back to the relevant step. Once validated, proceed to run your analysis. Results will open in a new tab automatically."
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
              <strong>Cardiac Data:</strong>
              {fileStructure.cardiacFiles.length > 0 ? (
                <span className="file-count">{fileStructure.cardiacFiles.length} file(s)</span>
              ) : (
                <span style={{ color: '#666', fontSize: '14px' }}>⚠️ No files (optional)</span>
              )}
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

            <div className="file-category">
              <strong>External Data Files:</strong>
              {fileStructure.externalFiles.length > 0 ? (
                <span className="file-count">✓ {fileStructure.externalFiles.length} file(s) from {subjectsWithExternal.length} subject(s)</span>
              ) : (
                <span style={{ color: '#666', fontSize: '14px' }}>⚠️ Not found (optional)</span>
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
          <div className="parser-prompt-card">
            {needsDataParser && subjectsNeedingParser.length > 0 ? (
              <>
                <p className="parser-prompt-description warning">
                  ⚠️ The following subject(s) need DataParser processing to generate individual metric files 
                  (HR, EDA, TEMP, etc.):
                </p>
                <div className="subjects-needing-parser">
                  {subjectsNeedingParser.map(subject => (
                    <span key={subject} className="subject-badge warning">{subject}</span>
                  ))}
                </div>
              </>
            ) : (
              <p className="parser-prompt-description">
                Launch the EmotiBit DataParser to process ground truth files and generate individual metric files.
              </p>
            )}
            <button 
              onClick={handleLaunchDataParser}
              className="launch-parser-btn"
            >
              Launch DataParser
            </button>
            {parserLaunchStatus && (
              <div className={`parser-status ${parserLaunchStatus.includes('Error') ? 'error' : 'success'}`}>
                {parserLaunchStatus}
              </div>
            )}
            <input 
              type="file" 
              ref={fileInputRef}
              onChange={handleLSLFileSelect}
              style={{ display: 'none' }}
            />
            <button onClick={() => fileInputRef.current?.click()}>
              Parse Event Markers from LSL File
            </button>
            {parseLSLStatus && (
              <div className={`parser-status ${parseLSLStatus.includes('Error') ? 'error' : 'success'}`}>
                {parseLSLStatus}
              </div>
            )}
          </div>
          <div className="config-action-area">
            <button 
              onClick={openConfigWizard}
              disabled={isScanning || !fileStructure}
              className="config-analysis-btn"
            >
              Configure Analysis
            </button>

            {uploadStatus && (
              <div className={`status-message ${uploadStatus.includes('Error') || uploadStatus.includes('⚠️') ? 'error' : 'success'}`}>
                {uploadStatus}
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
              {['Type', 'Events', 'Conditions', 'Tags', 
                ...(hasRespiratoryData ? ['Respiratory'] : []),
                ...(hasCardiacData ? ['Cardiac'] : []),
                ...(hasExternalFiles ? ['External'] : []),
                'Settings', 'Review', 'Run'].map((label, idx) => (
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
              {/* STEP 0: Type & Subjects */}
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

              {/* STEP 1: Event Markers */}
              {wizardStep === 1 && (
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

              {/* STEP 2: Condition Markers */}
              {wizardStep === 2 && (
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

              {/* STEP 3: Biometric Tags */}
              {wizardStep === 3 && (
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
                    {availableMetrics.length === 0 ? (
                      <div className="no-metrics-message">
                        No biometric metrics detected. Please ensure your folder contains EmotiBit data files.
                      </div>
                    ) : (
                      availableMetrics.map(metric => (
                        <label key={metric} className="tag-checkbox">
                          <input
                            type="checkbox"
                            checked={selectedMetrics[metric] || false}
                            onChange={() => handleMetricToggle(metric)}
                          />
                          <span>{metric}</span>
                        </label>
                      ))
                    )}
                  </div>
                  
                  <div className="selection-summary">
                    {Object.values(selectedMetrics).filter(Boolean).length} tags selected
                  </div>
                </div>
              )}

              {/* STEP 4: Respiratory (conditional) */}
              {hasRespiratoryData && wizardStep === 4 && (
                <div className="wizard-section">
                  <h3 className="wizard-section-title">Respiratory Data Configuration</h3>
                  <p className="wizard-section-description">
                    Configure respiratory (Vernier) data analysis. Select which metrics to analyze for each subject.
                  </p>

                  {subjectsWithRespiratory.filter(subject => selectedSubjects[subject]).length === 0 ? (
                    <div className="no-experiments-message">
                      No respiratory data found for selected subjects.
                    </div>
                  ) : (
                    <div className="respiratory-subjects-panel">
                      {subjectsWithRespiratory.filter(subject => selectedSubjects[subject]).map(subject => (
                        <div key={subject} className="respiratory-subject-card">
                          <h4 className="subject-card-title">{subject}</h4>
                          
                          <div className="respiratory-metrics-selection">
                            <label className="checkbox-label">
                              <input
                                type="checkbox"
                                checked={respiratoryConfigs[subject]?.selected !== false}
                                onChange={(e) => {
                                  setRespiratoryConfigs(prev => ({
                                    ...prev,
                                    [subject]: {
                                      ...prev[subject],
                                      selected: e.target.checked
                                    }
                                  }));
                                }}
                              />
                              <span>Include respiratory data for this subject</span>
                            </label>

                            {respiratoryConfigs[subject]?.selected !== false && (
                              <div className="respiratory-metric-options">
                                <label className="checkbox-label">
                                  <input
                                    type="checkbox"
                                    checked={respiratoryConfigs[subject]?.analyzeRR !== false}
                                    onChange={(e) => {
                                      setRespiratoryConfigs(prev => ({
                                        ...prev,
                                        [subject]: {
                                          ...prev[subject],
                                          analyzeRR: e.target.checked
                                        }
                                      }));
                                    }}
                                  />
                                  <span>Analyze RR (Respiratory Rate)</span>
                                </label>

                                <label className="checkbox-label">
                                  <input
                                    type="checkbox"
                                    checked={respiratoryConfigs[subject]?.analyzeForce !== false}
                                    onChange={(e) => {
                                      setRespiratoryConfigs(prev => ({
                                        ...prev,
                                        [subject]: {
                                          ...prev[subject],
                                          analyzeForce: e.target.checked
                                        }
                                      }));
                                    }}
                                  />
                                  <span>Analyze Force (Respiratory Effort)</span>
                                </label>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="respiratory-info-box" style={{
                    marginTop: '20px',
                    padding: '12px',
                    backgroundColor: '#e8f5e9',
                    border: '1px solid #4caf50',
                    borderRadius: '4px'
                  }}>
                    <strong>💡 Analysis Recommendations:</strong>
                    <ul style={{ marginTop: '8px', marginBottom: '0', paddingLeft: '20px' }}>
                      <li><strong>RR (Respiratory Rate):</strong> Best with Line Plot or Moving Average to visualize breathing patterns</li>
                      <li><strong>Force (Respiratory Effort):</strong> Best with Line Plot to show effort changes over time</li>
                      <li>Both metrics work well with Box Plot for condition comparisons</li>
                    </ul>
                  </div>
                </div>
              )}

              {/* STEP 5: Cardiac (conditional) */}
              {hasCardiacData && wizardStep === (hasRespiratoryData ? 5 : 4) && (
                <div className="wizard-section">
                  <h3 className="wizard-section-title">Cardiac Data Configuration</h3>
                  <p className="wizard-section-description">
                    Configure cardiac (Polar H10) data analysis. Select which metrics to analyze for each subject.
                  </p>

                  {subjectsWithCardiac.filter(subject => selectedSubjects[subject]).length === 0 ? (
                    <div className="no-experiments-message">
                      No cardiac data found for selected subjects.
                    </div>
                  ) : (
                    <div className="respiratory-subjects-panel">
                      {subjectsWithCardiac.filter(subject => selectedSubjects[subject]).map(subject => (
                        <div key={subject} className="respiratory-subject-card">
                          <h4 className="subject-card-title">{subject}</h4>
                          
                          <div className="respiratory-metrics-selection">
                            <label className="checkbox-label">
                              <input
                                type="checkbox"
                                checked={cardiacConfigs[subject]?.selected !== false}
                                onChange={(e) => {
                                  setCardiacConfigs(prev => ({
                                    ...prev,
                                    [subject]: {
                                      ...prev[subject],
                                      selected: e.target.checked
                                    }
                                  }));
                                }}
                              />
                              <span>Include cardiac data for this subject</span>
                            </label>

                            {cardiacConfigs[subject]?.selected !== false && (
                              <div className="respiratory-metric-options">
                                <label className="checkbox-label">
                                  <input
                                    type="checkbox"
                                    checked={cardiacConfigs[subject]?.analyzeHR !== false}
                                    onChange={(e) => {
                                      setCardiacConfigs(prev => ({
                                        ...prev,
                                        [subject]: {
                                          ...prev[subject],
                                          analyzeHR: e.target.checked
                                        }
                                      }));
                                    }}
                                  />
                                  <span>Analyze HR (Heart Rate)</span>
                                </label>

                                <label className="checkbox-label">
                                  <input
                                    type="checkbox"
                                    checked={cardiacConfigs[subject]?.analyzeHRV !== false}
                                    onChange={(e) => {
                                      setCardiacConfigs(prev => ({
                                        ...prev,
                                        [subject]: {
                                          ...prev[subject],
                                          analyzeHRV: e.target.checked
                                        }
                                      }));
                                    }}
                                  />
                                  <span>Analyze HRV (Heart Rate Variability)</span>
                                </label>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="respiratory-info-box" style={{
                    marginTop: '20px',
                    padding: '12px',
                    backgroundColor: '#e3f2fd',
                    border: '1px solid #2196F3',
                    borderRadius: '4px'
                  }}>
                    <strong>💡 Analysis Recommendations:</strong>
                    <ul style={{ marginTop: '8px', marginBottom: '0', paddingLeft: '20px' }}>
                      <li><strong>HR (Heart Rate):</strong> Best with Line Plot for continuous monitoring or Box Plot for comparison</li>
                      <li><strong>HRV (Heart Rate Variability):</strong> Provides stress/recovery insights, best with Mean analysis</li>
                      <li>Polar H10 provides high-accuracy ECG-based measurements</li>
                    </ul>
                  </div>
                </div>
              )}

              {/* STEP 6/7: External Data (conditional) */}
              {hasExternalFiles && wizardStep === (hasRespiratoryData && hasCardiacData ? 6 : hasRespiratoryData || hasCardiacData ? 5 : 4) && (
                <ExternalConfigStep
                  externalFilesBySubject={externalFilesBySubject}
                  selectedSubjects={selectedSubjects}
                  externalConfigs={externalConfigs}
                  setExternalConfigs={setExternalConfigs}
                />
              )}

              {/* STEP 7/8: Analysis Settings (Method + Plot + Cleaning combined) */}
              {wizardStep === (() => {
                let step = 4;
                if (hasRespiratoryData) step++;
                if (hasCardiacData) step++;
                if (hasExternalFiles) step++;
                return step;
              })() && (
                <div className="wizard-section">
                  <h3 className="wizard-section-title">Analysis Settings</h3>
                  <p className="wizard-section-description">
                    Configure how your data will be processed, visualized, and cleaned.
                  </p>

                  {/* Analysis Method */}
                  <div className="settings-subsection">
                    <h4 className="subsection-title">Analysis Method</h4>
                    <p className="subsection-hint">Choose the statistical method for your analysis.</p>

                    {(() => {
                      const { compatibleMethods, selectedSources } = getCompatibleOptions();
                      
                      return (
                        <>
                          {selectedSources.length > 1 && (
                            <div className="compatibility-notice" style={{
                              padding: '10px',
                              backgroundColor: '#e3f2fd',
                              border: '1px solid #2196F3',
                              borderRadius: '4px',
                              marginBottom: '15px',
                              fontSize: '13px'
                            }}>
                              ℹ️ Analyzing {selectedSources.length} data source types together. 
                              Showing methods compatible with: {selectedSources.join(', ')}
                            </div>
                          )}

                          <div className="method-grid">
                            <label className={`method-option ${!compatibleMethods.includes('raw') ? 'disabled' : ''}`}>
                              <input
                                type="radio"
                                name="analysisMethod"
                                value="raw"
                                checked={selectedAnalysisMethod === 'raw'}
                                onChange={(e) => setSelectedAnalysisMethod(e.target.value)}
                                disabled={!compatibleMethods.includes('raw')}
                              />
                              <div className="method-content">
                                <strong>Raw Data</strong>
                                <span>Direct signal values</span>
                                {!compatibleMethods.includes('raw') && (
                                  <span className="incompatible-note">Not compatible</span>
                                )}
                              </div>
                            </label>

                            <label className={`method-option ${!compatibleMethods.includes('mean') ? 'disabled' : ''}`}>
                              <input
                                type="radio"
                                name="analysisMethod"
                                value="mean"
                                checked={selectedAnalysisMethod === 'mean'}
                                onChange={(e) => setSelectedAnalysisMethod(e.target.value)}
                                disabled={!compatibleMethods.includes('mean')}
                              />
                              <div className="method-content">
                                <strong>Mean</strong>
                                <span>Average value</span>
                                {!compatibleMethods.includes('mean') && (
                                  <span className="incompatible-note">Not compatible</span>
                                )}
                              </div>
                            </label>

                            <label className={`method-option ${!compatibleMethods.includes('moving_average') ? 'disabled' : ''}`}>
                              <input
                                type="radio"
                                name="analysisMethod"
                                value="moving_average"
                                checked={selectedAnalysisMethod === 'moving_average'}
                                onChange={(e) => setSelectedAnalysisMethod(e.target.value)}
                                disabled={!compatibleMethods.includes('moving_average')}
                              />
                              <div className="method-content">
                                <strong>Moving Average</strong>
                                <span>Smoothed signal</span>
                                {!compatibleMethods.includes('moving_average') && (
                                  <span className="incompatible-note">Not compatible</span>
                                )}
                              </div>
                            </label>

                            <label className={`method-option ${!compatibleMethods.includes('rmssd') ? 'disabled' : ''}`}>
                              <input
                                type="radio"
                                name="analysisMethod"
                                value="rmssd"
                                checked={selectedAnalysisMethod === 'rmssd'}
                                onChange={(e) => setSelectedAnalysisMethod(e.target.value)}
                                disabled={!compatibleMethods.includes('rmssd')}
                              />
                              <div className="method-content">
                                <strong>RMSSD</strong>
                                <span>Root mean square of successive differences</span>
                                {!compatibleMethods.includes('rmssd') && (
                                  <span className="incompatible-note">Not compatible with selected sources</span>
                                )}
                              </div>
                            </label>
                          </div>
                        </>
                      );
                    })()}
                  </div>

                  {/* Plot Type */}
                  <div className="settings-subsection" style={{ marginTop: '30px' }}>
                    <h4 className="subsection-title">Visualization Type</h4>
                    <p className="subsection-hint">Select how you want to visualize your data.</p>
                    
                    {Object.keys(selectedMetrics).some(m => m === 'HRV' && selectedMetrics[m]) && (
                      <div className="hrv-notice-box" style={{
                        padding: '12px',
                        backgroundColor: '#e3f2fd',
                        border: '1px solid #2196F3',
                        borderRadius: '4px',
                        marginBottom: '15px',
                        fontSize: '14px'
                      }}>
                        <strong>Note:</strong> HRV uses specialized analysis and generates 4 dedicated plots 
                        (PPG Signal, Time Domain, Frequency Domain, Non-linear) regardless of the plot type selected here. 
                        The plot type selection applies to other selected metrics.
                      </div>
                    )}

                    {(() => {
                      const { compatiblePlots } = getCompatibleOptions();
                      const incompatibleCombos = {
                        'mean': ['lineplot', 'scatter', 'boxplot', 'poincare'],
                        'rmssd': ['poincare'],
                        'moving_average': ['poincare']
                      };
                      const methodIncompatible = incompatibleCombos[selectedAnalysisMethod] || [];

                      return (
                        <div className="plot-grid">
                          <label className={`plot-option ${!compatiblePlots.includes('lineplot') || methodIncompatible.includes('lineplot') ? 'disabled' : ''}`}>
                            <input
                              type="radio"
                              name="plotType"
                              value="lineplot"
                              checked={selectedPlotType === 'lineplot'}
                              onChange={(e) => setSelectedPlotType(e.target.value)}
                              disabled={!compatiblePlots.includes('lineplot') || methodIncompatible.includes('lineplot')}
                            />
                            <div className="plot-content">
                              <strong>Line Plot</strong>
                              <span>Time series visualization</span>
                              {!compatiblePlots.includes('lineplot') && (
                                <span className="incompatible-note">Not compatible with selected sources</span>
                              )}
                              {compatiblePlots.includes('lineplot') && methodIncompatible.includes('lineplot') && (
                                <span className="incompatible-note">Requires time-series data</span>
                              )}
                              {compatiblePlots.includes('lineplot') && selectedAnalysisMethod === 'moving_average' && (
                                <span className="recommended-note">✓ Recommended for Moving Average</span>
                              )}
                            </div>
                          </label>

                          <label className={`plot-option ${!compatiblePlots.includes('boxplot') || methodIncompatible.includes('boxplot') ? 'disabled' : ''}`}>
                            <input
                              type="radio"
                              name="plotType"
                              value="boxplot"
                              checked={selectedPlotType === 'boxplot'}
                              onChange={(e) => setSelectedPlotType(e.target.value)}
                              disabled={!compatiblePlots.includes('boxplot') || methodIncompatible.includes('boxplot')}
                            />
                            <div className="plot-content">
                              <strong>Box Plot</strong>
                              <span>Distribution summary</span>
                              {!compatiblePlots.includes('boxplot') && (
                                <span className="incompatible-note">Not compatible with selected sources</span>
                              )}
                              {compatiblePlots.includes('boxplot') && methodIncompatible.includes('boxplot') && (
                                <span className="incompatible-note">Requires distribution data</span>
                              )}
                            </div>
                          </label>

                          <label className={`plot-option ${!compatiblePlots.includes('poincare') || methodIncompatible.includes('poincare') ? 'disabled' : ''}`}>
                            <input
                              type="radio"
                              name="plotType"
                              value="poincare"
                              checked={selectedPlotType === 'poincare'}
                              onChange={(e) => setSelectedPlotType(e.target.value)}
                              disabled={!compatiblePlots.includes('poincare') || methodIncompatible.includes('poincare')}
                            />
                            <div className="plot-content">
                              <strong>Poincaré Plot</strong>
                              <span>HRV analysis</span>
                              {!compatiblePlots.includes('poincare') && (
                                <span className="incompatible-note">Only for EmotiBit data</span>
                              )}
                              {compatiblePlots.includes('poincare') && methodIncompatible.includes('poincare') && (
                                <span className="incompatible-note">Requires raw data</span>
                              )}
                            </div>
                          </label>

                          <label className={`plot-option ${!compatiblePlots.includes('scatter') || methodIncompatible.includes('scatter') ? 'disabled' : ''}`}>
                            <input
                              type="radio"
                              name="plotType"
                              value="scatter"
                              checked={selectedPlotType === 'scatter'}
                              onChange={(e) => setSelectedPlotType(e.target.value)}
                              disabled={!compatiblePlots.includes('scatter') || methodIncompatible.includes('scatter')}
                            />
                            <div className="plot-content">
                              <strong>Scatter Plot</strong>
                              <span>Point distribution</span>
                              {!compatiblePlots.includes('scatter') && (
                                <span className="incompatible-note">Not compatible with selected sources</span>
                              )}
                              {compatiblePlots.includes('scatter') && methodIncompatible.includes('scatter') && (
                                <span className="incompatible-note">Requires multiple data points</span>
                              )}
                            </div>
                          </label>

                          <label className={`plot-option ${!compatiblePlots.includes('barchart') ? 'disabled' : ''}`}>
                            <input
                              type="radio"
                              name="plotType"
                              value="barchart"
                              checked={selectedPlotType === 'barchart'}
                              onChange={(e) => setSelectedPlotType(e.target.value)}
                              disabled={!compatiblePlots.includes('barchart')}
                            />
                            <div className="plot-content">
                              <strong>Bar Chart</strong>
                              <span>Statistical comparison</span>
                              {!compatiblePlots.includes('barchart') && (
                                <span className="incompatible-note">Not compatible with selected sources</span>
                              )}
                              {compatiblePlots.includes('barchart') && selectedAnalysisMethod === 'mean' && (
                                <span className="recommended-note">✓ Recommended for Mean analysis</span>
                              )}
                            </div>
                          </label>
                        </div>
                      );
                    })()}
                    
                    {selectedAnalysisMethod === 'mean' && (
                      <div className="compatibility-hint">
                        💡 <strong>Tip:</strong> Mean analysis works best with the comparison bar chart (automatically generated)
                      </div>
                    )}
                  </div>

                  {/* Data Cleaning */}
                  <div className="settings-subsection" style={{ marginTop: '30px' }}>
                    <h4 className="subsection-title">Data Cleaning</h4>
                    <p className="subsection-hint">
                      Configure automated data cleaning stages to remove artifacts and invalid values from biometric signals.
                    </p>

                    <div className="cleaning-enable-toggle">
                      <label className="checkbox-label">
                        <input
                          type="checkbox"
                          checked={cleaningEnabled}
                          onChange={(e) => setCleaningEnabled(e.target.checked)}
                        />
                        <span className="toggle-text">Enable Data Cleaning</span>
                      </label>
                    </div>

                    {cleaningEnabled && (
                      <div className="cleaning-stages-panel">
                        <h5 className="cleaning-subtitle">Select Cleaning Stages</h5>
                        <p className="cleaning-hint">
                          Choose which cleaning operations to apply. Hover over each option for details.
                        </p>

                        <div className="cleaning-stages-grid">
                          <label className="cleaning-stage-item" title="Remove NaN, infinite values, and negative values (where applicable)">
                            <input
                              type="checkbox"
                              checked={cleaningStages.remove_invalid}
                              onChange={(e) => setCleaningStages({...cleaningStages, remove_invalid: e.target.checked})}
                            />
                            <div className="stage-content">
                              <strong>Remove Invalid Values</strong>
                              <span className="stage-description">NaN, infinity, negatives</span>
                            </div>
                            <span className="recommended-badge">Recommended</span>
                          </label>

                          <label className="cleaning-stage-item" title="Remove values outside physiologically valid ranges (e.g., HR: 30-220 bpm)">
                            <input
                              type="checkbox"
                              checked={cleaningStages.remove_physiological_outliers}
                              onChange={(e) => setCleaningStages({...cleaningStages, remove_physiological_outliers: e.target.checked})}
                            />
                            <div className="stage-content">
                              <strong>Remove Physiological Outliers</strong>
                              <span className="stage-description">Values outside valid ranges</span>
                            </div>
                            <span className="recommended-badge">Recommended</span>
                          </label>

                          <label className="cleaning-stage-item" title="Remove statistical outliers using modified z-score (>3.5 standard deviations)">
                            <input
                              type="checkbox"
                              checked={cleaningStages.remove_statistical_outliers}
                              onChange={(e) => setCleaningStages({...cleaningStages, remove_statistical_outliers: e.target.checked})}
                            />
                            <div className="stage-content">
                              <strong>Remove Statistical Outliers</strong>
                              <span className="stage-description">Beyond 3.5 std deviations</span>
                            </div>
                          </label>

                          <label className="cleaning-stage-item" title="Remove artifacts with unrealistic rate of change (e.g., HR change >30 bpm/sec)">
                            <input
                              type="checkbox"
                              checked={cleaningStages.remove_sudden_changes}
                              onChange={(e) => setCleaningStages({...cleaningStages, remove_sudden_changes: e.target.checked})}
                            />
                            <div className="stage-content">
                              <strong>Remove Sudden Changes</strong>
                              <span className="stage-description">Unrealistic rate of change</span>
                            </div>
                            <span className="recommended-badge">Recommended</span>
                          </label>

                          <label className="cleaning-stage-item" title="Fill small gaps in data using linear interpolation">
                            <input
                              type="checkbox"
                              checked={cleaningStages.interpolate}
                              onChange={(e) => setCleaningStages({...cleaningStages, interpolate: e.target.checked})}
                            />
                            <div className="stage-content">
                              <strong>Interpolate Missing Values</strong>
                              <span className="stage-description">Fill small gaps linearly</span>
                            </div>
                            <span className="recommended-badge">Recommended</span>
                          </label>

                          <label className="cleaning-stage-item" title="Apply median filter to reduce high-frequency noise">
                            <input
                              type="checkbox"
                              checked={cleaningStages.smooth}
                              onChange={(e) => setCleaningStages({...cleaningStages, smooth: e.target.checked})}
                            />
                            <div className="stage-content">
                              <strong>Apply Smoothing Filter</strong>
                              <span className="stage-description">Median filter (window=5)</span>
                            </div>
                          </label>
                        </div>

                        <div className="cleaning-summary-box">
                          <strong>Selected Stages:</strong> {Object.values(cleaningStages).filter(Boolean).length} of 6
                        </div>
                      </div>
                    )}

                    {!cleaningEnabled && (
                      <div className="cleaning-disabled-notice">
                        ℹ️ Data cleaning is disabled. Raw data will be used as-is.
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* STEP 8/9: Review */}
              {wizardStep === (() => {
                let step = 5;
                if (hasRespiratoryData) step++;
                if (hasCardiacData) step++;
                if (hasExternalFiles) step++;
                return step;
              })() && (
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
                      <strong>Event Windows:</strong> {selectedEvents.filter(e => e.event).length} configured
                    </div>
                    <div className="summary-item">
                      <strong>Biometric Tags:</strong> {Object.values(selectedMetrics).filter(Boolean).length} selected
                    </div>
                    {hasRespiratoryData && (
                      <div className="summary-item">
                        <strong>Respiratory Data:</strong> {(() => {
                          const selectedSubjectsWithResp = Object.keys(selectedSubjects)
                            .filter(s => selectedSubjects[s] && subjectsWithRespiratory.includes(s));
                          
                          const enabledCount = selectedSubjectsWithResp.filter(
                            s => respiratoryConfigs[s]?.selected !== false
                          ).length;
                          
                          const metricsInfo = selectedSubjectsWithResp
                            .filter(s => respiratoryConfigs[s]?.selected !== false)
                            .map(s => {
                              const metrics = [];
                              if (respiratoryConfigs[s]?.analyzeRR !== false) metrics.push('RR');
                              if (respiratoryConfigs[s]?.analyzeForce !== false) metrics.push('Force');
                              return metrics.length;
                            })
                            .reduce((a, b) => a + b, 0);
                          
                          return `${enabledCount} subject(s), ${metricsInfo} metric(s)`;
                        })()}
                      </div>
                    )}
                    {hasCardiacData && (
                      <div className="summary-item">
                        <strong>Cardiac Data:</strong> {(() => {
                          const selectedSubjectsWithCardiac = Object.keys(selectedSubjects)
                            .filter(s => selectedSubjects[s] && subjectsWithCardiac.includes(s));
                          
                          const enabledCount = selectedSubjectsWithCardiac.filter(
                            s => cardiacConfigs[s]?.selected !== false
                          ).length;
                          
                          const metricsInfo = selectedSubjectsWithCardiac
                            .filter(s => cardiacConfigs[s]?.selected !== false)
                            .map(s => {
                              const metrics = [];
                              if (cardiacConfigs[s]?.analyzeHR !== false) metrics.push('HR');
                              if (cardiacConfigs[s]?.analyzeHRV !== false) metrics.push('HRV');
                              return metrics.length;
                            })
                            .reduce((a, b) => a + b, 0);
                          
                          return `${enabledCount} subject(s), ${metricsInfo} metric(s)`;
                        })()}
                      </div>
                    )}
                    {hasExternalFiles && (
                      <div className="summary-item">
                        <strong>External Data Files:</strong> {(() => {
                          let selectedCount = 0;
                          let totalCount = 0;
                          
                          Object.keys(selectedSubjects).filter(s => selectedSubjects[s]).forEach(subject => {
                            if (externalConfigs[subject]) {
                              Object.entries(externalConfigs[subject]).forEach(([filename, config]) => {
                                totalCount++;
                                if (config.selected !== false) {
                                  selectedCount++;
                                }
                              });
                            }
                          });
                          
                          return `${selectedCount}/${totalCount} file(s) selected`;
                        })()}
                      </div>
                    )}
                    <div className="summary-item">
                      <strong>Analysis Method:</strong> {selectedAnalysisMethod}
                    </div>
                    <div className="summary-item">
                      <strong>Plot Type:</strong> {selectedPlotType}
                    </div>
                    <div className="summary-item">
                      <strong>Data Cleaning:</strong> {cleaningEnabled ? 
                        `Enabled (${Object.values(cleaningStages).filter(Boolean).length} stages)` : 
                        'Disabled'}
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

              {/* STEP 9/10: Run */}
              {wizardStep === (() => {
                let step = 6;
                if (hasRespiratoryData) step++;
                if (hasCardiacData) step++;
                if (hasExternalFiles) step++;
                return step;
              })() && (
                <div className="wizard-section wizard-final">
                  <p className="wizard-section-description">
                    Click the button below to start processing your data. This may take a few moments.
                  </p>

                  <button
                    onClick={uploadAndAnalyze}
                    disabled={configIssues.length > 0 || isAnalyzing}
                    className="run-analysis-btn"
                  >
                    {isAnalyzing ? '⏳ Analyzing...' : 'Run Analysis'}
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
                Step {wizardStep + 1} of {(() => {
                  let total = 6; // Base: Type, Events, Conditions, Tags, Settings, Review, Run = 7 but 0-indexed so 6
                  if (hasRespiratoryData) total++;
                  if (hasCardiacData) total++;
                  if (hasExternalFiles) total++;
                  return total + 1; // +1 because we're showing "Step X of Y" not 0-indexed
                })()}
              </div>

              <button
                onClick={nextWizardStep}
                disabled={wizardStep === (() => {
                  let max = 6;
                  if (hasRespiratoryData) max++;
                  if (hasCardiacData) max++;
                  if (hasExternalFiles) max++;
                  return max;
                })()}
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
              Back
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