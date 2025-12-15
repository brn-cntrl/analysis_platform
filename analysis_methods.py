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