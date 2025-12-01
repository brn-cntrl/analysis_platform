"""
Shared utility functions for EmotiBit data analysis.
Used by both the Flask app and Jupyter notebook.
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