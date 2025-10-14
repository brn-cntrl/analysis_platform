"""
Shared utility functions for EmotiBit data analysis.
Used by both the Flask app and Jupyter notebook.
"""

import pandas as pd
import numpy as np
from datetime import datetime

def prepare_event_markers_timestamps(event_markers_df):
    """
    Prepare event markers dataframe to ensure it has unix_timestamp column.
    Handles backward compatibility for files that use 'timestamp' with ISO format.
    
    Args:
        event_markers_df: DataFrame with event marker data
        
    Returns:
        Modified dataframe with 'unix_timestamp' column
    """
    df = event_markers_df.copy()
    
    # Check if unix_timestamp already exists
    if 'unix_timestamp' in df.columns:
        print("  ✓ Found 'unix_timestamp' column")
        return df
    
    # Check for 'timestamp' column (backward compatibility)
    if 'timestamp' in df.columns:
        print("  ✓ Found 'timestamp' column (ISO format) - converting to unix_timestamp")
        
        # Convert ISO format timestamps to Unix timestamps
        dt_series = pd.to_datetime(df['timestamp'], errors='coerce')
        df['unix_timestamp'] = (dt_series - pd.Timestamp("1970-01-01")) / pd.Timedelta('1s')
        
        # Drop NaN values
        before = len(df)
        df = df.dropna(subset=['unix_timestamp'])
        after = len(df)
        
        if before > after:
            print(f"  ⚠ Dropped {before - after} rows with invalid timestamps")
        
        print(f"  ✓ Converted {after} timestamps from ISO to Unix format")
        
        return df
    
    # Neither column found
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
    
    # Apply offset to emotibit timestamps
    emotibit_df = emotibit_df.copy()
    emotibit_df['AdjustedTimestamp'] = emotibit_df['LocalTimestamp'] + offset
    
    # For each event marker, find the closest biometric timestamp
    for idx, event_row in event_markers_df.iterrows():
        event_time = event_row['unix_timestamp']
        event_marker = event_row['event_marker']
        condition = event_row.get('condition', 'N/A')
        
        # Find closest timestamp in emotibit data
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
    
    Args:
        emotibit_df: DataFrame with biometric data
        event_markers_df: DataFrame with event markers
        offset: Timestamp offset to apply
        window_config: Dict with 'eventMarker', 'timeWindowType', 'customStart', 'customEnd'
    
    Returns:
        DataFrame with data from the specified window
    """
    # Apply offset to emotibit timestamps
    emotibit_df = emotibit_df.copy()
    emotibit_df['AdjustedTimestamp'] = emotibit_df['LocalTimestamp'] + offset
    
    # Get the metric column name (last column)
    metric_col = emotibit_df.columns[-1]
    
    # Find all occurrences of the event marker
    event_marker = window_config['eventMarker']
    marker_rows = event_markers_df[event_markers_df['event_marker'] == event_marker]
    
    if len(marker_rows) == 0:
        print(f"  ⚠ Warning: No occurrences of event marker '{event_marker}' found")
        return pd.DataFrame()
    
    print(f"  Found {len(marker_rows)} occurrences of '{event_marker}'")
    
    # Extract data for each occurrence
    all_data = []
    
    for idx, marker_row in marker_rows.iterrows():
        marker_time = marker_row['unix_timestamp']
        
        if window_config['timeWindowType'] == 'full':
            # Full event duration - find next event marker or end of data
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