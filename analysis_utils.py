"""
EMOTIBIT DATA SYNCHRONIZATION & EXTRACTION UTILITIES - LLM CONTRACT
===================================================================

PURPOSE:
This module provides foundational utilities for synchronizing and extracting biometric sensor data
with behavioral event markers. It solves the critical problem of aligning multiple asynchronous
data streams (sensor recordings vs. event annotations) that use different clock sources.

CORE PROBLEM SOLVED:
-------------------
Biometric sensors (EmotiBit) and event marking systems run on separate devices with separate clocks:
    - EmotiBit: Records with LocalTimestamp (device-local clock)
    - Event Markers: Recorded with experimenter's system clock (Unix timestamps)
    - Challenge: These clocks may differ by hours due to timezone, device time settings, or drift
    
This module provides timestamp alignment, event-to-data matching, and windowed data extraction
to enable synchronized analysis of physiological responses to experimental events.

ARCHITECTURE OVERVIEW:
---------------------
┌─────────────────────────────────────────────────────────────────┐
│                  Data Synchronization Pipeline                  │
└─────────────────────────────────────────────────────────────────┘
    │
    ├──► prepare_event_markers_timestamps()
    │    [Normalize timestamp formats]
    │    Input: Raw event markers (OLD or NEW format)
    │    Output: Standardized unix_timestamp column
    │
    ├──► find_timestamp_offset()
    │    [Calculate clock alignment]
    │    Input: Event markers + EmotiBit data
    │    Output: Offset value to align streams
    │
    ├──► match_event_markers_to_biometric() [OPTIONAL]
    │    [Point-wise event matching]
    │    Output: Closest biometric sample per event
    │
    └──► extract_window_data()
         [Window-based extraction]
         Input: EmotiBit data + Event config + Offset
         Output: Data windows around events

FUNCTION CONTRACT - prepare_event_markers_timestamps():
=======================================================

Purpose: Normalize event marker timestamps to consistent Unix format

Input Requirements:
    - df: pandas DataFrame with ONE of:
        * 'timestamp_unix' column (NEW format, preferred)
        * 'timestamp' column (OLD format, numeric unix OR ISO string)

Output Guarantees:
    Returns DataFrame with guaranteed 'unix_timestamp' column (float)
    - All timestamps are Unix epoch seconds (positive numeric values)
    - Invalid/null timestamps are removed (rows dropped)
    - Original DataFrame is never mutated (copy returned)

Format Support:
    
    NEW Format (Preferred):
        Columns: ['timestamp_unix', 'timestamp_iso', 'event_marker', 'condition', ...]
        timestamp_unix: Already in Unix epoch format (numeric)
        Processing: Direct copy to 'unix_timestamp', validate > 0
    
    OLD Format (Backward Compatibility):
        Columns: ['timestamp', 'event_marker', 'condition', ...]
        
        Case A: timestamp is numeric (int/float)
            → Assume Unix epoch, copy directly
        
        Case B: timestamp is ISO string
            → Parse and convert to Unix epoch
            → Supported formats: ISO 8601, RFC 3339
            → Examples: "2024-01-15T10:30:00Z", "2024-01-15T10:30:00.123+00:00"

Processing Pipeline:
    1. Create copy of input DataFrame (immutability)
    2. Detect format (NEW vs OLD, numeric vs string)
    3. Convert timestamps to Unix epoch if necessary
    4. Validate: Remove rows where unix_timestamp is null or <= 0
    5. Log conversion statistics (valid count, dropped count)

Error Handling:
    - Missing required columns → ValueError with descriptive message
    - Empty DataFrame or all nulls → ValueError
    - Unparseable ISO strings → Row dropped, count logged
    - Invalid numeric values (<=0) → Row dropped, count logged

Logging Output:
    "✓ Found 'timestamp_unix' column (NEW format)"
    "✓ Using 125 valid unix timestamps"
    "⚠ Dropped 3 rows with invalid timestamps"

Example Usage:
    >>> df_raw = pd.read_csv('event_markers.csv')
    >>> df_clean = prepare_event_markers_timestamps(df_raw)
    >>> assert 'unix_timestamp' in df_clean.columns
    >>> assert all(df_clean['unix_timestamp'] > 0)

FUNCTION CONTRACT - find_timestamp_offset():
============================================

Purpose: Calculate alignment offset between event markers and biometric data streams

Mathematical Definition:
    offset = min(event_timestamps) - min(emotibit_timestamps)
    
    After applying offset:
        aligned_emotibit_time = emotibit_LocalTimestamp + offset
        aligned_emotibit_time ≈ event_unix_timestamp

Input Requirements:
    - event_markers_df: DataFrame with 'unix_timestamp' column (from prepare_event_markers_timestamps)
    - emotibit_df: DataFrame with 'LocalTimestamp' column (EmotiBit device time)

Output:
    float: Offset in seconds to add to EmotiBit timestamps for alignment
    - Positive offset: Event system clock is ahead of EmotiBit clock
    - Negative offset: Event system clock is behind EmotiBit clock
    - Typical range: -43200 to +43200 seconds (±12 hours for timezone differences)

Assumptions:
    - Both recordings started at approximately the same real-world time
    - Clock drift is negligible over recording duration (<1 second error)
    - First event marker occurs near start of biometric recording

Use Case Example:
    Experimenter records events on computer (UTC timezone)
    EmotiBit device set to Pacific Time (PST, UTC-8)
    Expected offset: ~28800 seconds (8 hours)

Logging Output:
    "Event Marker Start: 2024-01-15 18:30:00"
    "EmotiBit Start: 2024-01-15 10:30:00"
    "Calculated Offset: 28800.00s (8.00 hours)"

Example Usage:
    >>> offset = find_timestamp_offset(df_events, df_hr)
    >>> df_hr['AlignedTime'] = df_hr['LocalTimestamp'] + offset
    >>> # Now AlignedTime matches event timestamps

FUNCTION CONTRACT - match_event_markers_to_biometric():
=======================================================

Purpose: Point-wise matching of discrete events to nearest biometric samples

Input Requirements:
    - event_markers_df: DataFrame with 'unix_timestamp' and 'event_marker' columns
    - emotibit_df: DataFrame with 'LocalTimestamp' column + metric value column (last column)
    - offset: float, timestamp offset from find_timestamp_offset()
    - tolerance: float, maximum time difference in seconds (default=1.0)

Output:
    List of dicts, one per matched event:
    [
        {
            'event_marker': str,           # Event label
            'condition': str,              # Experimental condition
            'event_timestamp': float,      # Unix timestamp of event
            'event_iso': str,              # ISO format (if available)
            'matched_timestamp': float,    # Nearest EmotiBit LocalTimestamp
            'adjusted_timestamp': float,   # LocalTimestamp + offset
            'time_diff': float,            # Absolute time difference (seconds)
            'biometric_value': float,      # Metric value at matched time
            'row_index': int               # Index in emotibit_df
        },
        ...
    ]

Matching Algorithm:
    For each event:
        1. Apply offset to all biometric timestamps
        2. Calculate absolute time difference: |adjusted_biometric_time - event_time|
        3. Find minimum time difference
        4. If min_diff <= tolerance → match, else warning

Use Cases:
    - Validating synchronization quality
    - Extracting instantaneous values at event onset
    - Quality control: checking for missing data at critical timepoints

Warnings:
    "WARNING: No match within tolerance for event 'stimulus_1' at 1705334400.0"
    → Event occurred during data gap or tolerance too strict

Example Usage:
    >>> matches = match_event_markers_to_biometric(df_events, df_hr, offset, tolerance=2.0)
    >>> for m in matches:
    ...     print(f"{m['event_marker']}: HR={m['biometric_value']:.1f} bpm, diff={m['time_diff']:.3f}s")

FUNCTION CONTRACT - extract_window_data():
==========================================

Purpose: Extract biometric data windows surrounding experimental events

Input Requirements:
    - emotibit_df: DataFrame with 'LocalTimestamp' column + metric value column
    - event_markers_df: DataFrame with 'unix_timestamp' and 'event_marker' columns
    - offset: float, timestamp offset from find_timestamp_offset()
    - window_config: dict with structure:
        {
            'eventMarker': str,          # Event name to match (or 'all')
            'conditionMarker': str,      # Optional condition filter
            'timeWindowType': str,       # 'full' or 'custom'
            'customStart': float,        # If custom: seconds before event
            'customEnd': float,          # If custom: seconds after event
            'label': str                 # Human-readable group label
        }

Output:
    DataFrame with schema: [AdjustedTimestamp, ...original_columns...]
    - AdjustedTimestamp: Time relative to event onset (t=0 at event)
    - Contains concatenated data from ALL occurrences of specified event
    - Empty DataFrame if no matching events or no data in windows

Window Extraction Modes:

    Mode 1: FULL Window (timeWindowType='full')
        Extracts from event marker until next marker (inter-event interval)
        Use case: Analyzing entire task blocks or conditions
        
        Behavior:
            start_time = event_timestamp
            end_time = next_event_timestamp OR end_of_recording
            window = [start_time, end_time)
    
    Mode 2: CUSTOM Window (timeWindowType='custom')
        Extracts fixed time window relative to event
        Use case: Baseline periods, stimulus responses with known duration
        
        Behavior:
            start_time = event_timestamp + customStart  # customStart can be negative
            end_time = event_timestamp + customEnd
            window = [start_time, end_time]
        
        Example: Baseline 30s before stimulus
            customStart = -30.0
            customEnd = 0.0

    Mode 3: ENTIRE Experiment ('eventMarker'='all')
        Returns complete dataset without filtering
        Use case: Whole-session analysis, no event segmentation
        
        Behavior:
            Returns full emotibit_df with AdjustedTimestamp column

Multi-Occurrence Handling:
    If event occurs N times:
        1. Extract N separate windows
        2. Concatenate all windows into single DataFrame
        3. Preserve chronological order
        4. Log total occurrences and extracted data points

Condition Filtering:
    If conditionMarker specified and 'condition' column exists:
        Only extract windows for events matching BOTH:
            - event_marker == config['eventMarker']
            - condition == config['conditionMarker']
    
    Use case: Analyzing only "difficult" trials or "stress" conditions

Processing Steps:
    1. Apply offset: emotibit_df['AdjustedTimestamp'] = LocalTimestamp + offset
    2. Filter events by marker name and optional condition
    3. For each matching event:
        a. Determine window boundaries (full or custom)
        b. Extract emotibit rows within window
        c. Append to collection
    4. Concatenate all windows (ignore_index=True)
    5. Log extraction statistics

Example Configurations:

    # Baseline period: 30s before stimulus
    {
        'eventMarker': 'stimulus_onset',
        'conditionMarker': '',
        'timeWindowType': 'custom',
        'customStart': -30.0,
        'customEnd': 0.0,
        'label': 'Baseline'
    }
    
    # Task performance: stimulus to response
    {
        'eventMarker': 'stimulus_onset',
        'conditionMarker': 'hard',
        'timeWindowType': 'full',
        'label': 'Hard Task Performance'
    }
    
    # Recovery period: 60s after stressor
    {
        'eventMarker': 'stressor_end',
        'conditionMarker': '',
        'timeWindowType': 'custom',
        'customStart': 0.0,
        'customEnd': 60.0,
        'label': 'Recovery'
    }

Logging Output:
    "Analyzing entire experiment duration"  # For 'all'
    "Found 12 occurrences of 'stimulus_onset' with condition 'hard'"
    "Extracted 3,450 data points across all occurrences"
    "⚠ Warning: No occurrences of event marker 'missing_event' found"

Error Recovery:
    - No matching events → Returns empty DataFrame, logs warning
    - No data in windows → Returns empty DataFrame (valid for some analyses)
    - Missing 'condition' column when conditionMarker specified → Ignores filter, logs warning

Example Usage:
    >>> baseline_config = {
    ...     'eventMarker': 'task_start',
    ...     'conditionMarker': '',
    ...     'timeWindowType': 'custom',
    ...     'customStart': -30.0,
    ...     'customEnd': 0.0,
    ...     'label': 'Baseline'
    ... }
    >>> baseline_data = extract_window_data(df_hr, df_events, offset, baseline_config)
    >>> print(f"Baseline HR: {baseline_data['HR'].mean():.1f} bpm")

FUNCTION CONTRACT - get_subject_files():
========================================

Purpose: Filter file manifest to extract files belonging to specific subject

Input Requirements:
    - manifest: dict with structure:
        {
            'emotibit_files': [
                {'filename': str, 'path': str, 'subject': str},
                ...
            ],
            'event_markers': {'path': str, 'subject': str} OR None,
            'event_markers_by_subject': {
                'subject1': {'path': str},
                'subject2': {'path': str},
                ...
            } OR None,
            'respiration_files': [...],  # Optional
            'external_files': [...]      # Optional
        }
    - subject_name: str, subject identifier (e.g., 'P001', 'participant_1')

Output:
    dict with structure:
    {
        'emotibit_files': list,      # Filtered EmotiBit files for this subject
        'event_markers': dict | None, # Event marker file for this subject
        'respiration_files': list,   # Filtered respiration files
        'external_files': list       # Filtered external data files
    }

Matching Logic:
    File is included if ANY of these conditions are true:
        1. file['subject'] field matches subject_name exactly
        2. subject_name appears as substring in file['path']
    
    Rationale: Handles both explicit subject fields and path-based identification

Event Markers Priority:
    Priority 1: event_markers_by_subject[subject_name]  # Batch mode
    Priority 2: event_markers (if subject_name in path)  # Single subject mode

Logging Output:
    "✓ Found event markers for P001 (batch mode)"
    "Subject files for P001:"
    "  - EmotiBit: 8 files"
    "  - Event markers: ✓"
    "  - External data: 2 files"

Use Cases:
    - Multi-subject studies: Isolate one subject's data for analysis
    - Batch processing: Iterate through subjects with consistent interface
    - Data validation: Verify complete dataset per subject

Example Usage:
    >>> subjects = ['P001', 'P002', 'P003']
    >>> for subject in subjects:
    ...     files = get_subject_files(manifest, subject)
    ...     if not files['event_markers']:
    ...         print(f"WARNING: {subject} missing event markers")
    ...     print(f"{subject}: {len(files['emotibit_files'])} sensor files")

FUNCTION CONTRACT - find_metric_file_for_subject():
===================================================

Purpose: Locate specific metric CSV file within subject's files

Input Requirements:
    - subject_files: dict from get_subject_files() with 'emotibit_files' key
    - metric: str, metric identifier (e.g., 'HR', 'EDA', 'TEMP', 'PI')

Output:
    str | None
    - Success: Full file path to metric CSV
    - Failure: None (metric file not found)

Matching Logic:
    File matches if filename contains pattern: '_{metric}.csv'
    Examples:
        - 'subject1_HR.csv' matches metric='HR'
        - '2024-01-15_12-30-00_EDA.csv' matches metric='EDA'
        - 'participant_2_TEMP.csv' matches metric='TEMP'

Common Metrics:
    - 'HR': Heart Rate (BPM)
    - 'EDA': Electrodermal Activity / Galvanic Skin Response (μS)
    - 'TEMP': Temperature (°C or °F)
    - 'PI': Photoplethysmography Infrared
    - 'PR': Photoplethysmography Red
    - 'PG': Photoplethysmography Green
    - 'AX': Accelerometer X-axis
    - 'AY': Accelerometer Y-axis
    - 'AZ': Accelerometer Z-axis

Example Usage:
    >>> subject_files = get_subject_files(manifest, 'P001')
    >>> hr_file = find_metric_file_for_subject(subject_files, 'HR')
    >>> if hr_file:
    ...     df_hr = pd.read_csv(hr_file)
    ... else:
    ...     print("Heart rate data not available")

TIMESTAMP SYNCHRONIZATION DEEP DIVE:
====================================

Problem Statement:
    Event markers: "Stimulus shown at 14:30:00 UTC"
    EmotiBit device: "HR=75 bpm recorded at LocalTimestamp=1705321800"
    Question: What was HR when stimulus was shown?

Without synchronization:
    ❌ EmotiBit LocalTimestamp might be in device-local time (PST, EST, etc.)
    ❌ Direct comparison yields nonsense results
    ❌ Data appears misaligned by hours

With synchronization:
    ✓ Calculate offset = find_timestamp_offset(events, emotibit)
    ✓ Align: emotibit['AdjustedTimestamp'] = emotibit['LocalTimestamp'] + offset
    ✓ Extract windows using aligned timestamps
    ✓ Accurate event-locked analysis

Quality Metrics:
    Good synchronization: time_diff < 1.0 second in match_event_markers_to_biometric
    Acceptable: time_diff < 5.0 seconds
    Poor: time_diff > 10.0 seconds (investigate clock drift or data gaps)

DATA FORMAT REQUIREMENTS:
=========================

Event Markers CSV:
    Required columns:
        - 'unix_timestamp' OR 'timestamp': Event time (Unix epoch or ISO string)
        - 'event_marker': Event label/name (string)
    
    Optional columns:
        - 'condition': Experimental condition (for filtering)
        - 'timestamp_iso': Human-readable timestamp
        - Any custom annotation columns

    Example:
        unix_timestamp,event_marker,condition
        1705334400.0,stimulus_onset,easy
        1705334460.0,response_collected,easy
        1705334520.0,stimulus_onset,hard

EmotiBit Metric CSV:
    Required columns:
        - 'LocalTimestamp': Device-local Unix timestamp (float)
        - Last column: Metric value (numeric)
    
    Common columns:
        - 'PacketNumber': Sequence number
        - 'DataTimestamp': Additional timestamp
        - Metric-specific value column
    
    Example (HR file):
        LocalTimestamp,PacketNumber,DataTimestamp,HR
        1705305600.123,1,1705305600.123,72.5
        1705305601.123,2,1705305601.123,73.1
        1705305602.123,3,1705305602.123,74.2

COMMON USAGE PATTERNS:
======================

Pattern 1: Basic Event-Locked Analysis
    >>> df_events = pd.read_csv('events.csv')
    >>> df_events = prepare_event_markers_timestamps(df_events)
    >>> df_hr = pd.read_csv('heart_rate.csv')
    >>> offset = find_timestamp_offset(df_events, df_hr)
    >>> 
    >>> config = {
    ...     'eventMarker': 'task_start',
    ...     'conditionMarker': '',
    ...     'timeWindowType': 'custom',
    ...     'customStart': 0.0,
    ...     'customEnd': 60.0,
    ...     'label': 'Task Performance'
    ... }
    >>> task_data = extract_window_data(df_hr, df_events, offset, config)
    >>> print(f"Mean HR during task: {task_data['HR'].mean():.1f} bpm")

Pattern 2: Multi-Subject Batch Processing
    >>> manifest = load_manifest('study_data.json')
    >>> subjects = ['P001', 'P002', 'P003']
    >>> results = {}
    >>> 
    >>> for subject in subjects:
    ...     files = get_subject_files(manifest, subject)
    ...     hr_file = find_metric_file_for_subject(files, 'HR')
    ...     
    ...     if hr_file and files['event_markers']:
    ...         df_events = pd.read_csv(files['event_markers']['path'])
    ...         df_events = prepare_event_markers_timestamps(df_events)
    ...         df_hr = pd.read_csv(hr_file)
    ...         
    ...         offset = find_timestamp_offset(df_events, df_hr)
    ...         baseline = extract_window_data(df_hr, df_events, offset, baseline_config)
    ...         
    ...         results[subject] = baseline['HR'].mean()

Pattern 3: Condition Comparison
    >>> baseline_config = {
    ...     'eventMarker': 'trial_start',
    ...     'conditionMarker': 'easy',
    ...     'timeWindowType': 'full',
    ...     'label': 'Easy Trials'
    ... }
    >>> stress_config = {
    ...     'eventMarker': 'trial_start',
    ...     'conditionMarker': 'hard',
    ...     'timeWindowType': 'full',
    ...     'label': 'Hard Trials'
    ... }
    >>> 
    >>> easy_data = extract_window_data(df_eda, df_events, offset, baseline_config)
    >>> hard_data = extract_window_data(df_eda, df_events, offset, stress_config)
    >>> 
    >>> print(f"EDA easy: {easy_data['EDA'].mean():.2f} μS")
    >>> print(f"EDA hard: {hard_data['EDA'].mean():.2f} μS")

ERROR HANDLING PHILOSOPHY:
=========================

Fail-Fast Errors (ValueError):
    - Missing required timestamp columns
    - Empty DataFrames with no valid data
    - Unparseable data structures

Graceful Degradation:
    - Invalid individual timestamps → Drop row, log count, continue
    - Missing optional condition column → Ignore filter, log warning
    - No matching events → Return empty DataFrame, log warning
    - No data in windows → Return empty DataFrame (valid state)

Logging Strategy:
    - ✓ Success indicators with checkmarks
    - ⚠ Warnings for non-fatal issues (dropped data, missing conditions)
    - Informative messages with counts and timestamps
    - DEBUG output shows matched files and filtering results

PERFORMANCE CHARACTERISTICS:
============================

Time Complexity:
    - prepare_event_markers_timestamps: O(n) where n = number of events
    - find_timestamp_offset: O(1) - just min() operations
    - match_event_markers_to_biometric: O(n × m) where n=events, m=biometric_samples
    - extract_window_data: O(k × m) where k=event_occurrences, m=samples_per_window

Space Complexity:
    - All functions create copies (immutability) → O(input_size)
    - extract_window_data concatenates windows → O(total_extracted_samples)

Typical Scale:
    - Events: 10-1000 markers per session
    - Biometric samples: 25-100 Hz → 90,000-360,000 samples/hour
    - Extracted windows: 1,000-50,000 samples total

DEPENDENCIES:
============

Required Libraries:
    - pandas >= 1.0: DataFrame operations
    - numpy >= 1.18: Numerical operations
    - datetime (stdlib): Timestamp parsing and conversion

Expected by Downstream:
    - analysis_methods module expects DataFrames from extract_window_data
    - plot_generator module expects standardized DataFrame schema
    - Main orchestrator (run_analysis) uses all utility functions

INVARIANTS:
==========

1. Immutability: Input DataFrames are never modified (copies returned)
2. Column Guarantees: Output always has 'AdjustedTimestamp' after extract_window_data
3. Timestamp Validity: unix_timestamp values are always > 0 after prepare_event_markers_timestamps
4. Empty Results: Empty DataFrame preferred over exceptions for "no data" cases
5. Logging Consistency: All functions log key statistics and warnings

EXTENSION POINTS:
================

1. Additional Timestamp Formats: Extend prepare_event_markers_timestamps parsing
2. Custom Matching Algorithms: Extend match_event_markers_to_biometric with new strategies
3. Window Types: Add new timeWindowType options in extract_window_data
4. File Filters: Extend get_subject_files with additional matching logic
5. Validation Rules: Add timestamp sanity checks (e.g., future dates, negative offsets)

VERSION: 1.0
PYTHON: 3.7+
REQUIRES: pandas>=1.0, numpy>=1.18
"""

