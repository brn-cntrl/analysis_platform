import React, { useState } from 'react';

function PsychoPyConfigStep({
  psychopyFilesBySubject,
  selectedSubjects,
  psychopyConfigs,
  setPsychopyConfigs
}) {
  
  const [expandedFiles, setExpandedFiles] = useState({});

  const toggleFileExpansion = (subject, filename) => {
    const key = `${subject}-${filename}`;
    setExpandedFiles(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const isFileExpanded = (subject, filename) => {
    const key = `${subject}-${filename}`;
    return expandedFiles[key] || false;
  };

  const updateConfig = (subject, filename, field, value) => {
    setPsychopyConfigs(prev => ({
      ...prev,
      [subject]: {
        ...prev[subject],
        [filename]: {
          ...prev[subject][filename],
          [field]: value
        }
      }
    }));
  };

  const addDataColumn = (subject, filename) => {
    const currentConfig = psychopyConfigs[subject][filename];
    updateConfig(subject, filename, 'dataColumns', [
      ...currentConfig.dataColumns,
      {
        column: '',
        displayName: '',
        dataType: 'continuous',
        units: ''
      }
    ]);
  };

  const removeDataColumn = (subject, filename, index) => {
    const currentConfig = psychopyConfigs[subject][filename];
    updateConfig(
      subject,
      filename,
      'dataColumns',
      currentConfig.dataColumns.filter((_, i) => i !== index)
    );
  };

  const updateDataColumn = (subject, filename, index, field, value) => {
    const currentConfig = psychopyConfigs[subject][filename];
    const updated = [...currentConfig.dataColumns];
    updated[index] = { ...updated[index], [field]: value };
    updateConfig(subject, filename, 'dataColumns', updated);
  };

  const addEventSource = (subject, filename) => {
    const currentConfig = psychopyConfigs[subject][filename];
    updateConfig(subject, filename, 'eventSources', [
      ...currentConfig.eventSources,
      {
        column: '',
        labelType: 'direct',
        customPrefix: ''
      }
    ]);
  };

  const removeEventSource = (subject, filename, index) => {
    const currentConfig = psychopyConfigs[subject][filename];
    updateConfig(
      subject,
      filename,
      'eventSources',
      currentConfig.eventSources.filter((_, i) => i !== index)
    );
  };

  const updateEventSource = (subject, filename, index, field, value) => {
    const currentConfig = psychopyConfigs[subject][filename];
    const updated = [...currentConfig.eventSources];
    updated[index] = { ...updated[index], [field]: value };
    updateConfig(subject, filename, 'eventSources', updated);
  };

  const addConditionColumn = (subject, filename) => {
    const currentConfig = psychopyConfigs[subject][filename];
    updateConfig(subject, filename, 'conditionColumns', [
      ...currentConfig.conditionColumns,
      {
        column: '',
        labelType: 'direct',
        customPrefix: ''
      }
    ]);
  };

  const removeConditionColumn = (subject, filename, index) => {
    const currentConfig = psychopyConfigs[subject][filename];
    updateConfig(
      subject,
      filename,
      'conditionColumns',
      currentConfig.conditionColumns.filter((_, i) => i !== index)
    );
  };

  const updateConditionColumn = (subject, filename, index, field, value) => {
    const currentConfig = psychopyConfigs[subject][filename];
    const updated = [...currentConfig.conditionColumns];
    updated[index] = { ...updated[index], [field]: value };
    updateConfig(subject, filename, 'conditionColumns', updated);
  };
  // const updateConditionColumns = (subject, filename, column, isSelected) => {
  //   const currentConfig = psychopyConfigs[subject][filename];
  //   const currentColumns = currentConfig.conditionColumns || [];
    
  //   if (isSelected) {
  //     // Add column if not already present
  //     if (!currentColumns.includes(column)) {
  //       updateConfig(subject, filename, 'conditionColumns', [...currentColumns, column]);
  //     }
  //   } else {
  //     // Remove column
  //     updateConfig(subject, filename, 'conditionColumns', currentColumns.filter(c => c !== column));
  //   }
  // };

  const getFileData = (subject, filename) => {
    const subjectFiles = psychopyFilesBySubject[subject] || [];
    return subjectFiles.find(f => f.filename === filename);
  };

  // const getNumericColumns = (subject, filename) => {
  //   const fileData = getFileData(subject, filename);
  //   if (!fileData) return [];
    
  //   return fileData.columns.filter((col, idx) => 
  //     fileData.column_types[idx] === 'numeric'
  //   );
  // };

  const getUniqueValues = (subject, filename, column) => {
    const fileData = getFileData(subject, filename);
    if (!fileData || !fileData.sample_data || fileData.sample_data.length === 0) return [];
    
    const values = new Set();
    fileData.sample_data.forEach(row => {
      if (row[column] !== undefined && row[column] !== null && row[column] !== '') {
        values.add(String(row[column]));
      }
    });
    return Array.from(values).slice(0, 5);
  };

  // const getConditionCandidates = (subject, filename) => {
  //   const fileData = getFileData(subject, filename);
  //   if (!fileData) return [];
    
  //   const candidates = [];
  //   fileData.columns.forEach((col, idx) => {
  //     const uniqueValues = getUniqueValues(subject, filename, col);
  //     // Only show columns with 2-10 unique values as potential conditions
  //     if (uniqueValues.length >= 2 && uniqueValues.length <= 10) {
  //       candidates.push({
  //         column: col,
  //         valueCount: uniqueValues.length,
  //         sampleValues: uniqueValues
  //       });
  //     }
  //   });
    
  //   return candidates;
  // };

  // Get selected subjects that have PsychoPy data
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
        Configure how to interpret your PsychoPy CSV files for analysis. Click on each file to expand and configure it.
      </p>

      {selectedSubjectsWithPsychopy.map(subject => {
        const files = psychopyFilesBySubject[subject] || [];
        
        return (
          <div key={subject} className="psychopy-subject-section">
            <h4 className="psychopy-subject-title">
              📁 Subject: {subject} ({files.length} file{files.length !== 1 ? 's' : ''})
            </h4>
            
            {files.map(fileData => {
              const isExpanded = isFileExpanded(subject, fileData.filename);
              const config = psychopyConfigs[subject]?.[fileData.filename] || {
                timestampColumn: '',
                timestampFormat: 'seconds',
                dataColumns: [{column: '', displayName: '', dataType: 'continuous', units: ''}],
                eventSources: [],
                conditionColumns: []
              };
              
              return (
                <div key={fileData.filename} className="psychopy-file-card">
                  <div 
                    className="psychopy-file-header"
                    onClick={() => toggleFileExpansion(subject, fileData.filename)}
                  >
                    <span className="psychopy-file-expand-icon">
                      {isExpanded ? '▼' : '▶'}
                    </span>
                    <div className="psychopy-file-info">
                      <span className="psychopy-filename">{fileData.filename}</span>
                      <span className="psychopy-experiment-name">
                        Experiment: {fileData.experiment_name}
                      </span>
                      <span className="psychopy-file-stats">
                        {fileData.columns.length} columns, {fileData.row_count} rows
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
                    <div className="psychopy-file-content">
                      {/* Timestamp Configuration */}
                      <div className="config-subsection">
                        <h5 className="subsection-title">1. Select Timestamp Column (Required)</h5>
                        <p className="subsection-description">
                          Choose the column that contains timing information.
                        </p>
                        
                        <select
                          value={config.timestampColumn}
                          onChange={(e) => updateConfig(subject, fileData.filename, 'timestampColumn', e.target.value)}
                          className="psychopy-select"
                        >
                          <option value="">Select timestamp column...</option>
                          {fileData.columns.map(col => (
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
                                  name={`timestampFormat-${subject}-${fileData.filename}`}
                                  value="seconds"
                                  checked={config.timestampFormat === 'seconds'}
                                  onChange={(e) => updateConfig(subject, fileData.filename, 'timestampFormat', e.target.value)}
                                />
                                <span>Seconds since experiment start</span>
                              </label>
                              <label className="format-option">
                                <input
                                  type="radio"
                                  name={`timestampFormat-${subject}-${fileData.filename}`}
                                  value="milliseconds"
                                  checked={config.timestampFormat === 'milliseconds'}
                                  onChange={(e) => updateConfig(subject, fileData.filename, 'timestampFormat', e.target.value)}
                                />
                                <span>Milliseconds since experiment start</span>
                              </label>
                              <label className="format-option">
                                <input
                                  type="radio"
                                  name={`timestampFormat-${subject}-${fileData.filename}`}
                                  value="unix"
                                  checked={config.timestampFormat === 'unix'}
                                  onChange={(e) => updateConfig(subject, fileData.filename, 'timestampFormat', e.target.value)}
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
                                  onChange={(e) => updateDataColumn(subject, fileData.filename, idx, 'column', e.target.value)}
                                  className="data-column-select"
                                >
                                  <option value="">Select column...</option>
                                  {fileData.columns.map(col => (
                                    <option key={col} value={col}>{col}</option>
                                  ))}
                                </select>

                                <input
                                  type="text"
                                  value={dataCol.displayName}
                                  onChange={(e) => updateDataColumn(subject, fileData.filename, idx, 'displayName', e.target.value)}
                                  placeholder="Display name"
                                  className="display-name-input"
                                />

                                {/* <select
                                  value={dataCol.dataType}
                                  onChange={(e) => updateDataColumn(subject, fileData.filename, idx, 'dataType', e.target.value)}
                                  className="data-type-select"
                                >
                                  <option value="continuous">Continuous</option>
                                  <option value="binary">Binary</option>
                                  <option value="count">Count</option>
                                </select> */}

                                {/* <input
                                  type="text"
                                  value={dataCol.units}
                                  onChange={(e) => updateDataColumn(subject, fileData.filename, idx, 'units', e.target.value)}
                                  placeholder="Units"
                                  className="units-input"
                                /> */}

                                {config.dataColumns.length > 1 && (
                                  <button
                                    onClick={() => removeDataColumn(subject, fileData.filename, idx)}
                                    className="remove-data-column-btn"
                                  >
                                    ×
                                  </button>
                                )}
                              </div>

                              {dataCol.column && (
                                <div className="column-preview">
                                  Sample values: {getUniqueValues(subject, fileData.filename, dataCol.column).join(', ') || 'N/A'}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>

                        <button 
                          onClick={() => addDataColumn(subject, fileData.filename)} 
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
                                  onChange={(e) => updateEventSource(subject, fileData.filename, idx, 'column', e.target.value)}
                                  className="event-source-select"
                                >
                                  <option value="">Select column...</option>
                                  {fileData.columns.map(col => (
                                    <option key={col} value={col}>{col}</option>
                                  ))}
                                </select>

                                <select
                                  value={source.labelType}
                                  onChange={(e) => updateEventSource(subject, fileData.filename, idx, 'labelType', e.target.value)}
                                  className="label-type-select"
                                >
                                  <option value="direct">Use values directly</option>
                                  <option value="prefixed">Add custom prefix</option>
                                </select>

                                {source.labelType === 'prefixed' && (
                                  <input
                                    type="text"
                                    value={source.customPrefix}
                                    onChange={(e) => updateEventSource(subject, fileData.filename, idx, 'customPrefix', e.target.value)}
                                    placeholder="Prefix (e.g., 'task_')"
                                    className="prefix-input"
                                  />
                                )}

                                <button
                                  onClick={() => removeEventSource(subject, fileData.filename, idx)}
                                  className="remove-event-source-btn"
                                >
                                  ×
                                </button>
                              </div>

                              {source.column && (
                                <div className="column-preview">
                                  Will create event markers: {getUniqueValues(subject, fileData.filename, source.column).map(v => 
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
                          onClick={() => addEventSource(subject, fileData.filename)} 
                          className="add-event-source-btn"
                        >
                          + Add Event Source
                        </button>
                      </div>

                      {/* Condition Columns - Same as Event Sources */}
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
                                  onChange={(e) => updateConditionColumn(subject, fileData.filename, idx, 'column', e.target.value)}
                                  className="condition-source-select"
                                >
                                  <option value="">Select column...</option>
                                  {fileData.columns.map(col => (
                                    <option key={col} value={col}>{col}</option>
                                  ))}
                                </select>

                                <select
                                  value={condition.labelType}
                                  onChange={(e) => updateConditionColumn(subject, fileData.filename, idx, 'labelType', e.target.value)}
                                  className="label-type-select"
                                >
                                  <option value="direct">Use values directly</option>
                                  <option value="prefixed">Add custom prefix</option>
                                </select>

                                {condition.labelType === 'prefixed' && (
                                  <input
                                    type="text"
                                    value={condition.customPrefix}
                                    onChange={(e) => updateConditionColumn(subject, fileData.filename, idx, 'customPrefix', e.target.value)}
                                    placeholder="Prefix (e.g., 'cond_')"
                                    className="prefix-input"
                                  />
                                )}

                                <button
                                  onClick={() => removeConditionColumn(subject, fileData.filename, idx)}
                                  className="remove-condition-source-btn"
                                >
                                  ×
                                </button>
                              </div>

                              {condition.column && (
                                <div className="column-preview">
                                  Will create conditions: {getUniqueValues(subject, fileData.filename, condition.column).map(v => 
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
                          onClick={() => addConditionColumn(subject, fileData.filename)} 
                          className="add-condition-source-btn"
                        >
                          + Add Condition Column
                        </button>

                        <div className="selection-summary">
                          {config.conditionColumns.filter(cc => cc.column).length} condition column(s) selected
                        </div>
                      </div>

                      {/* Configuration Summary for this file */}
                      <div className="file-config-summary-box">
                        <h5 className="summary-title">File Configuration Summary</h5>
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
          </div>
        );
      })}

      {/* Overall Configuration Summary */}
      <div className="psychopy-overall-summary">
        <h4 className="summary-title">Overall PsychoPy Configuration</h4>
        <div className="summary-content">
          {selectedSubjectsWithPsychopy.map(subject => {
            const files = psychopyFilesBySubject[subject] || [];
            const configuredCount = files.filter(f => {
              const config = psychopyConfigs[subject]?.[f.filename];
              return config?.timestampColumn && config?.dataColumns.some(dc => dc.column);
            }).length;
            
            return (
              <div key={subject} className="subject-summary-item">
                <strong>{subject}:</strong> {configuredCount} of {files.length} file(s) configured
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default PsychoPyConfigStep;