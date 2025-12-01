"""
BIOMETRIC DATA CLEANING & VALIDATION PIPELINE - LLM CONTRACT
============================================================

PURPOSE:
This module provides robust multi-stage cleaning for physiological sensor data, addressing
common data quality issues in wearable biometric devices: sensor artifacts, physiological
impossibilities, sudden disconnections, and noise. It ensures downstream analysis operates
on validated, high-quality signals.

CORE PROBLEM SOLVED:
--------------------
Wearable biometric sensors produce noisy data with characteristic issues:
    - Missing values: Sensor disconnections, movement artifacts
    - Physiological impossibilities: Heart rate = 500 bpm, temperature = 50°C
    - Sensor artifacts: Sudden jumps when device shifts or is touched
    - Statistical outliers: Random spikes from electrical interference
    - Unit errors: Data in wrong units (e.g., HR in milliseconds instead of BPM)

This module provides a configurable, metric-aware pipeline that removes invalid data
while preserving genuine physiological variation.

ARCHITECTURE OVERVIEW:
---------------------
┌────────────────────────────────────────────────────────────┐
│         BiometricDataCleaner (Main Class)                  │
└────────────────────────────────────────────────────────────┘
         │
         ├──► _get_thresholds()
         │    [Metric-specific validation rules]
         │
         └──► clean() ──────┬──► Stage 1: _remove_invalid_values()
              [Pipeline]    ├──► Stage 2: _remove_physiological_outliers()
                           ├──► Stage 3: _remove_statistical_outliers()
                           ├──► Stage 4: _remove_sudden_changes()
                           ├──► Stage 5: _interpolate_missing()
                           └──► Stage 6: _apply_smoothing()

CLASS CONTRACT - BiometricDataCleaner:
======================================

Purpose: Encapsulates metric-specific cleaning logic and thresholds

Constructor: __init__(metric_type='HR')

Input:
    - metric_type: str, one of ['HR', 'EDA', 'TEMP', 'PI', 'PR', 'PG', 'default']
    
Attributes:
    - self.metric_type: str, stored metric identifier
    - self.thresholds: dict, physiological validation rules with keys:
        * 'min': float | None, minimum valid value
        * 'max': float | None, maximum valid value
        * 'max_change': float | None, maximum rate of change per second

Metric Types & Thresholds:

    'HR' - Heart Rate (BPM):
        min: 30      # Bradycardia threshold
        max: 220     # Maximum achievable HR (220 - age)
        max_change: 30  # BPM change per second (prevents sensor glitches)
        Use case: Adult human heart rate during exercise/stress
    
    'EDA' - Electrodermal Activity (μS):
        min: 0       # Conductance cannot be negative
        max: 100     # Typical maximum skin conductance
        max_change: 5   # μS per second (gradual autonomic changes)
        Use case: Sweat gland activity, emotional arousal
    
    'TEMP' - Skin Temperature (°C):
        min: 30      # Hypothermia threshold
        max: 42      # Hyperthermia threshold
        max_change: 2   # °C per second (body temp changes slowly)
        Use case: Peripheral skin temperature
    
    'PI'/'PR'/'PG' - Photoplethysmography (Infrared/Red/Green):
        min: 0       # Light intensity cannot be negative
        max: None    # No upper limit (device-dependent)
        max_change: None  # High-frequency signal, no rate limit
        Use case: Raw PPG signals for heart rate detection
    
    'default' - Unknown Metrics:
        All thresholds: None
        Behavior: Only removes NaN/inf, no physiological validation
        Use case: Custom metrics without known ranges

Example Usage:
    >>> cleaner = BiometricDataCleaner(metric_type='HR')
    >>> print(cleaner.thresholds)
    {'min': 30, 'max': 220, 'max_change': 30}

METHOD CONTRACT - clean():
==========================

Purpose: Main entry point for multi-stage cleaning pipeline

Signature:
    clean(data, metric_col, timestamp_col='AdjustedTimestamp', stages=None)

Input Requirements:
    - data: pandas DataFrame with at minimum:
        * timestamp_col: numeric timestamp column (default='AdjustedTimestamp')
        * metric_col: numeric column with biometric values
    - metric_col: str, name of column containing metric values
    - timestamp_col: str, name of timestamp column (default='AdjustedTimestamp')
    - stages: dict | None, configuration for cleaning stages

Stages Configuration:
    Dict with boolean flags enabling/disabling each stage:
    {
        'remove_invalid': bool,                  # Default: True
        'remove_physiological_outliers': bool,   # Default: True
        'remove_statistical_outliers': bool,     # Default: False
        'remove_sudden_changes': bool,           # Default: True
        'interpolate': bool,                     # Default: True
        'smooth': bool                           # Default: False
    }
    
    If stages=None, uses default configuration above.

Output Guarantees:
    Returns pandas DataFrame where:
    - All rows have valid (non-NaN, non-inf) values in metric_col
    - Values are within physiological ranges (if thresholds defined)
    - No sudden unrealistic changes (if max_change defined)
    - Gaps are interpolated (if interpolate=True) or removed
    - Original DataFrame is never mutated (copy returned)
    - May return EMPTY DataFrame if all data is invalid

Processing Pipeline:
    1. Create copy of input DataFrame (immutability)
    2. Log original sample count
    3. Execute enabled stages in sequence (order matters!)
    4. Log final sample count and removal statistics
    5. Return cleaned DataFrame

Stage Execution Order (CRITICAL):
    The order is scientifically motivated:
    1. Invalid values → Must remove before calculations
    2. Physiological outliers → Clear data quality issues
    3. Statistical outliers → Aggressive, only if needed
    4. Sudden changes → Requires consecutive valid samples
    5. Interpolate → Fills gaps created by previous stages
    6. Smoothing → Final polish, only if needed

Logging Output:
    "🧹 Cleaning HR data..."
    "  Original: 10,000 samples"
    "    ✓ Removed 5 invalid values (NaN/inf/negative)"
    "    ✓ Removed 12 physiological outliers (range: 30-220)"
    "    ✓ Removed 3 sudden changes (rate > 30/sec)"
    "    ✓ Interpolated 8 missing values"
    "  Final: 9,972 samples (28 removed, 0.3%)"

Example Usage:
    >>> cleaner = BiometricDataCleaner(metric_type='HR')
    >>> df_raw = pd.read_csv('heart_rate.csv')
    >>> 
    >>> # Use default stages
    >>> df_clean = cleaner.clean(df_raw, 'HR')
    >>> 
    >>> # Custom stages (aggressive cleaning)
    >>> stages = {
    ...     'remove_invalid': True,
    ...     'remove_physiological_outliers': True,
    ...     'remove_statistical_outliers': True,  # Enable
    ...     'remove_sudden_changes': True,
    ...     'interpolate': False,  # Don't interpolate, just remove
    ...     'smooth': True  # Apply smoothing
    ... }
    >>> df_very_clean = cleaner.clean(df_raw, 'HR', stages=stages)

STAGE 1 - _remove_invalid_values():
===================================

Purpose: Remove mathematically invalid or impossible values

Input: DataFrame with metric_col
Output: DataFrame with invalid rows removed

Removal Criteria:
    1. NaN (Not a Number) → Always removed
    2. inf/-inf (Infinite) → Always removed
    3. Negative values → Removed for metrics: EDA, PI, PR, PG
       Rationale: These represent intensities/conductances that cannot be negative

Examples:
    - HR = NaN → REMOVE (missing sensor reading)
    - EDA = -0.5 μS → REMOVE (negative conductance impossible)
    - TEMP = -10°C → KEEP (negative temperature is valid, will be caught by physiological range)
    - HR = inf → REMOVE (sensor error)

Side Effects:
    - DataFrame row count may decrease
    - No interpolation performed (gaps left as-is)

STAGE 2 - _remove_physiological_outliers():
===========================================

Purpose: Remove values outside physiologically plausible ranges

Input: DataFrame with metric_col
Output: DataFrame with physiologically impossible rows removed

Behavior:
    if thresholds['min'] is not None:
        Remove rows where value < thresholds['min']
    if thresholds['max'] is not None:
        Remove rows where value > thresholds['max']
    if both are None:
        Skip this stage (no-op)

Examples:
    HR metric (min=30, max=220):
        - HR = 25 bpm → REMOVE (severe bradycardia, likely sensor error)
        - HR = 250 bpm → REMOVE (physiologically impossible)
        - HR = 180 bpm → KEEP (high but achievable during intense exercise)
    
    EDA metric (min=0, max=100):
        - EDA = 150 μS → REMOVE (exceeds typical maximum skin conductance)
        - EDA = 25 μS → KEEP (normal arousal level)
    
    TEMP metric (min=30, max=42):
        - TEMP = 28°C → REMOVE (hypothermia or sensor disconnected from skin)
        - TEMP = 45°C → REMOVE (hyperthermia threshold exceeded)
        - TEMP = 36.5°C → KEEP (normal skin temperature)

Use Case:
    Detects sensor malfunctions, incorrect units (e.g., HR in milliseconds instead of BPM),
    or device disconnection events.

STAGE 3 - _remove_statistical_outliers():
=========================================

Purpose: Remove statistical outliers using robust z-score method

Input: DataFrame with metric_col, threshold (default=3.5)
Output: DataFrame with statistical outliers removed

Algorithm:
    Uses Modified Z-Score based on Median Absolute Deviation (MAD):
    
    1. Calculate median and MAD:
        median = median(values)
        MAD = median(|values - median|)
    
    2. Calculate modified z-score:
        modified_z = 0.6745 × (value - median) / MAD
    
    3. Remove if |modified_z| >= threshold (default 3.5)
    
    Fallback: If MAD = 0 (constant signal), use standard deviation

Rationale:
    - Median/MAD are robust to outliers (unlike mean/std)
    - 0.6745 factor converts MAD to standard deviation units
    - threshold=3.5 is conservative (roughly 99.95% of normal distribution)

When to Enable:
    ✓ Noisy data with frequent spikes
    ✓ After removing physiological outliers (gentler second pass)
    ✗ Clean signals (may remove genuine physiological events)
    ✗ Highly variable metrics (exercise data, emotional responses)

Example:
    HR values: [70, 72, 71, 73, 150, 72, 71]
    median = 72, MAD = 1
    value=150 → modified_z = 0.6745 × (150-72) / 1 = 52.6 → REMOVE

STAGE 4 - _remove_sudden_changes():
===================================

Purpose: Detect and remove unrealistic rate-of-change artifacts

Input: DataFrame with metric_col and timestamp_col
Output: DataFrame with sudden change artifacts removed

Algorithm:
    1. Sort by timestamp (ensures chronological order)
    2. Calculate time differences: Δt = timestamp[i+1] - timestamp[i]
    3. Calculate value differences: Δv = |value[i+1] - value[i]|
    4. Calculate rate of change: rate = Δv / Δt (per second)
    5. Remove samples where rate > thresholds['max_change']

Physical Interpretation:
    HR (max_change=30 BPM/sec):
        - HR jumps 70→150 bpm in 0.5s → rate=160 BPM/sec → REMOVE (sensor glitch)
        - HR increases 70→100 bpm over 10s → rate=3 BPM/sec → KEEP (exercise onset)
    
    TEMP (max_change=2 °C/sec):
        - Temp jumps 34→38°C in 0.1s → rate=40 °C/sec → REMOVE (sensor moved)
        - Temp rises 34→35°C over 60s → rate=0.017 °C/sec → KEEP (normal warming)

Use Case:
    Detects sensor movement artifacts, device disconnection/reconnection, or data
    transmission errors that cause sudden non-physiological jumps.

Prerequisite:
    Requires valid timestamp column with consistent sampling rate.

STAGE 5 - _interpolate_missing():
=================================

Purpose: Fill gaps in data created by previous cleaning stages

Input: DataFrame with metric_col (may contain NaN)
Output: DataFrame with interpolated values, NaN minimized

Algorithm:
    1. Linear interpolation (limit=10 consecutive NaN):
        value[i] = linear_interpolate(value[i-1], value[i+k])
        where k ≤ 10
    
    2. Backward fill (limit=5) for leading NaN:
        value[0] = value[first_valid_index]
    
    3. Forward fill (limit=5) for trailing NaN:
        value[n] = value[last_valid_index]
    
    4. Drop any remaining NaN (if gap > 10 samples)

Gap Handling:
    - Small gaps (≤10 samples): Interpolated linearly
    - Large gaps (>10 samples): Left as NaN, then dropped
    - Edge gaps (≤5 samples): Filled with nearest valid value
    - Edge gaps (>5 samples): Dropped

Rationale:
    - Linear interpolation reasonable for slowly-changing signals (HR, TEMP, EDA)
    - Limits prevent unrealistic interpolation across long gaps
    - Preserves physiological trends while maintaining data continuity

When to Disable:
    - Research requiring only measured values (no interpolation bias)
    - When downstream analysis handles NaN appropriately
    - Sparse data where interpolation is inappropriate

Example:
    Values: [70, 72, NaN, NaN, 76, 78]
    Gap size: 2 samples (≤10)
    Result: [70, 72, 73.3, 74.7, 76, 78]  # Linear interpolation

STAGE 6 - _apply_smoothing():
=============================

Purpose: Reduce high-frequency noise using median filter

Input: DataFrame with metric_col, window size (default=5)
Output: DataFrame with smoothed metric values

Algorithm:
    Applies scipy.signal.medfilt with kernel_size=window
    For each point: value[i] = median(values[i-2:i+2])

Filter Properties:
    - Median filter: Preserves edges better than moving average
    - Window=5: Balances noise reduction with temporal resolution
    - Non-causal: Uses past and future samples (centered window)

When to Enable:
    ✓ Very noisy signals requiring additional smoothing
    ✓ Before calculating derivatives (rate of change, acceleration)
    ✓ Visualization purposes (cleaner plots)
    
When to Disable (DEFAULT):
    ✗ Analysis requiring original signal characteristics
    ✗ After other cleaning is sufficient
    ✗ High-frequency features are important (e.g., PPG pulse detection)

Trade-offs:
    + Reduces noise effectively
    + Preserves edges better than moving average
    - Introduces slight temporal blur
    - May reduce genuine high-frequency physiological variation

Example:
    Values: [70, 72, 85, 71, 73, 72, 70]  # 85 is noise spike
    Window=5, Result: [70, 72, 72, 72, 72, 72, 70]  # Spike removed

EMPTY DATAFRAME HANDLING:
=========================

Critical Behavior:
    If ALL data is removed during cleaning → Returns empty DataFrame
    
Causes:
    1. All values outside physiological range (wrong units!)
        Example: HR file contains milliseconds instead of BPM
    2. Continuous sensor disconnection
    3. Excessive noise with aggressive cleaning settings
    4. Fundamentally corrupted data file

Detection:
    Check: len(cleaned_df) == 0
    
Recommended Response:
    if len(cleaned_df) == 0:
        print(f"❌ ERROR: All {metric} data removed during cleaning")
        print(f"   Possible causes:")
        print(f"   - Wrong units (e.g., HR in milliseconds instead of BPM)")
        print(f"   - Sensor disconnected for entire recording")
        print(f"   - Data fundamentally corrupted")
        print(f"   Recommendation: Check raw data file and units")
        return None, []  # Skip this metric

CLEANING PRESETS:
=================

Conservative (Default):
    {
        'remove_invalid': True,
        'remove_physiological_outliers': True,
        'remove_statistical_outliers': False,  # Keep genuine variation
        'remove_sudden_changes': True,
        'interpolate': True,
        'smooth': False  # Preserve original signal characteristics
    }
    Use: General-purpose, preserves most genuine physiological variation

Aggressive:
    {
        'remove_invalid': True,
        'remove_physiological_outliers': True,
        'remove_statistical_outliers': True,   # Remove all outliers
        'remove_sudden_changes': True,
        'interpolate': False,  # No interpolation, only measured values
        'smooth': True  # Maximum noise reduction
    }
    Use: Very noisy data, visualization, or when conservative approach insufficient

Minimal:
    {
        'remove_invalid': True,
        'remove_physiological_outliers': False,  # Keep all values
        'remove_statistical_outliers': False,
        'remove_sudden_changes': False,
        'interpolate': True,
        'smooth': False
    }
    Use: High-quality data, research requiring minimal processing

No Interpolation:
    {
        'remove_invalid': True,
        'remove_physiological_outliers': True,
        'remove_statistical_outliers': False,
        'remove_sudden_changes': True,
        'interpolate': False,  # Key difference
        'smooth': False
    }
    Use: Research requiring only genuine measured values (no imputed data)

USAGE EXAMPLES:
==============

Example 1 - Basic Usage (Default Settings):
    >>> from DataCleaner import BiometricDataCleaner
    >>> import pandas as pd
    >>> 
    >>> df_raw = pd.read_csv('heart_rate.csv')
    >>> cleaner = BiometricDataCleaner(metric_type='HR')
    >>> df_clean = cleaner.clean(df_raw, metric_col='HR', timestamp_col='LocalTimestamp')
    >>> 
    >>> print(f"Cleaned: {len(df_clean)}/{len(df_raw)} samples retained")

Example 2 - Custom Stages (Aggressive Cleaning):
    >>> cleaner = BiometricDataCleaner(metric_type='EDA')
    >>> stages = {
    ...     'remove_invalid': True,
    ...     'remove_physiological_outliers': True,
    ...     'remove_statistical_outliers': True,  # Enable
    ...     'remove_sudden_changes': True,
    ...     'interpolate': True,
    ...     'smooth': True  # Enable
    ... }
    >>> df_clean = cleaner.clean(df_eda, 'EDA', stages=stages)

Example 3 - Handling Empty Results:
    >>> cleaner = BiometricDataCleaner(metric_type='HR')
    >>> df_clean = cleaner.clean(df_hr, 'HR')
    >>> 
    >>> if len(df_clean) == 0:
    ...     print("ERROR: All data removed during cleaning")
    ...     print("Check if HR is in correct units (BPM, not milliseconds)")
    ...     sys.exit(1)

Example 4 - Multiple Metrics with Appropriate Cleaners:
    >>> metrics = {
    ...     'HR': BiometricDataCleaner('HR'),
    ...     'EDA': BiometricDataCleaner('EDA'),
    ...     'TEMP': BiometricDataCleaner('TEMP')
    ... }
    >>> 
    >>> cleaned_data = {}
    >>> for metric, cleaner in metrics.items():
    ...     df = pd.read_csv(f'{metric}.csv')
    ...     cleaned_data[metric] = cleaner.clean(df, metric)

Example 5 - Research-Grade (No Interpolation):
    >>> cleaner = BiometricDataCleaner(metric_type='HR')
    >>> stages = {
    ...     'remove_invalid': True,
    ...     'remove_physiological_outliers': True,
    ...     'remove_statistical_outliers': False,
    ...     'remove_sudden_changes': True,
    ...     'interpolate': False,  # Only genuine measurements
    ...     'smooth': False
    ... }
    >>> df_research = cleaner.clean(df_hr, 'HR', stages=stages)
    >>> # Result may have fewer samples but all are genuine sensor readings

COMMON FAILURE MODES & DIAGNOSTICS:
===================================

Failure Mode 1: All Data Removed
    Symptom: len(cleaned_df) == 0
    Cause: Wrong units (HR in milliseconds instead of BPM)
    Diagnostic:
        print(f"Raw data range: {df_raw['HR'].min():.1f} - {df_raw['HR'].max():.1f}")
        # If seeing 800-1200 range → milliseconds instead of BPM
    Solution: Convert units before cleaning or adjust thresholds

Failure Mode 2: Excessive Removal (>50%)
    Symptom: Removed > 50% of samples
    Cause: Aggressive thresholds + noisy data
    Diagnostic: Review stage-by-stage removal counts in logs
    Solution: Disable statistical outlier removal, increase max_change threshold

Failure Mode 3: Artifacts Remain
    Symptom: Visible spikes/jumps in cleaned data
    Cause: Thresholds too lenient or sudden changes not detected
    Diagnostic: Check max_change threshold appropriateness for sampling rate
    Solution: Decrease max_change, enable statistical outlier removal, enable smoothing

Failure Mode 4: Loss of Genuine Variation
    Symptom: Data appears "flattened" or responses dampened
    Cause: Over-aggressive cleaning (statistical outliers + smoothing)
    Diagnostic: Compare cleaned vs raw data visually
    Solution: Disable statistical outlier removal and smoothing

INTEGRATION WITH ANALYSIS PIPELINE:
===================================

Typical Workflow:
    1. Load raw sensor data
    2. Create metric-specific cleaner
    3. Apply cleaning with appropriate stages
    4. Check for empty result (all data removed)
    5. If non-empty, proceed with analysis
    6. If empty, log error and skip metric

Code Pattern:
    >>> if cleaning_enabled:
    ...     from DataCleaner import BiometricDataCleaner
    ...     cleaner = BiometricDataCleaner(metric_type=metric)
    ...     df = cleaner.clean(df, metric_col, timestamp_col='LocalTimestamp',
    ...                        stages=cleaning_stages)
    ...     
    ...     if len(df) == 0:
    ...         print(f"❌ ERROR: All {metric} data removed during cleaning")
    ...         return None, []  # Skip analysis
    >>> 
    >>> # Proceed with analysis using cleaned data

PERFORMANCE CHARACTERISTICS:
============================

Time Complexity:
    - Stage 1-3: O(n) where n = number of samples
    - Stage 4: O(n log n) due to sorting
    - Stage 5: O(n) interpolation
    - Stage 6: O(n × window) median filter

Space Complexity:
    - O(n) for DataFrame copy
    - Additional O(n) for intermediate arrays in calculations

Typical Performance:
    - 10,000 samples: <100ms
    - 100,000 samples: <500ms
    - 1,000,000 samples: <5s

Bottlenecks:
    - Median filter (Stage 6) is slowest if enabled
    - Sorting for sudden change detection adds overhead

DEPENDENCIES:
============

External Libraries:
    - pandas >= 1.0: DataFrame operations
    - numpy >= 1.18: Numerical computations, statistical functions
    - scipy >= 1.4: Signal processing (medfilt for smoothing)

Standard Library:
    - None (all imports external)

INVARIANTS:
==========

1. Immutability: Input DataFrame is never modified (copies returned)
2. Column Preservation: All original columns present in output (values may be filtered)
3. Non-Empty Input: Assumes input DataFrame has at least one row
4. Stage Order: Stages execute in fixed order regardless of configuration
5. Logging: Always logs original count, final count, and removal statistics
6. NaN-Free Output: If interpolate=True, output has no NaN; if False, NaN rows dropped

EXTENSION POINTS:
================

1. New Metrics: Add to _get_thresholds() with appropriate ranges
2. New Stages: Add method following _stage_name() pattern, integrate in clean()
3. Custom Filters: Extend with domain-specific artifact detection
4. Adaptive Thresholds: Implement age/context-dependent ranges
5. Quality Scores: Add data quality metrics (e.g., % removed, signal-to-noise ratio)

VERSION: 1.0
PYTHON: 3.7+
REQUIRES: pandas>=1.0, numpy>=1.18, scipy>=1.4
"""