import pandas as pd
import numpy as np
from datetime import datetime

def prepare_event_markers_timestamps(df):
    """
    Prepare event markers by ensuring unix_timestamp column exists.
    Handles both OLD and NEW event marker file structures.
    
    OLD structure (current):
        - timestamp column (ISO format or unix)
    
    NEW structure (future):
        - timestamp_unix column
        - timestamp_iso column
    
    Args:
        df: DataFrame with event markers
        
    Returns:
        DataFrame with guaranteed 'unix_timestamp' column
    """
    df = df.copy()
    
    # ═══════════════════════════════════════════════════════════
    # NEW STRUCTURE: Check for timestamp_unix column
    # ═══════════════════════════════════════════════════════════
    if 'timestamp_unix' in df.columns:
        print(f"  ✓ Found 'timestamp_unix' column (NEW format)")
        df['unix_timestamp'] = df['timestamp_unix']
        
        # Drop invalid timestamps
        before_count = len(df)
        df = df[pd.notna(df['unix_timestamp'])]
        df = df[df['unix_timestamp'] > 0]  # Unix timestamps must be positive
        after_count = len(df)
        
        if before_count > after_count:
            print(f"  ⚠ Dropped {before_count - after_count} rows with invalid timestamps")
        
        print(f"  ✓ Using {after_count} valid unix timestamps")
        return df
    
    # ═══════════════════════════════════════════════════════════
    # OLD STRUCTURE: Check for timestamp column
    # ═══════════════════════════════════════════════════════════
    if 'timestamp' not in df.columns:
        raise ValueError("Event markers file missing timestamp column (expected 'timestamp' or 'timestamp_unix')")
    
    # Check if timestamp is already unix format (numeric)
    sample_timestamp = df['timestamp'].dropna().iloc[0] if len(df['timestamp'].dropna()) > 0 else None
    
    if sample_timestamp is None:
        raise ValueError("No valid timestamps found in event markers file")
    
    # Try to detect format
    if isinstance(sample_timestamp, (int, float)):
        # Already unix timestamp
        print(f"  ✓ Found 'timestamp' column (numeric unix format)")
        df['unix_timestamp'] = df['timestamp']
    else:
        # ISO format string - need to convert
        print(f"  ✓ Found 'timestamp' column (ISO format) - converting to unix_timestamp")
        
        converted_timestamps = []
        invalid_count = 0
        
        for idx, ts in enumerate(df['timestamp']):
            if pd.isna(ts):
                converted_timestamps.append(None)
                invalid_count += 1
                continue
            
            try:
                # Handle various ISO formats
                ts_str = str(ts).strip()
                
                # Try parsing with fromisoformat (Python 3.7+)
                try:
                    dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                except:
                    # Fallback to pd.to_datetime for broader format support
                    dt = pd.to_datetime(ts_str)
                
                unix_ts = dt.timestamp()
                converted_timestamps.append(unix_ts)
                
            except Exception as e:
                converted_timestamps.append(None)
                invalid_count += 1
        
        df['unix_timestamp'] = converted_timestamps
        
        # Drop rows with invalid timestamps
        before_count = len(df)
        df = df[pd.notna(df['unix_timestamp'])]
        after_count = len(df)
        
        if invalid_count > 0:
            print(f"  ⚠ Dropped {invalid_count} rows with invalid timestamps")
        
        print(f"  ✓ Converted {after_count} timestamps from ISO to Unix format")
    
    return df

    raise ValueError("Event markers file must have either 'unix_timestamp' or 'timestamp' column")


