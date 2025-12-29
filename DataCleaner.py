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
            'RR': {'min': 8, 'max': 25, 'max_change': 5}, 
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
            print(f"    Removed {removed} invalid values (NaN/inf/negative)")
        
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
            print(f"    Removed {removed} physiological outliers (range: {self.thresholds['min']}-{self.thresholds['max']})")
        
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
            print(f"    Removed {removed} statistical outliers (modified z-score > {threshold})")
        
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
            print(f"    Removed {removed} sudden changes (rate > {max_change}/sec)")
        
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
                print(f"    Interpolated {interpolated} missing values")
            
            # Drop any remaining NaN
            df = df.dropna(subset=[metric_col])
        
        return df
    
    def _apply_smoothing(self, df, metric_col, window=5):
        """Apply median filter for noise reduction"""
        if len(df) > window:
            df[metric_col] = signal.medfilt(df[metric_col].values, kernel_size=window)
            print(f"Applied median filter (window={window})")
        
        return df

    def bang_detect(self, x, y, z, type):
        # initialize and combine all
        df = pd.DataFrame()
        df["LocalTimestamp"] = x["LocalTimestamp"]
        df[f"{type}X"] = x[f"{type}X"]
        df[f"{type}Y"] = y[f"{type}Y"]
        df[f"{type}Z"] = z[f"{type}Z"]

        return df

    def flag(self, df, type, upper_threshold, lower_threshold):
        df["flag"] = "hi"

        def in_range(row):
            return (lower_threshold <= row[f"{type}X"] <= upper_threshold) and (lower_threshold <= row[f"{type}Y"] <= upper_threshold) and (lower_threshold <= row[f"{type}Z"] <= upper_threshold)

        flags = []

        i = 0
        n = len(df)

        while i < n:
            if in_range(df.iloc[i]): # if within thresholds
                while i < n and in_range(df.iloc[i]): # while signal continues to be within the thresholds
                    flags.append(1)  # flag as 1
                    i += 1 # go to next row
            else: # if not within thresholds
                while i < n and not in_range(df.iloc[i]): # while 20 rows down is not within thresholds
                    flags.append(0) # flag as 0
                    i += 1 # move to next row

        df["flag"] = flags

        return df


    def interval_marking(self, precleaned_data, flagged_df, interval_size):
        mask = np.zeros(len(flagged_df), dtype=bool)
        zero_ind = np.where(flagged_df["flag"].values == 0)[0]

        if len(zero_ind) > 0:
            for idx in zero_ind:
                start = max(0, idx - interval_size)
                end = min(len(flagged_df), idx + interval_size + 1)
                mask[start:end] = True

            flagged_df["flag"] = np.where(mask, 0, flagged_df["flag"])


            unusable_ind = flagged_df[flagged_df["flag"] == 0].index
            start = unusable_ind[0]
            intervals = []


            for i in range(1, len(unusable_ind)):
                if unusable_ind[i] == unusable_ind[i - 1] + 1:
                    continue
                else:
                    intervals.append((start, unusable_ind[i - 1]))
                    start = unusable_ind[i]
            intervals.append((start, unusable_ind[-1]))

            unusable_data = pd.DataFrame()
            for i in intervals:
                temp = flagged_df[(flagged_df.index >= i[0]) & (flagged_df.index <= i[1])]
                unusable_data = pd.concat([unusable_data, temp])

            timestamps = []
            for i in intervals:
                temp_2 = flagged_df[(flagged_df.index >= i[0]) & (flagged_df.index <= i[1])]
                timestamps.append((temp_2.iloc[0]["LocalTimestamp"], temp_2.iloc[-1]["LocalTimestamp"]))

            unusable_metric_data = pd.DataFrame()
            for i in timestamps:
                temp_3 = precleaned_data[(precleaned_data["LocalTimestamp"] >= i[0]) & (precleaned_data["LocalTimestamp"] <= i[1])]
                unusable_metric_data = pd.concat([unusable_metric_data, temp_3])
            cleaned_data = precleaned_data.loc[~precleaned_data.index.isin(unusable_metric_data.index)]
            
            return cleaned_data
        else:
            return precleaned_data