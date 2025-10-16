# EmotiBit Data Analysis System - Architecture

## Overview

A full-stack web application for analyzing biometric data collected from EmotiBit devices. The system enables researchers to compare physiological responses across multiple experimental conditions using event markers and condition markers, with dynamic multi-group comparisons and time series visualizations.

## System Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend                           │
│  ┌─────────────────┐         ┌──────────────────┐          │
│  │ AnalysisViewer  │         │  ResultsViewer   │          │
│  │  - File Upload  │         │  - Statistics    │          │
│  │  - Config UI    │         │  - Visualizations│          │
│  │  - Validation   │         │  - Export Tools  │          │
│  └─────────────────┘         └──────────────────┘          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Flask Backend (app.py)                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Routes:                                              │  │
│  │  • /api/scan-folder-data    - Extract metrics/markers│  │
│  │  • /api/upload-folder-and-analyze - Process & analyze│  │
│  │  • /api/plot/<filename>     - Serve visualizations   │  │
│  │  • /api/test-timestamp-matching - Debug tool         │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Analysis Utilities (analysis_utils.py)          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  • prepare_event_markers_timestamps()                 │  │
│  │  • find_timestamp_offset()                            │  │
│  │  • extract_window_data()                              │  │
│  │  • match_event_markers_to_biometric()                 │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│           Jupyter Notebook (data_analysis.ipynb)             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. Load configuration from manifest                  │  │
│  │  2. Prepare event marker timestamps                   │  │
│  │  3. For each selected metric:                         │  │
│  │     • Calculate timestamp offset                      │  │
│  │     • Extract data for each comparison group          │  │
│  │     • Calculate statistics                            │  │
│  │     • Generate visualizations                         │  │
│  │  4. Save results to JSON                              │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Output & Storage                           │
│  • data/<subject_folder>/file_manifest.json                 │
│  • data/outputs/results.json                                │
│  • data/outputs/<metric>_*.png                              │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Upload & Configuration Phase
```
User Action → Frontend
    ↓
Select Folder → Parse File Structure
    ↓
Scan Folder Data → Extract Metrics/Markers/Conditions
    ↓
Configure Analysis:
  • Select Biometric Metrics
  • Add Comparison Groups:
    - Label (user-defined name)
    - Event Marker (e.g., "sart_1")
    - Condition Marker (e.g., "physical_plants") [optional]
    - Time Window (full duration or custom offset)
    ↓
Validate Configuration
    ↓
Send to Backend
```

### 2. Analysis Phase
```
Backend Receives Request
    ↓
Save Files to data/<subject_folder>/
    ↓
Create file_manifest.json:
  • emotibit_files[]
  • event_markers
  • analysis_config:
    - selected_metrics[]
    - comparison_groups[]
    ↓
Execute Jupyter Notebook
    ↓
Notebook Processing:
  1. Load manifest
  2. Load event markers → prepare_event_markers_timestamps()
  3. For each metric:
     a. Load biometric CSV
     b. Calculate offset → find_timestamp_offset()
     c. For each comparison group:
        - Extract window → extract_window_data()
          * Filter by event_marker
          * Filter by condition_marker (if specified)
          * Apply time window
     d. Calculate statistics (mean, std, min, max, count)
     e. Generate plots:
        - Individual time series (1+ groups)
        - Chronological progression (2+ groups)
        - Statistical comparison (2+ groups)
  4. Save results.json
    ↓
Return Results to Frontend
    ↓
Open Results in New Tab
```

### 3. Results Display Phase
```
ResultsViewer Component
    ↓
Load results from sessionStorage
    ↓
Display:
  • Analysis Results (statistics per group)
  • Visualizations (PNG images)
  • Event Markers Summary
    ↓
User Actions:
  • Save Figures (download all PNGs)
  • Export JSON (download results.json)
```

## Frontend Architecture

### Components

#### **App.js**
- Simple routing based on URL path
- `/` → AnalysisViewer
- `/results` → ResultsViewer

#### **AnalysisViewer.jsx**
**State Management:**
- `fileStructure` - Uploaded files organized by type
- `availableMetrics` - Extracted from EmotiBit filenames
- `availableEventMarkers` - Extracted from event markers CSV
- `availableConditions` - Extracted from event markers CSV
- `selectedMetrics` - User checkbox selections
- `comparisonGroups[]` - Dynamic array of group configurations

**Layout:**
- Two-column grid layout
- **Left Column (sticky):**
  - Detected Files summary