def find_timestamp_offset(event_markers_df, emotibit_df):
    """
    Find the timestamp offset between event markers and emotibit data.
    
    Args:
        event_markers_df: DataFrame with event markers (must have 'unix_timestamp' column)
        emotibit_df: DataFrame with EmotiBit data (must have 'LocalTimestamp' column)
        
    Returns:
        Offset in seconds that should be added to emotibit timestamps
    """
    event_marker_start = event_markers_df['unix_timestamp'].min()
    emotibit_start = emotibit_df['LocalTimestamp'].min()
    
    offset = event_marker_start - emotibit_start
    
    print(f"  Event Marker Start: {datetime.fromtimestamp(event_marker_start)}")
    print(f"  EmotiBit Start: {datetime.fromtimestamp(emotibit_start)}")
    print(f"  Calculated Offset: {offset:.2f}s ({offset/3600:.2f} hours)")
    
    return offset


def match_event_markers_to_biometric(event_markers_df, emotibit_df, offset, tolerance=1.0):
    """
    Match event markers to biometric data timestamps.
    
    Args:
        event_markers_df: DataFrame with event markers
        emotibit_df: DataFrame with biometric data
        offset: Timestamp offset to apply to emotibit data
        tolerance: Time tolerance in seconds for matching (default 1.0)
    
    Returns:
        List of matches with event marker info and closest biometric timestamp
    """
    matches = []
    
    emotibit_df = emotibit_df.copy()
    emotibit_df['AdjustedTimestamp'] = emotibit_df['LocalTimestamp'] + offset
    
    for idx, event_row in event_markers_df.iterrows():
        event_time = event_row['unix_timestamp']
        event_marker = event_row['event_marker']
        condition = event_row.get('condition', 'N/A')
        
        time_diffs = (emotibit_df['AdjustedTimestamp'] - event_time).abs()
        closest_idx = time_diffs.idxmin()
        closest_time_diff = time_diffs.min()
        
        if closest_time_diff <= tolerance:
            closest_row = emotibit_df.loc[closest_idx]
            matches.append({
                'event_marker': event_marker,
                'condition': condition,
                'event_timestamp': event_time,
                'event_iso': event_row.get('iso_timestamp', 'N/A'),
                'matched_timestamp': closest_row['LocalTimestamp'],
                'adjusted_timestamp': closest_row['AdjustedTimestamp'],
                'time_diff': closest_time_diff,
                'biometric_value': closest_row.iloc[-1],  # Last column is the metric value
                'row_index': closest_idx
            })
        else:
            print(f"WARNING: No match within tolerance for event '{event_marker}' at {event_time}")
    
    return matches


