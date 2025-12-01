"""
BIOMETRIC DATA ANALYSIS MODULE - LLM CONTRACT
==============================================

PURPOSE:
This module provides statistical analysis methods for time-series biometric data (e.g., heart rate,
temperature, activity metrics). It transforms raw sensor data into meaningful analytical outputs
using various signal processing techniques.

CORE CONTRACT:
--------------
Input Requirements:
    - data: pandas DataFrame with at minimum:
        * 'AdjustedTimestamp': numeric timestamp column (required)
        * metric_col: numeric column with biometric measurements (required)
    - metric_col: string name of the column to analyze
    - method: one of ['raw', 'mean', 'moving_average', 'rmssd']

Output Guarantees:
    - Returns pandas DataFrame with same schema as input (except 'rmssd' which has n-1 rows)
    - All numeric values are JSON-serializable (NaN replaced with 0.0)
    - Original data is never mutated (copies are returned)

ANALYSIS METHODS CONTRACT:
--------------------------

1. 'raw' - Identity Transform
   Preconditions: Valid DataFrame with metric_col
   Postconditions: Returns exact copy of input data
   Use Case: Baseline visualization, no processing needed

2. 'mean' - Aggregate Statistics
   Preconditions: metric_col contains numeric data
   Postconditions: Returns single-row DataFrame with:
       - AdjustedTimestamp: mean of all timestamps
       - metric_col: mean of all metric values
   Use Case: Single summary value for entire dataset

3. 'moving_average' - Temporal Smoothing
   Preconditions: 
       - Numeric metric_col
       - Optional window_size parameter (default=30)
   Postconditions: Returns DataFrame with same row count where:
       - metric_col contains smoothed values using centered rolling window
       - Edge cases handled with min_periods=1
   Use Case: Noise reduction, trend identification
   
4. 'rmssd' - Variability Analysis (Root Mean Square of Successive Differences)
   Preconditions: metric_col has at least 2 data points
   Postconditions: Returns DataFrame with n-1 rows where:
       - metric_col contains successive differences (values[i+1] - values[i])
       - DataFrame.attrs['rmssd'] contains the RMSSD scalar value
   Use Case: Heart rate variability, signal stability analysis
   Mathematical Formula: RMSSD = sqrt(mean(diff(values)^2))

STATISTICS CONTRACT:
-------------------
Function: calculate_statistics(data, metric_col, method)

Returns dictionary with guaranteed keys:
    - 'mean': float (average of values, 0.0 if empty)
    - 'std': float (standard deviation, 0.0 if empty or single value)
    - 'min': float (minimum value, 0.0 if empty)
    - 'max': float (maximum value, 0.0 if empty)
    - 'count': int (number of non-null values)

Method-specific additions:
    - 'rmssd' method adds 'rmssd': float key
    - 'moving_average' method adds 'smoothness': float (coefficient of variation)

NaN Handling: All NaN values are replaced with 0.0 for JSON compatibility

ERROR HANDLING:
--------------
- ValueError raised for unknown method names
- Empty datasets return zeros for all statistics (no exceptions)
- Missing metric_col will raise KeyError (intentional fail-fast)
- NaN values in metric_col are dropped before statistics calculation

DEPENDENCIES:
------------
- pandas: DataFrame operations
- numpy: Numerical computations (diff, mean, sqrt)
- scipy.signal: Imported but unused (reserved for future signal processing)

USAGE EXAMPLES:
--------------

Example 1 - Get raw data with statistics:
    >>> processed = apply_analysis_method(df, 'heart_rate', method='raw')
    >>> stats = calculate_statistics(processed, 'heart_rate', method='raw')
    >>> print(stats['mean'])  # Average heart rate

Example 2 - Smooth noisy data:
    >>> smoothed = apply_analysis_method(df, 'temperature', 
    ...                                   method='moving_average', 
    ...                                   window_size=60)

Example 3 - Calculate heart rate variability:
    >>> hrv_data = apply_analysis_method(df, 'heart_rate', method='rmssd')
    >>> stats = calculate_statistics(hrv_data, 'heart_rate', method='rmssd')
    >>> print(stats['rmssd'])  # Overall variability measure

Example 4 - Get single summary value:
    >>> summary = apply_analysis_method(df, 'steps', method='mean')
    >>> # Returns single row with average steps

INVARIANTS:
----------
1. Input DataFrame is never modified (immutability)
2. Output always has 'AdjustedTimestamp' and metric_col columns
3. All statistics are JSON-serializable floats/ints
4. Row count: same as input (except rmssd: n-1, mean: 1)
5. Column schema preserved (except mean which may reorder)

EXTENSION POINTS:
----------------
- Add new methods by extending apply_analysis_method() switch statement
- Each new method should return DataFrame with compatible schema
- Update calculate_statistics() for method-specific metrics
- Add method to get_method_label() for UI display

VERSION: 1.0
PYTHON: 3.7+
"""
import pandas as pd
import numpy as np
from scipy import signal

