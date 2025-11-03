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
    extract_window_data,
    get_subject_files,           
    find_metric_file_for_subject  
)

# Import new modules
from analysis_methods import (
    apply_analysis_method,
    calculate_statistics,
    get_method_label
)

from plot_generator import (
    generate_plot,
    generate_comparison_plot
)


def run_analysis(upload_folder, manifest, selected_metrics, comparison_groups, 
                 analysis_method='raw', plot_type='lineplot', analyze_hrv=False, 
                 output_folder='data/outputs', batch_mode=False, selected_subjects=None):
    """
    Main entry point for analysis.
    
    Args:
        upload_folder: Path to subject data folder
        manifest: File manifest dict with paths to data files
        selected_metrics: List of metric names to analyze
        comparison_groups: List of comparison group configurations
        analysis_method: Analysis method ('raw', 'mean', 'moving_average', 'rmssd')
        plot_type: Visualization type ('lineplot', 'boxplot', 'scatter', 'poincare')
        analyze_hrv: Whether to perform HRV analysis
        output_folder: Where to save plots
        batch_mode: Whether analyzing multiple subjects
        selected_subjects: List of subject names (if batch_mode)
        
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
        'hrv': None,
        'config': {
            'analysis_method': analysis_method,
            'plot_type': plot_type,
            'batch_mode': batch_mode,
            'selected_subjects': selected_subjects or []
        }
    }
    
    print("\n" + "="*80)
    print("STARTING ANALYSIS")
    print("="*80)
    print(f"Subject folder: {os.path.basename(upload_folder)}")
    print(f"EmotiBit files: {len(manifest.get('emotibit_files', []))}")
    print(f"Event markers: {'Yes' if manifest.get('event_markers') else 'No'}")
    print(f"Selected metrics: {selected_metrics}")
    print(f"Comparison groups: {len(comparison_groups)}")
    print(f"Analysis method: {analysis_method}")
    print(f"Plot type: {plot_type}")
    print(f"Batch mode: {batch_mode}")
    if batch_mode and selected_subjects:
        print(f"Selected subjects: {selected_subjects}")
    print("="*80 + "\n")
    
    if len(comparison_groups) < 1:
        results['warnings'].append('Need at least 1 comparison group')
        print("⚠ Warning: Need at least 1 comparison group\n")
    
    # Load event markers
    print("1. LOADING EVENT MARKERS")
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
    
    print()
    
    # Analyze HRV if requested
    if analyze_hrv and df_markers is not None:
        print("2. ANALYZING HRV")
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
            print()
        except Exception as e:
            error_msg = f"Error analyzing HRV: {str(e)}"
            print(f"ERROR: {error_msg}")
            results['errors'].append(error_msg)
            import traceback
            traceback.print_exc()
            print()

    # Analyze selected metrics
    if df_markers is not None and selected_metrics:
        print(f"3. ANALYZING SELECTED METRICS (Method: {get_method_label(analysis_method)})")
        print("-" * 80)
        
        for metric in selected_metrics:
            if metric == 'HRV':
                # HRV is handled separately above
                continue
                
            print(f"\nAnalyzing metric: {metric}")
            print("-" * 40)
            
            try:
                # ═══════════════════════════════════════════════════════════
                # MULTI-SUBJECT BATCH MODE
                # ═══════════════════════════════════════════════════════════
                if batch_mode and selected_subjects and len(selected_subjects) > 1:
                    print(f"  🔄 Multi-subject analysis: {len(selected_subjects)} subjects")
                    
                    metric_results, metric_plots = analyze_metric_multi_subject(
                        manifest,
                        selected_subjects,
                        comparison_groups,
                        metric,
                        analysis_method,
                        plot_type,
                        output_folder
                    )
                    
                    if metric_results:
                        results['analysis'][metric] = metric_results
                        results['plots'].extend(metric_plots)
                
                # ═══════════════════════════════════════════════════════════
                # SINGLE SUBJECT MODE (ORIGINAL LOGIC)
                # ═══════════════════════════════════════════════════════════
                else:
                    print(f"  📊 Single subject analysis")
                    
                    metric_file = None
                    for emotibit_file in manifest['emotibit_files']:
                        if f'_{metric}.csv' in emotibit_file['filename']:
                            metric_file = emotibit_file['path']
                            break
                    
                    if not metric_file:
                        print(f"  ⚠ Warning: File for metric {metric} not found - skipping")
                        continue
                    
                    # Use original single-subject logic
                    metric_results, metric_plots = analyze_metric(
                        metric_file, 
                        df_markers, 
                        comparison_groups, 
                        metric,
                        analysis_method,
                        plot_type,
                        output_folder
                    )
                    
                    if metric_results:
                        results['analysis'][metric] = metric_results
                        results['plots'].extend(metric_plots)
                
            except Exception as e:
                error_msg = f"Error analyzing {metric}: {str(e)}"
                print(f"ERROR: {error_msg}")
                results['errors'].append(error_msg)
                import traceback
                traceback.print_exc()
        
        print()
    else:
        print("⚠ Skipping analysis - no event markers or metrics selected\n")
    
    # Finalize results
    print("4. FINALIZING RESULTS")
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
    print("="*80 + "\n")
    
    return results


def analyze_metric(metric_file, df_markers, comparison_groups, metric, 
                   analysis_method, plot_type, output_folder):
    """
    Analyze a single metric with specified method and generate plots.
    
    Args:
        metric_file: Path to metric CSV file
        df_markers: DataFrame with event markers
        comparison_groups: List of comparison group configs
        metric: Metric name (e.g., 'HR', 'EDA')
        analysis_method: Analysis method to apply
        plot_type: Type of plot to generate
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
    group_data_raw = {}
    
    for group in comparison_groups:
        group_label = group['label']
        print(f"\n  Extracting data for '{group_label}'...")
        
        data = extract_window_data(df_metric, df_markers, offset, group)
        
        if len(data) == 0:
            print(f"  ⚠ Warning: No data for group '{group_label}' - skipping")
            continue
        
        group_data_raw[group_label] = data
    
    if len(group_data_raw) < 1:
        print(f"  ⚠ Warning: No groups with data - skipping {metric}")
        return None, []
    
    # Apply analysis method to each group
    print(f"\n  Applying analysis method: {get_method_label(analysis_method)}")
    
    metric_col = df_metric.columns[-1]
    group_data_processed = {}
    
    for group_label, data in group_data_raw.items():
        try:
            processed_data = apply_analysis_method(data, metric_col, analysis_method)
            group_data_processed[group_label] = processed_data
            print(f"    ✓ Processed '{group_label}': {len(processed_data)} data points")
        except Exception as e:
            print(f"    ⚠ Error processing '{group_label}': {e}")
            continue
    
    if len(group_data_processed) == 0:
        print(f"  ⚠ Warning: No successfully processed groups - skipping {metric}")
        return None, []
    
    # Calculate statistics
    print(f"\n  Calculating statistics...")
    metric_results = {}
    
    for group_label, data in group_data_processed.items():
        stats = calculate_statistics(data, metric_col, analysis_method)
        metric_results[group_label] = stats
        
        print(f"    {group_label}: mean={stats['mean']:.2f}, std={stats['std']:.2f}, n={stats['count']}")
    
    # Generate plots
    print(f"\n  Creating visualizations (Plot type: {plot_type})...")
    plots = []
    
    # Main plot based on selected type
    plot1 = generate_plot(
        group_data_processed, 
        metric_col, 
        metric, 
        plot_type,
        analysis_method,
        output_folder
    )
    if plot1:
        plots.append(plot1)
    
    # Comparison plot (if multiple groups)
    if len(group_data_processed) >= 2:
        plot2 = generate_comparison_plot(
            metric_results, 
            metric, 
            analysis_method,
            output_folder
        )
        if plot2:
            plots.append(plot2)
    else:
        print(f"    ⚠ Skipping comparison plot - single group analysis")
    
    return metric_results, plots