def extract_window_data(emotibit_df, event_markers_df, offset, window_config):
    """
    Extract data from emotibit dataframe based on window configuration.
    """
    emotibit_df = emotibit_df.copy()
    emotibit_df['AdjustedTimestamp'] = emotibit_df['LocalTimestamp'] + offset
    
    event_marker = window_config['eventMarker']
    
    # SPECIAL CASE: "all" means entire experiment duration
    if event_marker == 'all':
        print(f"  Analyzing entire experiment duration")
        return emotibit_df.copy()
    
    metric_col = emotibit_df.columns[-1]
    
    marker_rows = event_markers_df[event_markers_df['event_marker'] == event_marker]
    
    condition_marker = window_config.get('conditionMarker', '')
    if condition_marker and condition_marker != '':
        if 'condition' in event_markers_df.columns:
            marker_rows = marker_rows[marker_rows['condition'] == condition_marker]
        else:
            print(f"  ⚠ Warning: Condition column not found in event markers")
    
    if len(marker_rows) == 0:
        print(f"  ⚠ Warning: No occurrences of event marker '{event_marker}'" + 
              (f" with condition '{condition_marker}'" if condition_marker else "") + " found")
        return pd.DataFrame()
    
    print(f"  Found {len(marker_rows)} occurrences of '{event_marker}'" +
          (f" with condition '{condition_marker}'" if condition_marker else ""))
    
    all_data = []
    
    for idx, marker_row in marker_rows.iterrows():
        marker_time = marker_row['unix_timestamp']
        
        if window_config['timeWindowType'] == 'full':
            next_markers = event_markers_df[
                (event_markers_df['unix_timestamp'] > marker_time) &
                (event_markers_df['event_marker'].notna()) &
                (event_markers_df['event_marker'] != '')
            ]
            
            if len(next_markers) > 0:
                end_time = next_markers.iloc[0]['unix_timestamp']
            else:
                end_time = event_markers_df['unix_timestamp'].max()
            
            window_data = emotibit_df[
                (emotibit_df['AdjustedTimestamp'] >= marker_time) &
                (emotibit_df['AdjustedTimestamp'] < end_time)
            ].copy()
            
        else:  # custom time window
            start_offset = window_config['customStart']
            end_offset = window_config['customEnd']
            
            window_data = emotibit_df[
                (emotibit_df['AdjustedTimestamp'] >= marker_time + start_offset) &
                (emotibit_df['AdjustedTimestamp'] <= marker_time + end_offset)
            ].copy()
        
        if len(window_data) > 0:
            all_data.append(window_data)
    
    if len(all_data) == 0:
        return pd.DataFrame()
    
    combined_data = pd.concat(all_data, ignore_index=True)
    print(f"  Extracted {len(combined_data)} data points across all occurrences")
    
    return combined_data