- **Right Column:**
  - Biometric Metrics selection
  - Analysis Configuration (comparison groups)
  - Run Analysis button
  - Status messages

**Key Functions:**
- `handleFolderSelect()` - Process uploaded folder
- `scanFolderData()` - Extract metrics/markers via API
- `addComparisonGroup()` - Add new comparison card
- `removeComparisonGroup()` - Remove comparison card
- `updateComparisonGroup()` - Update group field
- `uploadAndAnalyze()` - Send to backend for analysis

#### **ResultsViewer.jsx**
**Features:**
- Displays analysis results from sessionStorage
- Shows statistics for all comparison groups
- Renders plot images
- Provides export functionality

**Actions:**
- Save Figures - Downloads all PNG files
- Export JSON - Downloads results.json

### State Flow
```
User Upload → FileStructure State
    ↓
Scan API Call → Available Metrics/Markers State
    ↓
User Configuration → ComparisonGroups State
    ↓
Upload & Analyze → Backend
    ↓
Results → sessionStorage
    ↓
New Tab Opens → ResultsViewer
```

## Backend Architecture

### Flask Routes

#### `/api/scan-folder-data` [POST]
**Purpose:** Extract available metrics, event markers, and conditions from uploaded folder

**Input:**
- `emotibit_filenames` - List of EmotiBit CSV filenames
- `event_markers_file` - Event markers CSV file

**Process:**
1. Parse metric tags from filenames using regex: `_emotibit_ground_truth_([A-Z0-9%]+)\.csv`
2. Read event markers CSV
3. Extract unique event markers from `event_marker` column
4. Extract unique conditions from `condition` column
5. Normalize PRS markers (e.g., `prs_1_suffix` → `prs_1`)

**Output:**
```json
{
  "metrics": ["HR", "EDA", "TEMP", ...],
  "event_markers": ["sart_1", "biometric_baseline", ...],
  "conditions": ["physical_plants", "physical_no_plants", ...]
}
```

#### `/api/upload-folder-and-analyze` [POST]
**Purpose:** Upload files, create manifest, execute notebook, return results

**Input:**
- `files[]` - Uploaded CSV files
- `paths[]` - Original relative paths
- `folder_name` - Subject folder name
- `selected_metrics` - JSON array of selected metrics
- `comparison_groups` - JSON array of group configurations

**Process:**
1. Organize files into `data/<subject_folder>/`
2. Create `file_manifest.json` with:
   - File paths organized by type
   - Analysis configuration
3. Execute notebook: `jupyter nbconvert --execute --inplace data_analysis.ipynb`
4. Read `results.json`
5. Add plot URLs
6. Return results

**Output:**
```json
{
  "message": "Analysis completed successfully",
  "results": { ... },
  "folder_name": "..."
}
```

#### `/api/plot/<filename>` [GET]
**Purpose:** Serve generated plot images

**Returns:** PNG image file

#### `/api/test-timestamp-matching` [POST]
**Purpose:** Debug tool to verify timestamp alignment

**Process:**
1. Upload event markers + single metric file
2. Calculate timestamp offset
3. Sample 100 timestamps
4. Report alignment statistics

## Analysis Utilities (analysis_utils.py)

### Core Functions

#### `prepare_event_markers_timestamps(event_markers_df)`
**Purpose:** Convert ISO timestamps to Unix timestamps for alignment

**Handles:**
- Modern format: `unix_timestamp` column already present
- Legacy format: `timestamp` column with ISO 8601 strings

**Process:**
1. Check for existing `unix_timestamp` column
2. If not found, look for `timestamp` column
3. Convert using: `(pd.to_datetime(timestamp) - Unix_Epoch) / 1s`
4. Drop invalid timestamps (NaT values)

**Returns:** DataFrame with `unix_timestamp` column

---

#### `find_timestamp_offset(event_markers_df, emotibit_df)`
**Purpose:** Calculate timezone offset between event markers and EmotiBit data

**Algorithm:**
```
offset = min(event_markers['unix_timestamp']) - min(emotibit['LocalTimestamp'])
```

**Why needed:** Event marker timestamps are in system time, EmotiBit timestamps are in device time. These are often in different timezones.

**Returns:** Offset in seconds

---

#### `extract_window_data(emotibit_df, event_markers_df, offset, window_config)`
**Purpose:** Extract biometric data for specified event/condition window

