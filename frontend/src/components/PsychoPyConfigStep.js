import React from 'react';

function PsychoPyConfigStep({
  psychopyColumns,
  psychopyColumnTypes,
  psychopySampleData,
  psychopyConfig,
  setPsychopyConfig
}) {
  
  const addDataColumn = () => {
    setPsychopyConfig(prev => ({
      ...prev,
      dataColumns: [...prev.dataColumns, {
        column: '',
        displayName: '',
        dataType: 'continuous',
        units: ''
      }]
    }));
  };

  const removeDataColumn = (index) => {
    setPsychopyConfig(prev => ({
      ...prev,
      dataColumns: prev.dataColumns.filter((_, i) => i !== index)
    }));
  };

  const updateDataColumn = (index, field, value) => {
    setPsychopyConfig(prev => {
      const updated = [...prev.dataColumns];
      updated[index] = { ...updated[index], [field]: value };
      return { ...prev, dataColumns: updated };
    });
  };

  const addEventSource = () => {
    setPsychopyConfig(prev => ({
      ...prev,
      eventSources: [...prev.eventSources, {
        column: '',
        labelType: 'direct',
        customPrefix: ''
      }]
    }));
  };

  const removeEventSource = (index) => {
    setPsychopyConfig(prev => ({
      ...prev,
      eventSources: prev.eventSources.filter((_, i) => i !== index)
    }));
  };

  const updateEventSource = (index, field, value) => {
    setPsychopyConfig(prev => {
      const updated = [...prev.eventSources];
      updated[index] = { ...updated[index], [field]: value };
      return { ...prev, eventSources: updated };
    });
  };

  const toggleConditionColumn = (column) => {
    setPsychopyConfig(prev => ({
      ...prev,
      conditionColumns: prev.conditionColumns.includes(column)
        ? prev.conditionColumns.filter(c => c !== column)
        : [...prev.conditionColumns, column]
    }));
  };

  const numericColumns = psychopyColumns.filter((col, idx) => 
    psychopyColumnTypes[idx] === 'numeric'
  );

  const getUniqueValues = (column) => {
    if (!psychopySampleData || psychopySampleData.length === 0) return [];
    const values = new Set();
    psychopySampleData.forEach(row => {
      if (row[column] !== undefined && row[column] !== null && row[column] !== '') {
        values.add(String(row[column]));
      }
    });
    return Array.from(values).slice(0, 5);
  };

  return (
    <div className="wizard-section psychopy-config-section">
      <h3 className="wizard-section-title">PsychoPy Data Configuration</h3>
      <p className="wizard-section-description">
        Configure how to interpret your PsychoPy CSV data for analysis.
      </p>

      {/* Timestamp Selection */}
      <div className="config-subsection">
        <h4 className="subsection-title">1. Select Timestamp Column (Required)</h4>
        <p className="subsection-description">
          Choose the column that contains timing information for your trials.
        </p>
        
        <select
          value={psychopyConfig.timestampColumn}
          onChange={(e) => setPsychopyConfig(prev => ({
            ...prev,
            timestampColumn: e.target.value
          }))}
          className="psychopy-select"
        >
          <option value="">Select timestamp column...</option>
          {numericColumns.map(col => (
            <option key={col} value={col}>{col}</option>
          ))}
        </select>

        {psychopyConfig.timestampColumn && (
          <div className="timestamp-format-selection">
            <label className="format-label">Timestamp Format:</label>
            <div className="format-options">
              <label className="format-option">
                <input
                  type="radio"
                  name="timestampFormat"
                  value="seconds"
                  checked={psychopyConfig.timestampFormat === 'seconds'}
                  onChange={(e) => setPsychopyConfig(prev => ({
                    ...prev,
                    timestampFormat: e.target.value
                  }))}
                />
                <span>Seconds since experiment start</span>
              </label>
              <label className="format-option">
                <input
                  type="radio"
                  name="timestampFormat"
                  value="milliseconds"
                  checked={psychopyConfig.timestampFormat === 'milliseconds'}
                  onChange={(e) => setPsychopyConfig(prev => ({
                    ...prev,
                    timestampFormat: e.target.value
                  }))}
                />
                <span>Milliseconds since experiment start</span>
              </label>
              <label className="format-option">
                <input
                  type="radio"
                  name="timestampFormat"
                  value="unix"
                  checked={psychopyConfig.timestampFormat === 'unix'}
                  onChange={(e) => setPsychopyConfig(prev => ({
                    ...prev,
                    timestampFormat: e.target.value
                  }))}
                />
                <span>Unix timestamp</span>
              </label>
            </div>
          </div>
        )}
      </div>

      {/* Data Columns Selection */}
      <div className="config-subsection">
        <h4 className="subsection-title">2. Select Data Columns (Required)</h4>
        <p className="subsection-description">
          Choose which columns contain the measurements you want to visualize and analyze.
        </p>

        <div className="data-columns-list">
          {psychopyConfig.dataColumns.map((dataCol, idx) => (
            <div key={idx} className="data-column-config">
              <div className="data-column-row">
                <select
                  value={dataCol.column}
                  onChange={(e) => updateDataColumn(idx, 'column', e.target.value)}
                  className="data-column-select"
                >
                  <option value="">Select column...</option>
                  {psychopyColumns.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>

                <input
                  type="text"
                  value={dataCol.displayName}
                  onChange={(e) => updateDataColumn(idx, 'displayName', e.target.value)}
                  placeholder="Display name (e.g., 'Reaction Time')"
                  className="display-name-input"
                />

                <select
                  value={dataCol.dataType}
                  onChange={(e) => updateDataColumn(idx, 'dataType', e.target.value)}
                  className="data-type-select"
                >
                  <option value="continuous">Continuous</option>
                  <option value="binary">Binary</option>
                  <option value="count">Count</option>
                </select>

                <input
                  type="text"
                  value={dataCol.units}
                  onChange={(e) => updateDataColumn(idx, 'units', e.target.value)}
                  placeholder="Units (optional)"
                  className="units-input"
                />

                {psychopyConfig.dataColumns.length > 1 && (
                  <button
                    onClick={() => removeDataColumn(idx)}
                    className="remove-data-column-btn"
                  >
                    ×
                  </button>
                )}
              </div>

              {dataCol.column && (
                <div className="column-preview">
                  Sample values: {getUniqueValues(dataCol.column).join(', ')}
                </div>
              )}
            </div>
          ))}
        </div>

        <button onClick={addDataColumn} className="add-data-column-btn">
          + Add Data Column
        </button>

        <div className="selection-summary">
          {psychopyConfig.dataColumns.filter(dc => dc.column).length} data column(s) selected
        </div>
      </div>

      {/* Event Marker Sources */}
      <div className="config-subsection">
        <h4 className="subsection-title">3. Map Event Marker Sources (Optional)</h4>
        <p className="subsection-description">
          Select columns whose values indicate what experimental procedure was occurring.
        </p>

        <div className="event-sources-list">
          {psychopyConfig.eventSources.map((source, idx) => (
            <div key={idx} className="event-source-config">
              <div className="event-source-row">
                <select
                  value={source.column}
                  onChange={(e) => updateEventSource(idx, 'column', e.target.value)}
                  className="event-source-select"
                >
                  <option value="">Select column...</option>
                  {psychopyColumns.map(col => (
                    <option key={col} value={col}>{col}</option>
                  ))}
                </select>

                <select
                  value={source.labelType}
                  onChange={(e) => updateEventSource(idx, 'labelType', e.target.value)}
                  className="label-type-select"
                >
                  <option value="direct">Use values directly</option>
                  <option value="prefixed">Add custom prefix</option>
                </select>

                {source.labelType === 'prefixed' && (
                  <input
                    type="text"
                    value={source.customPrefix}
                    onChange={(e) => updateEventSource(idx, 'customPrefix', e.target.value)}
                    placeholder="Prefix (e.g., 'task_')"
                    className="prefix-input"
                  />
                )}

                <button
                  onClick={() => removeEventSource(idx)}
                  className="remove-event-source-btn"
                >
                  ×
                </button>
              </div>

              {source.column && (
                <div className="column-preview">
                  Will create event markers: {getUniqueValues(source.column).map(v => 
                    source.labelType === 'prefixed' && source.customPrefix 
                      ? `${source.customPrefix}${v}` 
                      : v
                  ).join(', ')}
                </div>
              )}
            </div>
          ))}
        </div>

        <button onClick={addEventSource} className="add-event-source-btn">
          + Add Event Source
        </button>
      </div>

      {/* Condition Columns */}
      <div className="config-subsection">
        <h4 className="subsection-title">4. Select Condition Columns (Optional)</h4>
        <p className="subsection-description">
          Choose columns that represent experimental conditions for grouping/filtering.
        </p>

        <div className="condition-columns-grid">
          {psychopyColumns.map(col => {
            const uniqueValues = getUniqueValues(col);
            const hasReasonableCardinality = uniqueValues.length > 0 && uniqueValues.length <= 10;
            
            if (!hasReasonableCardinality) return null;

            return (
              <label key={col} className="condition-column-checkbox">
                <input
                  type="checkbox"
                  checked={psychopyConfig.conditionColumns.includes(col)}
                  onChange={() => toggleConditionColumn(col)}
                />
                <div className="condition-column-info">
                  <span className="condition-column-name">{col}</span>
                  <span className="condition-column-values">
                    ({uniqueValues.length} values: {uniqueValues.join(', ')})
                  </span>
                </div>
              </label>
            );
          })}
        </div>

        <div className="selection-summary">
          {psychopyConfig.conditionColumns.length} condition column(s) selected
        </div>
      </div>

      {/* Configuration Summary */}
      <div className="config-summary-box">
        <h4 className="summary-title">Configuration Summary</h4>
        <div className="summary-grid">
          <div className="summary-item">
            <strong>Timestamp:</strong> {psychopyConfig.timestampColumn || 'Not selected'}
            {psychopyConfig.timestampColumn && ` (${psychopyConfig.timestampFormat})`}
          </div>
          <div className="summary-item">
            <strong>Data Columns:</strong> {psychopyConfig.dataColumns.filter(dc => dc.column).length}
          </div>
          <div className="summary-item">
            <strong>Event Sources:</strong> {psychopyConfig.eventSources.filter(es => es.column).length}
          </div>
          <div className="summary-item">
            <strong>Condition Filters:</strong> {psychopyConfig.conditionColumns.length}
          </div>
        </div>
      </div>
    </div>
  );
}

export default PsychoPyConfigStep;