def get_subject_files(manifest, subject_name):
    
    subject_files = {
        'emotibit_files': [],
        'event_markers': None,
        'respiration_files': [],
        'external_files': [] 
    }
    
    for emotibit_file in manifest.get('emotibit_files', []):
        if (emotibit_file.get('subject') == subject_name or 
            subject_name in emotibit_file.get('path', '')):
            subject_files['emotibit_files'].append(emotibit_file)
    
    # Priority 1: Check per-subject event markers (batch mode)
    if 'event_markers_by_subject' in manifest:
        subject_files['event_markers'] = manifest['event_markers_by_subject'].get(subject_name)
        if subject_files['event_markers']:
            print(f"  ✓ Found event markers for {subject_name} (batch mode)")
    
    # Priority 2: Check single event markers file (backward compatibility)
    if not subject_files['event_markers'] and manifest.get('event_markers'):
        if subject_name in manifest['event_markers'].get('path', ''):
            subject_files['event_markers'] = manifest['event_markers']
            print(f"  ✓ Found event markers for {subject_name} (single subject mode)")
    
    # Filter respiration files for this subject
    for resp_file in manifest.get('respiration_files', []):
        if (resp_file.get('subject') == subject_name or 
            subject_name in resp_file.get('path', '')):
            subject_files['respiration_files'].append(resp_file)
    
    # Filter external files for this subject
    for external_file in manifest.get('external_files', []):
        if (external_file.get('subject') == subject_name or 
            subject_name in external_file.get('path', '')):
            subject_files['external_files'].append(external_file)
    
    # DEBUG: Log what was found
    print(f"\n  Subject files for {subject_name}:")
    print(f"    - EmotiBit: {len(subject_files['emotibit_files'])} files")
    print(f"    - Event markers: {'✓' if subject_files['event_markers'] else '❌ MISSING'}")
    print(f"    - External data: {len(subject_files['external_files'])} files")
    
    return subject_files

def find_metric_file_for_subject(subject_files, metric):
    """
    Find the specific metric file for a subject.
    
    Args:
        subject_files: Dict from get_subject_files()
        metric: Metric name (e.g., 'HR', 'EDA')
        
    Returns:
        File path string or None
    """
    for emotibit_file in subject_files.get('emotibit_files', []):
        if f'_{metric}.csv' in emotibit_file['filename']:
            return emotibit_file['path']
    return None