**Input - window_config:**
```python
{
  'eventMarker': 'sart_1',           # Required
  'conditionMarker': 'physical_plants',  # Optional
  'timeWindowType': 'full' | 'custom',
  'customStart': -5,    # seconds before event
  'customEnd': 30       # seconds after event
}
```

**Process:**
1. Apply offset to align timestamps
2. Filter event markers by `eventMarker`
3. If `conditionMarker` specified, filter further by condition
4. For each matching event occurrence:
   - If `timeWindowType == 'full'`:
     - Extract from event start to next event (or end of data)
   - If `timeWindowType == 'custom'`:
     - Extract from `marker_time + customStart` to `marker_time + customEnd`
5. Concatenate all windows
6. Return combined DataFrame with `AdjustedTimestamp` column

**Key Feature:** Handles multiple occurrences of same event marker

**Returns:** DataFrame with biometric data from matching windows

---

#### `match_event_markers_to_biometric(event_markers_df, emotibit_df, offset, tolerance)`
**Purpose:** Match event timestamps to nearest biometric readings (used in testing)

## Jupyter Notebook (data_analysis.ipynb)

### Structure
```python
# 1. Setup & Configuration
- Import libraries
- Configure paths
- Initialize results structure
- Import analysis_utils functions

# 2. Load Configuration
- Find most recent subject folder
- Load file_manifest.json
- Extract analysis_config

# 3. Load Event Markers
- Read event markers CSV
- Prepare timestamps (convert ISO to Unix)
- Store marker info in results

# 4. Analyze Each Selected Metric
for metric in selected_metrics:
    # 4a. Load biometric data
    - Find metric file
    - Read CSV
    
    # 4b. Calculate offset
    offset = find_timestamp_offset(df_markers, df_metric)
    
    # 4c. Extract data for each comparison group
    for group in comparison_groups:
        data = extract_window_data(df_metric, df_markers, offset, group)
        group_data[group_label] = data
    
    # 4d. Calculate statistics
    for group_label, data in group_data.items():
        stats = {mean, std, min, max, count}
        metric_results[group_label] = stats
    
    # 4e. Generate visualizations
    - Plot 1: Individual time series (always)
    - Plot 2: Chronological progression (if 2+ groups)
    - Plot 3: Statistical comparison (if 2+ groups)

# 5. Save Results
- Write results.json with:
  - analysis statistics
  - plot metadata
  - errors/warnings
```

### Visualization Details

#### Plot 1: Individual Time Series
**Type:** Stacked subplots (one per comparison group)

**Features:**
- X-axis: Elapsed time in seconds from event start
- Y-axis: Metric value
- Red dashed line: Mean value
- Statistics box: Mean, Std, n
- Color-coded by group

**Always generated** (works for 1+ groups)

---

#### Plot 2: Chronological Progression
**Type:** Continuous time series

**Features:**
- X-axis: Elapsed time in minutes from recording start
- Y-axis: Metric value
- All groups plotted chronologically
- Vertical lines mark event boundaries
- Labels show which section belongs to which group
- Legend identifies groups by color

**Only generated if 2+ groups**

---

#### Plot 3: Statistical Comparison
**Type:** Bar chart with error bars

**Features:**
- X-axis: Group labels
- Y-axis: Mean metric value
- Error bars: ±1 standard deviation
- Value labels on bars
- Color-coded by group

**Only generated if 2+ groups**

---

### Color Palette
```python
colors = [
    '#4CAF50',  # Green
    '#2196F3',  # Blue
    '#FF9800',  # Orange
    '#9C27B0',  # Purple
    '#F44336',  # Red
    '#00BCD4',  # Cyan
    '#FFEB3B',  # Yellow
    '#795548',  # Brown
    '#607D8B',  # Blue Grey
    '#E91E63'   # Pink
]
```
Supports up to 10 groups; cycles if more groups added.

## Key Features

### 1. Dynamic Multi-Group Comparison
- Users can compare 1 to N event marker windows
- Add/remove comparison groups on-the-fly
- Each group has custom label, event marker, condition marker, and time window

### 2. Dual Filtering (Event + Condition)
- Filter by event marker (e.g., "sart_1")
- Optionally filter by condition (e.g., "physical_plants")
- Extract only data matching BOTH criteria

### 3. Timestamp Alignment
- Handles timezone offsets between data sources
- Converts ISO 8601 timestamps to Unix epoch
- Aligns event markers with biometric data streams