def apply_analysis_method(data, metric_col, method='raw', **kwargs):
    """
    Apply specified analysis method to the data.
    
    Args:
        data: DataFrame with biometric data
        metric_col: Name of the column containing metric values
        method: Analysis method to apply ('raw', 'mean', 'moving_average', 'rmssd')
        **kwargs: Additional parameters for specific methods
        
    Returns:
        Processed DataFrame with results
    """
    if method == 'raw':
        return apply_raw(data, metric_col)
    elif method == 'mean':
        return apply_mean(data, metric_col)
    elif method == 'moving_average':
        window_size = kwargs.get('window_size', 30)
        return apply_moving_average(data, metric_col, window_size)
    elif method == 'rmssd':
        return apply_rmssd(data, metric_col)
    else:
        raise ValueError(f"Unknown analysis method: {method}")


def apply_raw(data, metric_col):
    """
    Return raw data as-is.
    
    Args:
        data: DataFrame with biometric data
        metric_col: Name of the column containing metric values
        
    Returns:
        Original DataFrame
    """
    return data.copy()


def apply_mean(data, metric_col):
    """
    Calculate mean value for the entire dataset.
    Returns a single-row DataFrame with the mean.
    
    Args:
        data: DataFrame with biometric data
        metric_col: Name of the column containing metric values
        
    Returns:
        DataFrame with single row containing mean value
    """
    mean_value = data[metric_col].mean()
    
    result = pd.DataFrame({
        'AdjustedTimestamp': [data['AdjustedTimestamp'].mean()],
        metric_col: [mean_value]
    })
    
    return result


def apply_moving_average(data, metric_col, window_size=30):
    """
    Apply moving average smoothing to the data.
    
    Args:
        data: DataFrame with biometric data
        metric_col: Name of the column containing metric values
        window_size: Size of moving average window (default 30)
        
    Returns:
        DataFrame with smoothed values
    """
    result = data.copy()
    
    # Apply moving average
    result[metric_col] = result[metric_col].rolling(
        window=window_size, 
        center=True, 
        min_periods=1
    ).mean()
    
    return result


def apply_rmssd(data, metric_col):
    """
    Calculate Root Mean Square of Successive Differences (RMSSD).
    Useful for HRV and variability analysis.
    
    Args:
        data: DataFrame with biometric data
        metric_col: Name of the column containing metric values
        
    Returns:
        DataFrame with RMSSD values (successive differences)
    """
    result = data.copy()
    
    # Calculate successive differences
    values = result[metric_col].values
    successive_diffs = np.diff(values)
    
    # Calculate RMSSD
    squared_diffs = successive_diffs ** 2
    rmssd_value = np.sqrt(np.mean(squared_diffs))
    
    # Store successive differences as the transformed metric
    # Note: This will have one less data point than original
    result = result.iloc[:-1].copy()  # Remove last row to match diff length
    result[metric_col] = successive_diffs
    
    # Add RMSSD as metadata (will be used in statistics)
    result.attrs['rmssd'] = rmssd_value
    
    return result


def calculate_statistics(data, metric_col, method='raw'):
    """
    Calculate statistics appropriate for the analysis method.
    
    Args:
        data: DataFrame with (potentially transformed) biometric data
        metric_col: Name of the column containing metric values
        method: Analysis method used
        
    Returns:
        Dictionary with statistical measures
    """
    values = data[metric_col].dropna()
    
    if len(values) == 0:
        return {
            'mean': 0,
            'std': 0,
            'min': 0,
            'max': 0,
            'count': 0
        }
    
    # Calculate statistics with NaN handling for JSON serialization
    mean_val = float(values.mean())
    std_val = float(values.std())
    min_val = float(values.min())
    max_val = float(values.max())
    
    # Replace NaN with 0 for JSON compatibility (single data point has no std deviation)
    if np.isnan(std_val):
        std_val = 0.0
    if np.isnan(mean_val):
        mean_val = 0.0
    if np.isnan(min_val):
        min_val = 0.0
    if np.isnan(max_val):
        max_val = 0.0
    
    stats = {
        'mean': mean_val,
        'std': std_val,
        'min': min_val,
        'max': max_val,
        'count': int(len(values))
    }
    
    # Add method-specific statistics
    if method == 'rmssd' and hasattr(data, 'attrs') and 'rmssd' in data.attrs:
        stats['rmssd'] = float(data.attrs['rmssd'])
    
    if method == 'moving_average':
        # Add smoothness metric (less variance = smoother)
        stats['smoothness'] = float(values.std() / values.mean()) if values.mean() != 0 else 0
    
    return stats


def get_method_label(method):
    """
    Get human-readable label for analysis method.
    
    Args:
        method: Method identifier
        
    Returns:
        Human-readable string
    """
    labels = {
        'raw': 'Raw Data',
        'mean': 'Mean Value',
        'moving_average': 'Moving Average',
        'rmssd': 'RMSSD (Successive Differences)'
    }
    return labels.get(method, method)