def analyze_metric_multi_subject(manifest, selected_subjects, comparison_groups, 
                                  metric, analysis_method, plot_type, output_folder):
    """
    Analyze a metric across multiple subjects (intra-subject analysis).
    Creates subject × event combinations for comparison.
    
    Args:
        manifest: Full file manifest
        selected_subjects: List of subject names
        comparison_groups: List of event-based comparison groups
        metric: Metric name (e.g., 'HR', 'EDA')
        analysis_method: Analysis method to apply
        plot_type: Type of plot to generate
        output_folder: Where to save plots
        
    Returns:
        Tuple of (metric_results dict, plots list)
    """
    print(f"  Loading data for {len(selected_subjects)} subjects...")
    
    # Data structure: {composite_label: DataFrame}
    group_data_raw = {}
    
    # ═══════════════════════════════════════════════════════════════
    # STEP 1: Load data for each subject × event combination
    # ═══════════════════════════════════════════════════════════════
    for subject in selected_subjects:
        print(f"\n  Processing subject: {subject}")
        
        # Get files specific to this subject
        subject_files = get_subject_files(manifest, subject)
        
        if not subject_files['emotibit_files']:
            print(f"    ⚠ No EmotiBit files found for {subject} - skipping")
            continue
        
        if not subject_files['event_markers']:
            print(f"    ⚠ No event markers found for {subject} - skipping")
            continue
        
        # Load metric file for this subject
        metric_file = find_metric_file_for_subject(subject_files, metric)
        if not metric_file:
            print(f"    ⚠ No {metric} file found for {subject} - skipping")
            continue
        
        print(f"    ✓ Loading: {os.path.basename(metric_file)}")
        df_metric = pd.read_csv(metric_file)
        
        # Load event markers for this subject
        event_markers_path = subject_files['event_markers']['path']
        print(f"    ✓ Loading: {os.path.basename(event_markers_path)}")
        df_markers = pd.read_csv(event_markers_path)
        df_markers = prepare_event_markers_timestamps(df_markers)
        
        # Calculate timestamp offset for this subject
        print(f"    Calculating timestamp offset...")
        offset = find_timestamp_offset(df_markers, df_metric)
        
        # Extract data for each comparison group (event window)
        for group in comparison_groups:
            group_label = group['label']
            composite_label = f"{subject} - {group_label}"
            
            print(f"    Extracting: {composite_label}")
            
            data = extract_window_data(df_metric, df_markers, offset, group)
            
            if len(data) == 0:
                print(f"      ⚠ No data found - skipping")
                continue
            
            group_data_raw[composite_label] = data
            print(f"      ✓ {len(data)} data points")
    
    if len(group_data_raw) == 0:
        print(f"  ⚠ Warning: No data extracted for any subject-event combination")
        return None, []
    
    print(f"\n  Successfully loaded {len(group_data_raw)} subject-event combinations")
    
    # ═══════════════════════════════════════════════════════════════
    # STEP 2: Apply analysis method to all combinations
    # ═══════════════════════════════════════════════════════════════
    print(f"\n  Applying analysis method: {get_method_label(analysis_method)}")
    
    metric_col = list(group_data_raw.values())[0].columns[-1]  # Last column is metric
    group_data_processed = {}
    
    for composite_label, data in group_data_raw.items():
        try:
            processed_data = apply_analysis_method(data, metric_col, analysis_method)
            group_data_processed[composite_label] = processed_data
            print(f"    ✓ {composite_label}: {len(processed_data)} points")
        except Exception as e:
            print(f"    ⚠ Error processing '{composite_label}': {e}")
            continue
    
    if len(group_data_processed) == 0:
        print(f"  ⚠ Warning: No successfully processed data")
        return None, []
    
    # ═══════════════════════════════════════════════════════════════
    # STEP 3: Calculate statistics for all combinations
    # ═══════════════════════════════════════════════════════════════
    print(f"\n  Calculating statistics...")
    metric_results = {}
    
    for composite_label, data in group_data_processed.items():
        stats = calculate_statistics(data, metric_col, analysis_method)
        metric_results[composite_label] = stats
        print(f"    {composite_label}: mean={stats['mean']:.2f}, std={stats['std']:.2f}, n={stats['count']}")
    
    # ═══════════════════════════════════════════════════════════════
    # STEP 4: Generate visualizations
    # ═══════════════════════════════════════════════════════════════
    print(f"\n  Creating visualizations (Plot type: {plot_type})...")
    plots = []
    
    # Main plot based on selected type
    plot1 = generate_plot(
        group_data_processed, 
        metric_col, 
        metric, 
        plot_type,
        analysis_method,
        output_folder,
        suffix='_multi_subject'  # ← Distinguish from single-subject plots
    )
    if plot1:
        plots.append(plot1)
    
    # Comparison plot (always useful for multi-subject)
    plot2 = generate_comparison_plot(
        metric_results, 
        metric, 
        analysis_method,
        output_folder,
        suffix='_multi_subject'
    )
    if plot2:
        plots.append(plot2)
    
    return metric_results, plots