### 4. Flexible Time Windows
- **Full event duration:** From marker to next marker
- **Custom offset:** User-defined start/end relative to marker

### 5. Multiple Occurrences Handling
- Single event marker can occur multiple times in recording
- Extracts and aggregates data from all occurrences
- Example: "sart_1" appears 3 times → combines all 3 windows

### 6. Results in Separate Tab
- Analysis results open in new browser tab
- Allows comparison of multiple analysis runs side-by-side
- Export figures and JSON independently

### 7. Backward Compatibility
- Supports both modern (`unix_timestamp`) and legacy (`timestamp`) formats
- Gracefully handles missing condition columns

## File Structure
```
project/
├── app.py                          # Flask backend
├── analysis_utils.py               # Shared analysis functions
├── data_analysis.ipynb             # Jupyter notebook
├── requirements.txt                # Python dependencies
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.js                  # Main React component
│   │   ├── components/
│   │   │   ├── AnalysisViewer.jsx  # Main analysis interface
│   │   │   ├── AnalysisViewer.css
│   │   │   ├── ResultsViewer.jsx   # Results display
│   │   │   └── ResultsViewer.css
│   │   └── index.js
│   └── package.json
│
└── data/
    ├── <subject_folder>/
    │   ├── file_manifest.json      # File paths & analysis config
    │   ├── <subject>_event_markers.csv
    │   └── emotibit_data/
    │       ├── *_HR.csv
    │       ├── *_EDA.csv
    │       └── ...
    │
    └── outputs/
        ├── results.json            # Analysis results
        ├── HR_individual_timeseries.png
        ├── HR_timeseries.png
        ├── HR_comparison.png
        └── ...
```

## Data Formats

### Event Markers CSV
```csv
timestamp,event_marker,condition,EDA,HR,BI,PG
2025-05-22T20:42:36.738613,startup,,1.23,,11639.0
2025-05-22T20:43:10.123456,biometric_baseline,,,75.2,
2025-05-22T20:45:30.456789,sart_1,physical_plants,,,
2025-05-22T20:50:15.789012,sart_2,physical_plants,,,
2025-05-22T20:55:45.012345,sart_1,physical_no_plants,,,
```

**Key Columns:**
- `timestamp` - ISO 8601 format (legacy) OR
- `unix_timestamp` - Unix epoch seconds (modern)
- `event_marker` - Event identifier
- `condition` - Optional condition identifier
- Additional columns - Streamed biometric data (can have NaN)

---

### EmotiBit Biometric CSV
```csv
LocalTimestamp,EmotiBitTimestamp,PacketNumber,DataLength,TypeTag,ProtocolVersion,DataReliability,HR
1747946556.738,1234567.890,1,1,HR,5,100,72.5
1747946557.123,1234568.275,2,1,HR,5,100,73.1
...
```

**Key Columns:**
- `LocalTimestamp` - Unix timestamp from EmotiBit device
- `HR` (or other metric) - Last column contains the biometric value

---

### file_manifest.json
```json
{
  "emotibit_files": [
    {
      "filename": "2025-05-22_20-42-36_xxx_emotibit_ground_truth_HR.csv",
      "path": "data/subject_folder/emotibit_data/...",
      "relative_path": "emotibit_data/..."
    }
  ],
  "event_markers": {
    "filename": "2025-05-23_xxx_event_markers.csv",
    "path": "data/subject_folder/...",
    "relative_path": "..."
  },
  "analysis_config": {
    "selected_metrics": ["HR", "EDA"],
    "comparison_groups": [
      {
        "id": 1,
        "label": "Baseline",
        "eventMarker": "biometric_baseline",
        "conditionMarker": "",
        "timeWindowType": "full",
        "customStart": -5,
        "customEnd": 30
      },
      {
        "id": 2,
        "label": "Task with Plants",
        "eventMarker": "sart_1",
        "conditionMarker": "physical_plants",
        "timeWindowType": "custom",
        "customStart": 0,
        "customEnd": 60
      }
    ]
  }
}
```

---

