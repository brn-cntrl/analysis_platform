import React, { useState, useEffect, useMemo } from 'react';

function PsychoPyConfigStep({
  psychopyFilesBySubject,
  selectedSubjects,
  psychopyConfigs,
  setPsychopyConfigs
}) {
  
  const [expandedExperiments, setExpandedExperiments] = useState({});
  const [includePsychopy, setIncludePsychopy] = useState(false);
  const [selectedExperimentTypes, setSelectedExperimentTypes] = useState({});
  const [psychopyMode, setPsychopyMode] = useState('union');

  const deriveExperimentType = (fileData) => {
    const expName = (fileData?.experiment_name || '').trim();
    if (expName && expName.toLowerCase() !== 'unknown') return expName;
    const name = (fileData?.filename || '').toLowerCase();
    if (name.includes('sart')) return 'SART';
    if (name.includes('prs')) return 'PRS';
    const base = (fileData?.filename || '').replace(/\.csv$/i, '');
    const tokens = base.split(/[_\-\s]+/).filter(Boolean);
    const candidate = tokens.find(t => /[A-Za-z]{3,}/.test(t)) || tokens[tokens.length - 1] || 'Unknown';
    return candidate;
  };

  // Build a map of experiment types to subjects/files
  const experimentTypeMap = useMemo(() => {
    const map = {};
    const selectedSubjectsList = Object.keys(selectedSubjects).filter(s => selectedSubjects[s]);
    
    selectedSubjectsList.forEach(subject => {
      const files = psychopyFilesBySubject[subject] || [];
      files.forEach(fileData => {
        const expType = deriveExperimentType(fileData);
        if (!map[expType]) {
          map[expType] = {
            subjects: new Set(),
            filesBySubject: {}
          };
        }
        map[expType].subjects.add(subject);
        if (!map[expType].filesBySubject[subject]) {
          map[expType].filesBySubject[subject] = [];
        }
        map[expType].filesBySubject[subject].push(fileData);
      });
    });
    
    // Convert sets to arrays for easier rendering
    Object.keys(map).forEach(expType => {
      map[expType].subjects = Array.from(map[expType].subjects);
    });
    
    return map;
  }, [psychopyFilesBySubject, selectedSubjects]);

  // Filter experiment types based on union/intersection mode
  const availableExperimentTypes = useMemo(() => {
    const selectedSubjectsList = Object.keys(selectedSubjects).filter(s => selectedSubjects[s]);
    
    if (selectedSubjectsList.length === 0) return [];
    
    const experimentTypes = Object.keys(experimentTypeMap);
    
    if (psychopyMode === 'intersection') {
      // Only show experiment types that ALL selected subjects have
      return experimentTypes.filter(expType => {
        const data = experimentTypeMap[expType];
        return selectedSubjectsList.every(subject => data.subjects.includes(subject));
      });
    } else {
      // Union: show all
      return experimentTypes;
    }
  }, [experimentTypeMap, psychopyMode, selectedSubjects]);

  // Initialize from existing configs
  useEffect(() => {
    const initial = {};
    Object.keys(experimentTypeMap).forEach(expType => {
      const data = experimentTypeMap[expType];
      const firstSubject = data.subjects[0];
      const firstFile = data.filesBySubject[firstSubject]?.[0];
      
      if (firstFile && psychopyConfigs?.[firstSubject]?.[firstFile.filename]?.selected) {
        initial[expType] = true;
        setIncludePsychopy(true);
      }
    });
    
    if (Object.keys(initial).length > 0) {
      setSelectedExperimentTypes(initial);
    }
  }, [experimentTypeMap, psychopyConfigs]);

  const toggleExperimentExpansion = (expType) => {
    setExpandedExperiments(prev => ({
      ...prev,
      [expType]: !prev[expType]
    }));
  };

  const isExperimentExpanded = (expType) => {
    return expandedExperiments[expType] || false;
  };

  const setExperimentTypeSelected = (expType, selected) => {
    setSelectedExperimentTypes(prev => ({
      ...prev,
      [expType]: selected
    }));
    
    // Update configs for all subjects/files of this experiment type
    const data = experimentTypeMap[expType];
    data.subjects.forEach(subject => {
      const files = data.filesBySubject[subject] || [];
      files.forEach(fileData => {
        updateConfig(subject, fileData.filename, 'selected', selected);
      });
    });
  };

  const isExperimentTypeSelected = (expType) => {
    return !!selectedExperimentTypes[expType];
  };

  // Get a sample file for showing configuration options
  const getSampleFile = (expType) => {
    const data = experimentTypeMap[expType];
    if (!data) return null;
    const firstSubject = data.subjects[0];
    return data.filesBySubject[firstSubject]?.[0];
  };

  // Get the current config for an experiment type (using first subject's config as template)
  const getExperimentConfig = (expType) => {
    const data = experimentTypeMap[expType];
    if (!data) return getDefaultConfig();
    
    const firstSubject = data.subjects[0];
    const firstFile = data.filesBySubject[firstSubject]?.[0];
    
    if (!firstFile) return getDefaultConfig();
    
    return psychopyConfigs?.[firstSubject]?.[firstFile.filename] || getDefaultConfig();
  };

  const getDefaultConfig = () => ({
    timestampColumn: '',
    timestampFormat: 'seconds',
    dataColumns: [{ column: '', displayName: '', dataType: 'continuous', units: '' }],
    eventSources: [],
    conditionColumns: [],
    selected: false
  });

  // Update config for a specific subject/file
  const updateConfig = (subject, filename, field, value) => {
    setPsychopyConfigs(prev => {
      const prevSubject = prev?.[subject] || {};
      const prevFileCfg = prevSubject?.[filename] || getDefaultConfig();
      return {
        ...prev,
        [subject]: {
          ...prevSubject,
          [filename]: {
            ...prevFileCfg,
            [field]: value
          }
        }
      };
    });
  };

  // Update config for all files of an experiment type
  const updateExperimentConfig = (expType, field, value) => {
    const data = experimentTypeMap[expType];
    data.subjects.forEach(subject => {
      const files = data.filesBySubject[subject] || [];
      files.forEach(fileData => {
        updateConfig(subject, fileData.filename, field, value);
      });
    });
  };

  const addDataColumn = (expType) => {
    const currentConfig = getExperimentConfig(expType);
    updateExperimentConfig(expType, 'dataColumns', [
      ...currentConfig.dataColumns,
      { column: '', displayName: '', dataType: 'continuous', units: '' }
    ]);
  };

  const removeDataColumn = (expType, index) => {
    const currentConfig = getExperimentConfig(expType);
    updateExperimentConfig(
      expType,
      'dataColumns',
      currentConfig.dataColumns.filter((_, i) => i !== index)
    );
  };

  const updateDataColumn = (expType, index, field, value) => {
    const currentConfig = getExperimentConfig(expType);
    const updated = [...currentConfig.dataColumns];
    updated[index] = { ...updated[index], [field]: value };
    updateExperimentConfig(expType, 'dataColumns', updated);
  };

  const addEventSource = (expType) => {
    const currentConfig = getExperimentConfig(expType);
    updateExperimentConfig(expType, 'eventSources', [
      ...currentConfig.eventSources,
      { column: '', labelType: 'direct', customPrefix: '' }
    ]);
  };

  const removeEventSource = (expType, index) => {
    const currentConfig = getExperimentConfig(expType);
    updateExperimentConfig(
      expType,
      'eventSources',
      currentConfig.eventSources.filter((_, i) => i !== index)
    );
  };

  const updateEventSource = (expType, index, field, value) => {
    const currentConfig = getExperimentConfig(expType);
    const updated = [...currentConfig.eventSources];
    updated[index] = { ...updated[index], [field]: value };
    updateExperimentConfig(expType, 'eventSources', updated);
  };

  const addConditionColumn = (expType) => {
    const currentConfig = getExperimentConfig(expType);
    updateExperimentConfig(expType, 'conditionColumns', [
      ...currentConfig.conditionColumns,
      { column: '', labelType: 'direct', customPrefix: '' }
    ]);
  };

  const removeConditionColumn = (expType, index) => {
    const currentConfig = getExperimentConfig(expType);
    updateExperimentConfig(
      expType,
      'conditionColumns',
      currentConfig.conditionColumns.filter((_, i) => i !== index)
    );
  };

  const updateConditionColumn = (expType, index, field, value) => {
    const currentConfig = getExperimentConfig(expType);
    const updated = [...currentConfig.conditionColumns];
    updated[index] = { ...updated[index], [field]: value };
    updateExperimentConfig(expType, 'conditionColumns', updated);
  };

  const getUniqueValues = (expType, column) => {
    const sampleFile = getSampleFile(expType);
    if (!sampleFile || !sampleFile.sample_data || sampleFile.sample_data.length === 0) return [];
    
    const values = new Set();
    sampleFile.sample_data.forEach(row => {
      if (row[column] !== undefined && row[column] !== null && row[column] !== '') {
        values.add(String(row[column]));
      }
    });
    return Array.from(values).slice(0, 5);
  };

  const selectedSubjectsWithPsychopy = Object.keys(selectedSubjects)
    .filter(s => selectedSubjects[s] && psychopyFilesBySubject[s]);

  if (selectedSubjectsWithPsychopy.length === 0) {
    return (
      <div className="wizard-section psychopy-config-section">
        <h3 className="wizard-section-title">PsychoPy Data Configuration</h3>
        <p className="wizard-section-description">
          No PsychoPy data found for the selected subjects.
        </p>
      </div>
    );
  }

  return (
    <div className="wizard-section psychopy-config-section">
      <h3 className="wizard-section-title">PsychoPy Data Configuration</h3>
      <p className="wizard-section-description">
        Configure how to interpret your PsychoPy CSV files for analysis. Select experiment types and configure them once to apply to all subjects.
      </p>

      {/* Include PsychoPy files toggle */}
      <div className="psychopy-include-toggle">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={includePsychopy}
            onChange={(e) => setIncludePsychopy(e.target.checked)}
          />
          <span>Include PsychoPy files</span>
        </label>
      </div>

      {includePsychopy && (
        <>
          {/* Union/Intersection Mode Toggle */}
          {selectedSubjectsWithPsychopy.length > 1 && (
            <div className="psychopy-mode-toggle">
              <label className="mode-option">
                <input
                  type="radio"
                  name="psychopyMode"
                  value="union"
                  checked={psychopyMode === 'union'}
                  onChange={(e) => setPsychopyMode(e.target.value)}
                />
                <span>Union (all experiment types)</span>
              </label>
              <label className="mode-option">
                <input
                  type="radio"
                  name="psychopyMode"
                  value="intersection"
                  checked={psychopyMode === 'intersection'}
                  onChange={(e) => setPsychopyMode(e.target.value)}
                />
                <span>Intersection (common only)</span>
              </label>
            </div>
          )}

          {/* Experiment Type Selection */}
          <div className="psychopy-selection-panel">
            <h4 className="selection-title">Select Experiment Types to Include</h4>
            
            <div className="experiment-type-checkboxes">
              {availableExperimentTypes.length === 0 ? (
                <div className="no-experiments-message">
                  No common experiment types found across selected subjects.
                </div>
              ) : (
                availableExperimentTypes.map(expType => {
                  const data = experimentTypeMap[expType];
                  const totalSubjects = selectedSubjectsWithPsychopy.length;
                  const availableForSubjects = data.subjects.length;
                  
                  return (
                    <label key={expType} className="experiment-checkbox-item">
                      <input
                        type="checkbox"
                        checked={isExperimentTypeSelected(expType)}
                        onChange={(e) => setExperimentTypeSelected(expType, e.target.checked)}
                      />
                      <span className="experiment-name">{expType}</span>
                      {psychopyMode === 'union' && totalSubjects > 1 && (
                        <span className="subject-availability">
                          ({availableForSubjects}/{totalSubjects} subjects)
                        </span>
                      )}
                    </label>
                  );
                })
              )}
            </div>
            
            <div className="selection-hint">
              Tip: Selected experiment types will be configured once and applied to all applicable subjects.
            </div>
          </div>

          {/* Configuration for Selected Experiment Types */}
          {Object.keys(selectedExperimentTypes).filter(exp => selectedExperimentTypes[exp]).map(expType => {
            const isExpanded = isExperimentExpanded(expType);
            const config = getExperimentConfig(expType);
            const sampleFile = getSampleFile(expType);
            const data = experimentTypeMap[expType];
            
            if (!sampleFile) return null;
            
            return (
              <div key={expType} className="psychopy-experiment-card">
                <div 
                  className="psychopy-experiment-header"
                  onClick={() => toggleExperimentExpansion(expType)}
                >
                  <span className="psychopy-experiment-expand-icon">
                    {isExpanded ? '▼' : '▶'}
                  </span>
                  <div className="psychopy-experiment-info">
                    <span className="psychopy-experiment-name">{expType}</span>
                    <span className="psychopy-experiment-subjects">
                      Applies to: {data.subjects.join(', ')}
                    </span>
                    <span className="psychopy-experiment-stats">
                      {sampleFile.columns.length} columns, {sampleFile.row_count} rows (sample)
                    </span>
                  </div>
                  <div className="psychopy-config-status">
                    {config.timestampColumn && config.dataColumns.some(dc => dc.column) ? (
                      <span className="status-configured">✓ Configured</span>
                    ) : (
                      <span className="status-not-configured">⚠ Not configured</span>
                    )}
                  </div>
                </div>

                {isExpanded && (
                  <div className="psychopy-experiment-content">
                    {/* Timestamp Configuration */}
                    <div className="config-subsection">
                      <h5 className="subsection-title">1. Select Timestamp Column (Required)</h5>
                      <p className="subsection-description">
                        Choose the column that contains timing information.
                      </p>
                      
                      <select
                        value={config.timestampColumn}
                        onChange={(e) => updateExperimentConfig(expType, 'timestampColumn', e.target.value)}
                        className="psychopy-select"
                      >
                        <option value="">Select timestamp column...</option>
                        {sampleFile.columns.map(col => (
                          <option key={col} value={col}>{col}</option>
                        ))}
                      </select>

                      {config.timestampColumn && (
                        <div className="timestamp-format-selection">
                          <label className="format-label">Timestamp Format:</label>
                          <div className="format-options">
                            <label className="format-option">
                              <input
                                type="radio"
                                name={`timestampFormat-${expType}`}
                                value="seconds"
                                checked={config.timestampFormat === 'seconds'}
                                onChange={(e) => updateExperimentConfig(expType, 'timestampFormat', e.target.value)}
                              />
                              <span>Seconds since experiment start</span>
                            </label>
                            <label className="format-option">
                              <input
                                type="radio"
                                name={`timestampFormat-${expType}`}
                                value="milliseconds"
                                checked={config.timestampFormat === 'milliseconds'}
                                onChange={(e) => updateExperimentConfig(expType, 'timestampFormat', e.target.value)}
                              />
                              <span>Milliseconds since experiment start</span>
                            </label>
                            <label className="format-option">
                              <input
                                type="radio"
                                name={`timestampFormat-${expType}`}
                                value="unix"
                                checked={config.timestampFormat === 'unix'}
                                onChange={(e) => updateExperimentConfig(expType, 'timestampFormat', e.target.value)}
                              />
                              <span>Unix timestamp</span>
                            </label>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Data Columns Configuration */}
                    <div className="config-subsection">
                      <h5 className="subsection-title">2. Select Data Columns (Required)</h5>
                      <p className="subsection-description">
                        Choose columns containing measurements to visualize and analyze.
                      </p>

                      <div className="data-columns-list">
                        {config.dataColumns.map((dataCol, idx) => (
                          <div key={idx} className="data-column-config">
                            <div className="data-column-row">
                              <select
                                value={dataCol.column}
                                onChange={(e) => updateDataColumn(expType, idx, 'column', e.target.value)}
                                className="data-column-select"
                              >
                                <option value="">Select column...</option>
                                {sampleFile.columns.map(col => (
                                  <option key={col} value={col}>{col}</option>
                                ))}
                              </select>

                              <input
                                type="text"
                                value={dataCol.displayName}
                                onChange={(e) => updateDataColumn(expType, idx, 'displayName', e.target.value)}
                                placeholder="Display name"
                                className="display-name-input"
                              />

                              {config.dataColumns.length > 1 && (
                                <button
                                  onClick={() => removeDataColumn(expType, idx)}
                                  className="remove-data-column-btn"
                                >
                                  ×
                                </button>
                              )}
                            </div>

                            {dataCol.column && (
                              <div className="column-preview">
                                Sample values: {getUniqueValues(expType, dataCol.column).join(', ') || 'N/A'}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>

                      <button 
                        onClick={() => addDataColumn(expType)} 
                        className="add-data-column-btn"
                      >
                        + Add Data Column
                      </button>

                      <div className="selection-summary">
                        {config.dataColumns.filter(dc => dc.column).length} data column(s) selected
                      </div>
                    </div>

                    {/* Event Marker Sources */}
                    <div className="config-subsection">
                      <h5 className="subsection-title">3. Map Event Marker Sources (Optional)</h5>
                      <p className="subsection-description">
                        Select columns whose values indicate experimental procedures.
                      </p>

                      <div className="event-sources-list">
                        {config.eventSources.map((source, idx) => (
                          <div key={idx} className="event-source-config">
                            <div className="event-source-row">
                              <select
                                value={source.column}
                                onChange={(e) => updateEventSource(expType, idx, 'column', e.target.value)}
                                className="event-source-select"
                              >
                                <option value="">Select column...</option>
                                {sampleFile.columns.map(col => (
                                  <option key={col} value={col}>{col}</option>
                                ))}
                              </select>

                              <select
                                value={source.labelType}
                                onChange={(e) => updateEventSource(expType, idx, 'labelType', e.target.value)}
                                className="label-type-select"
                              >
                                <option value="direct">Use values directly</option>
                                <option value="prefixed">Add custom prefix</option>
                              </select>

                              {source.labelType === 'prefixed' && (
                                <input
                                  type="text"
                                  value={source.customPrefix}
                                  onChange={(e) => updateEventSource(expType, idx, 'customPrefix', e.target.value)}
                                  placeholder="Prefix (e.g., 'task_')"
                                  className="prefix-input"
                                />
                              )}

                              <button
                                onClick={() => removeEventSource(expType, idx)}
                                className="remove-event-source-btn"
                              >
                                ×
                              </button>
                            </div>

                            {source.column && (
                              <div className="column-preview">
                                Will create event markers: {getUniqueValues(expType, source.column).map(v => 
                                  source.labelType === 'prefixed' && source.customPrefix 
                                    ? `${source.customPrefix}${v}` 
                                    : v
                                ).join(', ')}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>

                      <button 
                        onClick={() => addEventSource(expType)} 
                        className="add-event-source-btn"
                      >
                        + Add Event Source
                      </button>
                    </div>

                    {/* Condition Columns */}
                    <div className="config-subsection">
                      <h5 className="subsection-title">4. Map Condition Columns (Optional)</h5>
                      <p className="subsection-description">
                        Select columns representing experimental conditions for grouping/filtering.
                      </p>

                      <div className="condition-sources-list">
                        {config.conditionColumns.map((condition, idx) => (
                          <div key={idx} className="condition-source-config">
                            <div className="condition-source-row">
                              <select
                                value={condition.column}
                                onChange={(e) => updateConditionColumn(expType, idx, 'column', e.target.value)}
                                className="condition-source-select"
                              >
                                <option value="">Select column...</option>
                                {sampleFile.columns.map(col => (
                                  <option key={col} value={col}>{col}</option>
                                ))}
                              </select>

                              <select
                                value={condition.labelType}
                                onChange={(e) => updateConditionColumn(expType, idx, 'labelType', e.target.value)}
                                className="label-type-select"
                              >
                                <option value="direct">Use values directly</option>
                                <option value="prefixed">Add custom prefix</option>
                              </select>

                              {condition.labelType === 'prefixed' && (
                                <input
                                  type="text"
                                  value={condition.customPrefix}
                                  onChange={(e) => updateConditionColumn(expType, idx, 'customPrefix', e.target.value)}
                                  placeholder="Prefix (e.g., 'cond_')"
                                  className="prefix-input"
                                />
                              )}

                              <button
                                onClick={() => removeConditionColumn(expType, idx)}
                                className="remove-condition-source-btn"
                              >
                                ×
                              </button>
                            </div>

                            {condition.column && (
                              <div className="column-preview">
                                Will create conditions: {getUniqueValues(expType, condition.column).map(v => 
                                  condition.labelType === 'prefixed' && condition.customPrefix 
                                    ? `${condition.customPrefix}${v}` 
                                    : v
                                ).join(', ')}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>

                      <button 
                        onClick={() => addConditionColumn(expType)} 
                        className="add-condition-source-btn"
                      >
                        + Add Condition Column
                      </button>

                      <div className="selection-summary">
                        {config.conditionColumns.filter(cc => cc.column).length} condition column(s) selected
                      </div>
                    </div>

                    {/* Configuration Summary for this experiment type */}
                    <div className="file-config-summary-box">
                      <h5 className="summary-title">Configuration Summary</h5>
                      <div className="summary-grid">
                        <div className="summary-item">
                          <strong>Timestamp:</strong> {config.timestampColumn || 'Not selected'}
                          {config.timestampColumn && ` (${config.timestampFormat})`}
                        </div>
                        <div className="summary-item">
                          <strong>Data Columns:</strong> {config.dataColumns.filter(dc => dc.column).length}
                        </div>
                        <div className="summary-item">
                          <strong>Event Sources:</strong> {config.eventSources.filter(es => es.column).length}
                        </div>
                        <div className="summary-item">
                          <strong>Condition Filters:</strong> {(config.conditionColumns || []).length}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}

          {/* Overall Configuration Summary */}
          <div className="psychopy-overall-summary">
            <h4 className="summary-title">Overall PsychoPy Configuration</h4>
            <div className="summary-content">
              <div className="summary-stats">
                <strong>Selected experiment types:</strong> {Object.values(selectedExperimentTypes).filter(Boolean).length}
              </div>
              {Object.keys(selectedExperimentTypes).filter(exp => selectedExperimentTypes[exp]).map(expType => {
                const config = getExperimentConfig(expType);
                const data = experimentTypeMap[expType];
                const isConfigured = config.timestampColumn && config.dataColumns.some(dc => dc.column);
                
                return (
                  <div key={expType} className="experiment-summary-item">
                    <strong>{expType}:</strong>
                    <span> {data.subjects.length} subject(s)</span>
                    <span className={isConfigured ? "status-ok" : "status-warning"}>
                      {isConfigured ? " ✓ Configured" : " ⚠ Not configured"}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default PsychoPyConfigStep;