def analyze_hrv_from_ppg(manifest, df_markers, comparison_groups, output_folder):
    """
    Analyze HRV from PPG signals.
    [PRESERVED - No changes to this function]
    """
    print("  Loading PPG data files...")
    
    # Find PI file (required)
    pi_file = None
    for emotibit_file in manifest['emotibit_files']:
        if '_PI.csv' in emotibit_file['filename']:
            pi_file = emotibit_file['path']
            break
    
    if not pi_file:
        raise FileNotFoundError("PI (Infrared) PPG file not found")
    
    print(f"    ✓ Found PI file")
    
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
    """
    Generate HRV plots with proper spacing.
    [PRESERVED - No changes to this function]
    """
    try:
        if plot_type == 'signal':
            signals, info = data, param
            nk.ppg_plot(signals, info)
            fig = plt.gcf()
            fig.set_size_inches(20, 22)
            fig.suptitle('PPG Signal with Detected Peaks', fontsize=24, fontweight='bold', y=0.995)
            for ax in fig.get_axes():
                ax.tick_params(axis='both', which='major', labelsize=12)
                ax.xaxis.label.set_fontsize(16)
                ax.yaxis.label.set_fontsize(16)
                legend = ax.get_legend()
                if legend:
                    for text in legend.get_texts():
                        text.set_fontsize(16)
            filename = 'HRV_ppg_signal.png'
            name = 'HRV - PPG Signal with Peaks'
            
        elif plot_type == 'time':
            peaks, sampling_rate = data, param
            nk.hrv_time(peaks, sampling_rate=sampling_rate, show=True)
            fig = plt.gcf()
            fig.set_size_inches(20, 20)
            fig.suptitle('Time Domain HRV', fontsize=24, fontweight='bold', y=0.995)
            for ax in fig.get_axes():
                ax.tick_params(axis='both', which='major', labelsize=18)
                ax.xaxis.label.set_fontsize(16)
                ax.yaxis.label.set_fontsize(16)
                legend = ax.get_legend()
                if legend:
                    for text in legend.get_texts():
                        text.set_fontsize(16)
            filename = 'HRV_time_domain.png'
            name = 'HRV - Time Domain'
            
        elif plot_type == 'frequency':
            peaks, sampling_rate = data, param
            nk.hrv_frequency(peaks, sampling_rate=sampling_rate, show=True)
            fig = plt.gcf()
            fig.set_size_inches(20, 18)
            fig.suptitle('Frequency Domain HRV', fontsize=24, fontweight='bold', y=0.995)
            for ax in fig.get_axes():
                ax.tick_params(axis='both', which='major', labelsize=18)
                ax.xaxis.label.set_fontsize(16)
                ax.yaxis.label.set_fontsize(16)
                legend = ax.get_legend()
                if legend:
                    for text in legend.get_texts():
                        text.set_fontsize(16)
            filename = 'HRV_frequency_domain.png'
            name = 'HRV - Frequency Domain'
            
        elif plot_type == 'nonlinear':
            peaks, sampling_rate = data, param
            nk.hrv_nonlinear(peaks, sampling_rate=sampling_rate, show=True)
            fig = plt.gcf()
            fig.set_size_inches(22, 20)
            fig.suptitle('Non-linear HRV', fontsize=24, fontweight='bold', y=0.995)
            for ax in fig.get_axes():
                ax.tick_params(axis='both', which='major', labelsize=18)
                ax.xaxis.label.set_fontsize(16)
                ax.yaxis.label.set_fontsize(16)
                legend = ax.get_legend()
                if legend:
                    for text in legend.get_texts():
                        text.set_fontsize(16)
            filename = 'HRV_nonlinear.png'
            name = 'HRV - Non-linear'
        
        plot_path = os.path.join(output_folder, filename)
        plt.savefig(plot_path, dpi=100, bbox_inches='tight', pad_inches=0.5)
        plt.close(fig)
        
        print(f"    ✓ Saved: {filename}")
        return {'name': name, 'path': plot_path, 'filename': filename, 'url': f'/api/plot/{filename}'}
    except Exception as e:
        print(f"    ⚠ Could not generate {plot_type} plot: {e}")
        plt.close('all')
        return None