### results.json
```json
{
  "status": "completed",
  "timestamp": "2025-10-14T09:35:20.235625",
  "errors": [],
  "warnings": [],
  "markers": {
    "shape": [100859, 8],
    "columns": ["timestamp", "EDA", "HR", ...],
    "conditions": {
      "physical_plants": 50000,
      "physical_no_plants": 50859
    }
  },
  "analysis": {
    "HR": {
      "Baseline": {
        "mean": 72.96,
        "std": 4.45,
        "min": 63.91,
        "max": 85.9,
        "count": 142
      },
      "Task with Plants": {
        "mean": 68.17,
        "std": 4.94,
        "min": 60.78,
        "max": 102.18,
        "count": 396
      }
    }
  },
  "plots": [
    {
      "name": "HR Individual Time Series",
      "path": "data/outputs/HR_individual_timeseries.png",
      "filename": "HR_individual_timeseries.png",
      "url": "/api/plot/HR_individual_timeseries.png"
    },
    ...
  ]
}
```

## Error Handling

### Frontend Validation
- Folder must be selected
- At least 1 comparison group required
- All groups must have event markers selected
- At least 1 biometric metric selected

### Backend Validation
- File types restricted to CSV
- File size limit: 500MB total
- Notebook execution timeout: 120 seconds

### Notebook Error Handling
- Try/catch around each metric analysis
- Continues if one metric fails
- Errors stored in results.json
- Invalid timestamps filtered out (NaN/NaT)
- Missing data handled with dropna()

### Common Issues & Solutions

**Issue:** No timestamp matches
- **Cause:** Timezone offset calculation failed
- **Solution:** Check that event markers and biometric files are from same session

**Issue:** No data for comparison group
- **Cause:** Event marker or condition not found in data
- **Solution:** Verify spelling, check event markers CSV

**Issue:** Plots not generated
- **Cause:** Insufficient data points
- **Solution:** Adjust time window or check data quality

## Performance Considerations

### File Upload
- Only necessary files uploaded (event markers + selected metrics)
- Typical upload: 3-10 files, 5-50MB total

### Analysis Speed
- Vectorized pandas operations
- Typical execution: 5-15 seconds per metric
- Scales linearly with number of metrics and comparison groups

### Memory Usage
- Loads one metric at a time
- Releases memory between metrics
- Typical peak: 200-500MB RAM

## Security Considerations

- File uploads restricted to CSV only
- Filenames sanitized with `secure_filename()`
- No arbitrary code execution in notebook
- Session storage for temporary data (cleared on tab close)
- No authentication (designed for local/trusted use)

## Future Enhancements

### Potential Features
1. Statistical significance testing (t-test, ANOVA)
2. Export to Excel with formatted tables
3. Custom plot styling options
4. Batch analysis of multiple subjects
5. Real-time data streaming support
6. Database storage for historical analyses
7. User authentication & multi-user support
8. Advanced filtering (e.g., by time of day, ranges)
9. Correlation analysis between metrics
10. Machine learning feature extraction

## Dependencies

### Frontend
- React 18.x

### Backend
- Flask 2.x
- Flask-CORS
- pandas
- numpy
- matplotlib
- jupyter

### Analysis
- pandas (data manipulation)
- numpy (numerical operations)
- matplotlib (visualization)
- datetime (timestamp handling)

## Development Workflow

### Setup
```bash
# Backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
npm run build
```

### Development
```bash
# Terminal 1: Flask backend
python app.py

# Terminal 2: React frontend (development mode)
cd frontend
npm start
```

### Production Build
```bash
cd frontend
npm run build
# Static files served by Flask from frontend/build/
```

## Testing

### Manual Testing Checklist
- [ ] Upload folder with EmotiBit data
- [ ] Verify metrics detected correctly
- [ ] Verify event markers detected correctly
- [ ] Add multiple comparison groups
- [ ] Configure different time windows
- [ ] Select multiple metrics
- [ ] Run analysis
- [ ] Verify plots generated
- [ ] Check statistics accuracy
- [ ] Export figures
- [ ] Export JSON
- [ ] Test with single comparison group
- [ ] Test with condition markers

### Debug Tools
- `/api/test-timestamp-matching` - Verify timestamp alignment
- Browser console - Frontend errors
- Flask terminal - Backend errors
- Notebook output - Analysis progress

## Troubleshooting

### Notebook Won't Execute
- Check jupyter installation: `jupyter --version`
- Verify notebook path in app.py
- Check for syntax errors in notebook

### Timestamps Not Aligning
- Use test route to verify offset calculation
- Check that files are from same experimental session
- Verify timestamp columns exist

### Plots Not Displaying
- Check Flask terminal for plot generation errors
- Verify OUTPUT_FOLDER exists and is writable
- Check browser console for image loading errors

---

**Last Updated:** October 2025
**Version:** 2.0
**Authors:** Brian Cantrell, PhD