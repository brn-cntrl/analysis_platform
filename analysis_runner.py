"""
Main analysis runner module - replaces Jupyter notebook execution.
Handles the complete analysis pipeline for EmotiBit data.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import os
import json
from datetime import datetime
import neurokit2 as nk

from analysis_utils import (
    prepare_event_markers_timestamps,
    find_timestamp_offset,
    extract_window_data
)


def run_analysis(subject_folder, manifest, selected_metrics, comparison_groups, analyze_hrv=False, output_folder='data/outputs'):
    """
    Main entry point for analysis - replaces notebook execution.
    
    Args:
        subject_folder: Path to subject data folder
        manifest: File manifest dict with paths to data files
        selected_metrics: List of metric names to analyze
        comparison_groups: List of comparison group configurations
        output_folder: Where to save plots
        
    Returns:
        results: Dict containing analysis results, plots, and status
    """
    os.makedirs(output_folder, exist_ok=True)
    
    results = {
        'status': 'processing',
        'timestamp': datetime.now().isoformat(),
        'errors': [],
        'warnings': [],
        'markers': {},
        'analysis': {},
        'plots': [],
        'hrv': None
    }
    
    print("\n1. LOADING CONFIGURATION")
    print("-" * 80)
    print(f"Using subject folder: {os.path.basename(subject_folder)}")
    print(f"  EmotiBit files: {len(manifest.get('emotibit_files', []))}")
    print(f"  Event markers: {'Yes' if manifest.get('event_markers') else 'No'}")
    print(f"  Selected metrics: {selected_metrics}")
    print(f"  Comparison groups: {len(comparison_groups)}")
    
    if len(comparison_groups) < 1:
        results['warnings'].append('Need at least 1 comparison group')
        print("  ⚠ Warning: Need at least 1 comparison group")
    
    # Load event markers
    print("\n2. LOADING EVENT MARKERS")
    print("-" * 80)
    
    try:
        if manifest.get('event_markers'):
            event_markers_path = manifest['event_markers']['path']
            print(f"Loading from: {event_markers_path}")
            
            df_markers = pd.read_csv(event_markers_path)
            print(f"✓ Loaded {df_markers.shape[0]} rows")
            print(f"  Columns: {df_markers.columns.tolist()}")
            
            df_markers = prepare_event_markers_timestamps(df_markers)
            
            results['markers'] = {
                'shape': df_markers.shape,
                'columns': list(df_markers.columns),
                'head': df_markers.head(10).replace({np.nan: None}).to_dict('records')
            }
            
            if 'condition' in df_markers.columns:
                results['markers']['conditions'] = df_markers['condition'].value_counts().to_dict()
        else:
            raise FileNotFoundError("No event markers file in manifest")
            
    except Exception as e:
        error_msg = f"Error loading event markers: {str(e)}"
        print(f"ERROR: {error_msg}")
        results['errors'].append(error_msg)
        df_markers = None
    
    # Analyze HRV if requested
    if analyze_hrv and df_markers is not None:
        print("\n3. ANALYZING HRV")
        print("-" * 80)
        
        try:
            hrv_results, hrv_plots = analyze_hrv_from_ppg(
                manifest, 
                df_markers, 
                comparison_groups, 
                output_folder
            )
            
            if hrv_results:
                results['hrv'] = hrv_results
                results['plots'].extend(hrv_plots)
        except Exception as e:
            error_msg = f"Error analyzing HRV: {str(e)}"
            print(f"  ERROR: {error_msg}")
            results['errors'].append(error_msg)
            import traceback
            traceback.print_exc()

    # Analyze selected metrics
    if df_markers is not None and selected_metrics:
        print("\n3. ANALYZING SELECTED METRICS")
        print("-" * 80)
        
        for metric in selected_metrics:
            print(f"\nAnalyzing metric: {metric}")
            print("-" * 40)
            
            try:
                metric_file = None
                for emotibit_file in manifest['emotibit_files']:
                    if f'_{metric}.csv' in emotibit_file['filename']:
                        metric_file = emotibit_file['path']
                        break
                
                if not metric_file:
                    print(f"  ⚠ Warning: File for metric {metric} not found - skipping")
                    continue
                
                metric_results, metric_plots = analyze_metric(
                    metric_file, 
                    df_markers, 
                    comparison_groups, 
                    metric, 
                    output_folder
                )
                
                if metric_results:
                    results['analysis'][metric] = metric_results
                    results['plots'].extend(metric_plots)
                
            except Exception as e:
                error_msg = f"Error analyzing {metric}: {str(e)}"
                print(f"  ERROR: {error_msg}")
                results['errors'].append(error_msg)
                import traceback
                traceback.print_exc()
    else:
        print("\n⚠ Skipping analysis - no event markers or metrics selected")
    
    # Finalize results
    print("\n4. FINALIZING RESULTS")
    print("-" * 80)
    
    results['status'] = 'completed' if len(results['errors']) == 0 else 'completed_with_errors'
    
    print(f"✓ Analysis complete!")
    print(f"  Status: {results['status']}")
    print(f"  Plots generated: {len(results['plots'])}")
    print(f"  Metrics analyzed: {len(results.get('analysis', {}))}")
    if results['errors']:
        print(f"  Errors: {len(results['errors'])}")
    if results['warnings']:
        print(f"  Warnings: {len(results['warnings'])}")
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    
    return results


def analyze_metric(metric_file, df_markers, comparison_groups, metric, output_folder):
    """
    Analyze a single metric and generate plots.
    
    Args:
        metric_file: Path to metric CSV file
        df_markers: DataFrame with event markers
        comparison_groups: List of comparison group configs
        metric: Metric name (e.g., 'HR', 'EDA')
        output_folder: Where to save plots
        
    Returns:
        Tuple of (metric_results dict, plots list)
    """
    print(f"  Loading: {os.path.basename(metric_file)}")
    df_metric = pd.read_csv(metric_file)
    print(f"  ✓ Loaded {df_metric.shape[0]} rows")
    
    print(f"  Calculating timestamp offset...")
    offset = find_timestamp_offset(df_markers, df_metric)
    
    # Extract data for each comparison group
    group_data = {}
    
    for group in comparison_groups:
        group_label = group['label']
        print(f"\n  Extracting data for '{group_label}'...")
        
        data = extract_window_data(df_metric, df_markers, offset, group)
        
        if len(data) == 0:
            print(f"  ⚠ Warning: No data for group '{group_label}' - skipping")
            continue
        
        group_data[group_label] = data
    
    if len(group_data) < 1:
        print(f"  ⚠ Warning: No groups with data - skipping {metric}")
        return None, []
    
    # Calculate statistics
    metric_col = df_metric.columns[-1]
    metric_results = {}
    
    for group_label, data in group_data.items():
        values = data[metric_col].dropna()
        
        stats = {
            'mean': float(values.mean()),
            'std': float(values.std()),
            'min': float(values.min()),
            'max': float(values.max()),
            'count': int(len(values))
        }
        
        metric_results[group_label] = stats
        print(f"\n  {group_label}: mean={stats['mean']:.2f}, std={stats['std']:.2f}, n={stats['count']}")
    
    # Generate plots
    print(f"\n  Creating visualizations...")
    plots = []
    
    # Plot 1: Individual time series
    plot1 = generate_individual_timeseries_plot(group_data, metric_col, metric, output_folder)
    if plot1:
        plots.append(plot1)
    
    # Plots 2 and 3: Only if multiple groups
    if len(group_data) >= 2:
        plot2 = generate_chronological_timeseries_plot(group_data, metric_col, metric, output_folder)
        if plot2:
            plots.append(plot2)
        
        plot3 = generate_comparison_plot(metric_results, metric, output_folder)
        if plot3:
            plots.append(plot3)
    else:
        print(f"  ⚠ Skipping comparison plots - single group analysis")
    
    return metric_results, plots


def generate_individual_timeseries_plot(group_data, metric_col, metric, output_folder):
    """Generate individual time series plot for each comparison group."""
    colors = ['#4CAF50', '#2196F3', '#FF9800', '#9C27B0', '#F44336', 
              '#00BCD4', '#FFEB3B', '#795548', '#607D8B', '#E91E63']
    
    num_groups = len(group_data)
    fig, axes = plt.subplots(num_groups, 1, figsize=(14, 4 * num_groups), squeeze=False)
    
    for idx, (group_label, data) in enumerate(group_data.items()):
        ax = axes[idx, 0]
        values = data[metric_col].dropna()
        
        timestamps = data['AdjustedTimestamp'].values
        start_time = timestamps.min()
        elapsed_seconds = timestamps - start_time
        
        color = colors[idx % len(colors)]
        
        ax.plot(elapsed_seconds, values, color=color, linewidth=1.5, alpha=0.8)
        ax.scatter(elapsed_seconds, values, color=color, s=12, alpha=0.6)
        
        mean_val = values.mean()
        ax.axhline(y=mean_val, color='red', linestyle='--', alpha=0.5, 
                label=f'Mean: {mean_val:.2f}')
        
        stats_text = f'Mean: {values.mean():.2f}\nStd: {values.std():.2f}\nn: {len(values)}'
        ax.text(0.98, 0.97, stats_text, transform=ax.transAxes,
            verticalalignment='top', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8),
            fontsize=9, family='monospace')
        
        ax.set_xlabel('Elapsed Time (seconds)', fontsize=11)
        ax.set_ylabel(f'{metric} Value', fontsize=11)
        ax.set_title(f'{group_label}', fontsize=12, fontweight='bold', color=color)
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.legend(loc='upper left', fontsize=9)
    
    plt.tight_layout()
    plot_path = os.path.join(output_folder, f'{metric}_individual_timeseries.png')
    plt.savefig(plot_path, dpi=100, bbox_inches='tight')
    plt.close()
    
    print(f"    ✓ Saved: {metric}_individual_timeseries.png")
    
    return {
        'name': f'{metric} Individual Time Series',
        'path': plot_path,
        'filename': f'{metric}_individual_timeseries.png',
        'url': f'/api/plot/{metric}_individual_timeseries.png'
    }


def generate_chronological_timeseries_plot(group_data, metric_col, metric, output_folder):
    """Generate chronological time series plot showing all groups."""
    colors = ['#4CAF50', '#2196F3', '#FF9800', '#9C27B0', '#F44336', 
              '#00BCD4', '#FFEB3B', '#795548', '#607D8B', '#E91E63']
    
    fig, ax = plt.subplots(figsize=(16, 6))
    
    all_time_series_data = []
    
    for group_label, data in group_data.items():
        values = data[metric_col].dropna()
        timestamps = data['AdjustedTimestamp'].values
        
        for ts, val in zip(timestamps, values):
            all_time_series_data.append({
                'timestamp': ts,
                'value': val,
                'group': group_label
            })
    
    ts_df = pd.DataFrame(all_time_series_data)
    ts_df = ts_df.sort_values('timestamp').reset_index(drop=True)
    
    start_time = ts_df['timestamp'].min()
    ts_df['elapsed_minutes'] = (ts_df['timestamp'] - start_time) / 60
    
    group_labels = list(group_data.keys())
    
    for idx, group_label in enumerate(group_labels):
        group_segment = ts_df[ts_df['group'] == group_label]
        if len(group_segment) > 0:
            color = colors[idx % len(colors)]
            ax.plot(group_segment['elapsed_minutes'], group_segment['value'],
                color=color, linewidth=1.5, alpha=0.8, label=group_label)
            ax.scatter(group_segment['elapsed_minutes'], group_segment['value'],
                    color=color, s=8, alpha=0.6)
    
    # Add event boundaries
    event_boundaries = []
    for group_label in group_labels:
        group_segment = ts_df[ts_df['group'] == group_label]
        if len(group_segment) > 0:
            start_min = group_segment['elapsed_minutes'].min()
            end_min = group_segment['elapsed_minutes'].max()
            event_boundaries.append((group_label, start_min, end_min))
    
    y_min, y_max = ax.get_ylim()
    for group_label, start_min, end_min in event_boundaries:
        ax.axvline(x=start_min, color='black', linestyle='--', alpha=0.3, linewidth=1)
        ax.axvline(x=end_min, color='black', linestyle='--', alpha=0.3, linewidth=1)
        
        mid_min = (start_min + end_min) / 2
        ax.text(mid_min, y_max * 0.97, group_label, 
            ha='center', va='top', fontweight='bold', fontsize=10,
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white", alpha=0.9, edgecolor='gray'))
    
    # Set x-axis ticks
    max_minutes = ts_df['elapsed_minutes'].max()
    if max_minutes <= 5:
        tick_interval = 0.5
    elif max_minutes <= 15:
        tick_interval = 1
    elif max_minutes <= 60:
        tick_interval = 2
    else:
        tick_interval = 5
    
    tick_positions = np.arange(0, max_minutes + tick_interval, tick_interval)
    ax.set_xticks(tick_positions)
    ax.set_xticklabels([f'{t:.1f}' if t % 1 != 0 else str(int(t)) for t in tick_positions])
    
    ax.set_xlabel('Elapsed Time (minutes)', fontsize=12)
    ax.set_ylabel(f'{metric} Value', fontsize=12)
    ax.set_title(f'{metric} Time Series: Chronological Progression', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10, loc='best')
    ax.grid(True, alpha=0.3, linestyle='--')
    plt.tight_layout()
    
    plot_path = os.path.join(output_folder, f'{metric}_timeseries.png')
    plt.savefig(plot_path, dpi=100, bbox_inches='tight')
    plt.close()
    
    print(f"    ✓ Saved: {metric}_timeseries.png")
    
    return {
        'name': f'{metric} Time Series',
        'path': plot_path,
        'filename': f'{metric}_timeseries.png',
        'url': f'/api/plot/{metric}_timeseries.png'
    }


def generate_comparison_plot(metric_results, metric, output_folder):
    """Generate comparison bar chart with statistics."""
    colors = ['#4CAF50', '#2196F3', '#FF9800', '#9C27B0', '#F44336', 
              '#00BCD4', '#FFEB3B', '#795548', '#607D8B', '#E91E63']
    
    fig, ax = plt.subplots(figsize=(max(10, len(metric_results) * 2), 6))
    
    group_labels = list(metric_results.keys())
    means = [metric_results[label]['mean'] for label in group_labels]
    stds = [metric_results[label]['std'] for label in group_labels]
    
    x_pos = np.arange(len(group_labels))
    bars = ax.bar(x_pos, means, yerr=stds, capsize=10, 
                color=[colors[i % len(colors)] for i in range(len(group_labels))], 
                alpha=0.7, edgecolor='black', linewidth=1.5)
    
    ax.set_xticks(x_pos)
    ax.set_xticklabels(group_labels, rotation=45, ha='right')
    ax.set_ylabel(f'{metric} Value', fontsize=12)
    ax.set_title(f'{metric}: Statistical Comparison', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y', linestyle='--')
    
    # Add value labels on bars
    for i, (mean, std) in enumerate(zip(means, stds)):
        ax.text(i, mean + std + 0.05 * max(means), f'{mean:.2f}±{std:.2f}',
            ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    plt.tight_layout()
    plot_path = os.path.join(output_folder, f'{metric}_comparison.png')
    plt.savefig(plot_path, dpi=100, bbox_inches='tight')
    plt.close()
    
    print(f"    ✓ Saved: {metric}_comparison.png")
    
    return {
        'name': f'{metric} Statistical Comparison',
        'path': plot_path,
        'filename': f'{metric}_comparison.png',
        'url': f'/api/plot/{metric}_comparison.png'
    }

def analyze_hrv_from_ppg(manifest, df_markers, comparison_groups, output_folder):
    """Analyze HRV from PPG signals."""
    print("  Loading PPG data files...")
    
    # Find PI file (required)
    print("  Loading PPG data files...")
    print(f"  Total emotibit files in manifest: {len(manifest['emotibit_files'])}")
    for f in manifest['emotibit_files']:
        print(f"    - {f['filename']}")

    # Find PI file (required)
    pi_file = None
    for emotibit_file in manifest['emotibit_files']:
        print(f"  Checking file: {emotibit_file['filename']}")
        if '_PI.csv' in emotibit_file['filename']:
            pi_file = emotibit_file['path']
            print(f"  ✓ Found PI file: {emotibit_file['filename']}")
            break

    if not pi_file:
        print("  ERROR: No PI file found in manifest")
        raise FileNotFoundError("PI (Infrared) PPG file not found")
    
    # Load and process
    pi_data = pd.read_csv(pi_file)
    pi_signal = pi_data.iloc[:, -1].values
    timestamps = pi_data['LocalTimestamp'].values
    
    sampling_rate = int(round(1 / np.mean(np.diff(timestamps))))
    pi_signal = pi_signal[~np.isnan(pi_signal)]
    pi_cleaned = nk.ppg_clean(pi_signal, sampling_rate=sampling_rate)
    
    print(f"  Processing PPG signal...")
    signals, info = nk.ppg_process(pi_cleaned, sampling_rate=sampling_rate)
    peaks = info["PPG_Peaks"]
    
    num_peaks = len(peaks)
    duration = len(pi_signal) / sampling_rate / 60
    avg_hr = num_peaks / duration if duration > 0 else 0
    
    print(f"  ✓ Detected {num_peaks} peaks, {duration:.2f} min, {avg_hr:.2f} bpm")
    
    # Calculate HRV
    hrv_indices = nk.hrv(peaks, sampling_rate=sampling_rate, show=False)
    hrv_dict = {}
    for key, value in hrv_indices.to_dict('records')[0].items():
        if isinstance(value, (np.integer, np.floating)):
            hrv_dict[key] = float(value)
        elif pd.isna(value):
            hrv_dict[key] = None
        else:
            hrv_dict[key] = value
    
    # Generate plots
    plots = []
    plots.append(generate_hrv_plot(signals, info, 'signal', output_folder))
    plots.append(generate_hrv_plot(peaks, sampling_rate, 'time', output_folder))
    plots.append(generate_hrv_plot(peaks, sampling_rate, 'frequency', output_folder))
    plots.append(generate_hrv_plot(peaks, sampling_rate, 'nonlinear', output_folder))
    
    return {
        'num_peaks': int(num_peaks),
        'duration_minutes': float(duration),
        'average_hr_bpm': float(avg_hr),
        'sampling_rate': int(sampling_rate),
        'indices': hrv_dict
    }, [p for p in plots if p]


def generate_hrv_plot(data, param, plot_type, output_folder):
    """Generate HRV plots."""
    try:
        if plot_type == 'signal':
            signals, info = data, param
            nk.ppg_plot(signals, info)
            plt.suptitle('PPG Signal Analysis', fontsize=14, fontweight='bold')
            filename = 'HRV_ppg_signal.png'
            name = 'HRV - PPG Signal with Peaks'
        elif plot_type == 'time':
            peaks, sampling_rate = data, param
            nk.hrv_time(peaks, sampling_rate=sampling_rate, show=True)
            plt.suptitle('Time Domain HRV', fontsize=14, fontweight='bold')
            filename = 'HRV_time_domain.png'
            name = 'HRV - Time Domain'
        elif plot_type == 'frequency':
            peaks, sampling_rate = data, param
            nk.hrv_frequency(peaks, sampling_rate=sampling_rate, show=True)
            plt.suptitle('Frequency Domain HRV', fontsize=14, fontweight='bold')
            filename = 'HRV_frequency_domain.png'
            name = 'HRV - Frequency Domain'
        elif plot_type == 'nonlinear':
            peaks, sampling_rate = data, param
            nk.hrv_nonlinear(peaks, sampling_rate=sampling_rate, show=True)
            plt.suptitle('Non-linear HRV', fontsize=14, fontweight='bold')
            filename = 'HRV_nonlinear.png'
            name = 'HRV - Non-linear'
        
        plot_path = os.path.join(output_folder, filename)
        plt.savefig(plot_path, dpi=100, bbox_inches='tight')
        plt.close()
        
        print(f"    ✓ Saved: {filename}")
        return {'name': name, 'path': plot_path, 'filename': filename, 'url': f'/api/plot/{filename}'}
    except Exception as e:
        print(f"    ⚠ Could not generate {plot_type} plot: {e}")
        return None