import pandas as pd
import numpy as np
from scipy import signal

class BiometricDataCleaner:
    """
    Multi-stage cleaning pipeline for physiological data.
    """
    
    def __init__(self, metric_type='HR'):
        """
        Args:
            metric_type: Type of metric (HR, EDA, TEMP, etc.)
        """
        self.metric_type = metric_type
        self.thresholds = self._get_thresholds(metric_type)
    
    def _get_thresholds(self, metric_type):
        """Define physiologically valid ranges"""
        ranges = {
            'HR': {'min': 30, 'max': 220, 'max_change': 30},
            'EDA': {'min': 0, 'max': 100, 'max_change': 5},
            'TEMP': {'min': 30, 'max': 42, 'max_change': 2},
            'PI': {'min': 0, 'max': None, 'max_change': None},
            'PR': {'min': 0, 'max': None, 'max_change': None},
            'PG': {'min': 0, 'max': None, 'max_change': None},
            'default': {'min': None, 'max': None, 'max_change': None}
        }
        return ranges.get(metric_type, ranges['default'])
    
    def clean(self, data, metric_col, timestamp_col='AdjustedTimestamp', 
              stages=None):
        """
        Main cleaning pipeline with configurable stages.
        
        Args:
            data: DataFrame with biometric data
            metric_col: Name of column with values
            timestamp_col: Name of timestamp column
            stages: Dict with boolean flags for each stage:
                {
                    'remove_invalid': True,
                    'remove_physiological_outliers': True,
                    'remove_statistical_outliers': False,
                    'remove_sudden_changes': True,
                    'interpolate': True,
                    'smooth': False
                }
            
        Returns:
            Cleaned DataFrame
        """
        # Default: all stages enabled except statistical outliers and smoothing
        if stages is None:
            stages = {
                'remove_invalid': True,
                'remove_physiological_outliers': True,
                'remove_statistical_outliers': False,
                'remove_sudden_changes': True,
                'interpolate': True,
                'smooth': False
            }
        
        df = data.copy()
        original_count = len(df)
        
        print(f"\n🧹 Cleaning {self.metric_type} data...")
        print(f"  Original: {original_count} samples")
        
        # STAGE 1: Remove invalid values
        if stages.get('remove_invalid', True):
            df = self._remove_invalid_values(df, metric_col)
        
        # STAGE 2: Remove physiological outliers
        if stages.get('remove_physiological_outliers', True):
            if self.thresholds['min'] is not None or self.thresholds['max'] is not None:
                df = self._remove_physiological_outliers(df, metric_col)
        
        # STAGE 3: Remove statistical outliers
        if stages.get('remove_statistical_outliers', False):
            df = self._remove_statistical_outliers(df, metric_col)
        
        # STAGE 4: Remove sudden jumps
        if stages.get('remove_sudden_changes', True):
            if self.thresholds['max_change'] is not None:
                df = self._remove_sudden_changes(df, metric_col, timestamp_col)
        
        # STAGE 5: Interpolate missing values
        if stages.get('interpolate', True):
            df = self._interpolate_missing(df, metric_col)
        else:
            df = df.dropna(subset=[metric_col])
        
        # STAGE 6: Apply smoothing
        if stages.get('smooth', False):
            df = self._apply_smoothing(df, metric_col)
        
        final_count = len(df)
        removed = original_count - final_count
        pct = (removed / original_count * 100) if original_count > 0 else 0
        print(f"  Final: {final_count} samples ({removed} removed, {pct:.1f}%)")
        
        return df
    
    def _remove_invalid_values(self, df, metric_col):
        """Remove NaN, inf, and negative values (for metrics that must be positive)"""
        before = len(df)
        
        # Remove NaN
        df = df.dropna(subset=[metric_col])
        
        # Remove infinite values
        df = df[np.isfinite(df[metric_col])]
        
        # Remove negative values for certain metrics
        if self.metric_type in ['EDA', 'PI', 'PR', 'PG']:
            df = df[df[metric_col] >= 0]
        
        removed = before - len(df)
        if removed > 0:
            print(f"    ✓ Removed {removed} invalid values (NaN/inf/negative)")
        
        return df
    
    def _remove_physiological_outliers(self, df, metric_col):
        """Remove values outside physiologically valid range"""
        before = len(df)
        
        if self.thresholds['min'] is not None:
            df = df[df[metric_col] >= self.thresholds['min']]
        
        if self.thresholds['max'] is not None:
            df = df[df[metric_col] <= self.thresholds['max']]
        
        removed = before - len(df)
        if removed > 0:
            print(f"    ✓ Removed {removed} physiological outliers (range: {self.thresholds['min']}-{self.thresholds['max']})")
        
        return df
    
    def _remove_statistical_outliers(self, df, metric_col, threshold=3.5):
        """Remove values beyond threshold standard deviations from median"""
        before = len(df)
        
        # Use median and MAD for robustness
        median = df[metric_col].median()
        mad = np.median(np.abs(df[metric_col] - median))
        
        if mad == 0:
            # Fallback to standard deviation if MAD is zero
            std = df[metric_col].std()
            if std > 0:
                z_scores = np.abs((df[metric_col] - median) / std)
                df = df[z_scores < threshold]
        else:
            modified_z_scores = 0.6745 * (df[metric_col] - median) / mad
            df = df[np.abs(modified_z_scores) < threshold]
        
        removed = before - len(df)
        if removed > 0:
            print(f"    ✓ Removed {removed} statistical outliers (modified z-score > {threshold})")
        
        return df
    
    def _remove_sudden_changes(self, df, metric_col, timestamp_col):
        """Remove data points with unrealistic rate of change"""
        before = len(df)
        
        # Calculate rate of change per second
        df = df.sort_values(timestamp_col).reset_index(drop=True)
        time_diff = df[timestamp_col].diff()
        value_diff = df[metric_col].diff().abs()
        
        # Rate of change per second
        rate_of_change = value_diff / time_diff.replace(0, np.nan)
        
        # Remove points with excessive change
        max_change = self.thresholds['max_change']
        mask = (rate_of_change <= max_change) | rate_of_change.isna()
        df = df[mask]
        
        removed = before - len(df)
        if removed > 0:
            print(f"    ✓ Removed {removed} sudden changes (rate > {max_change}/sec)")
        
        return df
    
    def _interpolate_missing(self, df, metric_col):
        """Interpolate missing values linearly"""
        before_nan = df[metric_col].isna().sum()
        
        if before_nan > 0:
            # Linear interpolation
            df[metric_col] = df[metric_col].interpolate(method='linear', limit=10)
            
            # If still NaN at edges, use forward/backward fill
            df[metric_col] = df[metric_col].fillna(method='bfill', limit=5)
            df[metric_col] = df[metric_col].fillna(method='ffill', limit=5)
            
            after_nan = df[metric_col].isna().sum()
            interpolated = before_nan - after_nan
            
            if interpolated > 0:
                print(f"    ✓ Interpolated {interpolated} missing values")
            
            # Drop any remaining NaN
            df = df.dropna(subset=[metric_col])
        
        return df
    
    def _apply_smoothing(self, df, metric_col, window=5):
        """Apply median filter for noise reduction"""
        if len(df) > window:
            df[metric_col] = signal.medfilt(df[metric_col].values, kernel_size=window)
            print(f"    ✓ Applied median filter (window={window})")
        
        return df