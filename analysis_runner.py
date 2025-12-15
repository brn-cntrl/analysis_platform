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
                 output_folder='data/outputs', batch_mode=False, selected_subjects=None,
                 external_configs=None, respiratory_configs=None, cardiac_configs=None,
                 analysis_type='inter', cleaning_enabled=False, cleaning_stages=None):
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
            'selected_subjects': selected_subjects or [],
            'cleaning_enabled': cleaning_enabled,
            'cleaning_stages': cleaning_stages or {}
        }
    }
    
    print("\n" + "="*80)
    print("STARTING ANALYSIS")
    print("="*80)
    print(f"Subject folder: {os.path.basename(upload_folder)}")
    print(f"EmotiBit files: {len(manifest.get('emotibit_files', []))}")
    
    if batch_mode:
        em_count = len(manifest.get('event_markers_by_subject', {}))
        print(f"Event markers: {em_count} subjects")
    else:
        print(f"Event markers: {'Yes' if manifest.get('event_markers') else 'No'}")
    
    print(f"External files: {len(manifest.get('external_files', []))}")
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
        print("Warning: Need at least 1 comparison group\n")
    
    print("1. LOADING EVENT MARKERS")
    print("-" * 80)

    df_markers = None

    try:
        if batch_mode:
            print(f"Batch mode: Event markers will be loaded per-subject")
            em_count = len(manifest.get('event_markers_by_subject', {}))
            print(f"{em_count} subject(s) have event markers")
            
            df_markers = True  # Truthy value to pass checks
            
        elif manifest.get('event_markers'):
            event_markers_path = manifest['event_markers']['path']
            print(f"Loading from: {event_markers_path}")
            
            df_markers = pd.read_csv(event_markers_path)
            print(f"Loaded {df_markers.shape[0]} rows")
            print(f"Columns: {df_markers.columns.tolist()}")
            
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
    
    if analyze_hrv and df_markers is not None:
        if batch_mode and analysis_type == 'intra' and len(selected_subjects) > 1:
            print("2. SKIPPING HRV ANALYSIS")
            print("-" * 80)
            print("HRV analysis is disabled for intra-subject (multi-subject comparison) mode")
            print("Reason: HRV processing takes 30-75 seconds per subject and would cause timeouts")
            print("Recommendation: Use inter-subject mode to analyze each subject's HRV separately")
            results['warnings'].append('HRV skipped: Not supported in intra-subject mode (use inter-subject instead)')
            print()
        else:
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

    # ═══════════════════════════════════════════════════════════════════════════
    # ANALYZE EXTERNAL DATA FILES
    # ═══════════════════════════════════════════════════════════════════════════
    if external_configs and len(external_configs) > 0:
        print(f"3a. ANALYZING EXTERNAL DATA")
        print("-" * 80)
        
        try:
            external_results, external_plots = analyze_external_data(
                manifest,
                external_configs,
                comparison_groups,
                output_folder,
                batch_mode=batch_mode,
                selected_subjects=selected_subjects,
                analysis_method=analysis_method,
                plot_type=plot_type,
                cleaning_enabled=cleaning_enabled,
                cleaning_stages=cleaning_stages
            )
            
            if external_results:
                # Merge external results into main analysis results
                for data_label, stats in external_results.items():
                    # Use a special key format to distinguish external data
                    results['analysis'][f"External: {data_label}"] = stats
                
                results['plots'].extend(external_plots)
                print(f"  ✓ Analyzed {len(external_results)} external data series")
            
            print()
        except Exception as e:
            error_msg = f"Error analyzing external data: {str(e)}"
            print(f"ERROR: {error_msg}")
            results['errors'].append(error_msg)
            import traceback
            traceback.print_exc()
            print()

    # ═══════════════════════════════════════════════════════════════════════════
    # ANALYZE RESPIRATORY DATA FILES
    # ═══════════════════════════════════════════════════════════════════════════
    if respiratory_configs and len(respiratory_configs) > 0:
        print(f"3b. ANALYZING RESPIRATORY DATA")
        print("-" * 80)
        
        try:
            respiratory_results, respiratory_plots = analyze_respiratory_data(
                manifest,
                respiratory_configs,
                comparison_groups,
                output_folder,
                batch_mode=batch_mode,
                selected_subjects=selected_subjects,
                analysis_method=analysis_method,
                plot_type=plot_type,
                cleaning_enabled=cleaning_enabled,
                cleaning_stages=cleaning_stages
            )
            
            if respiratory_results:
                # Merge respiratory results into main analysis results
                for metric_label, stats in respiratory_results.items():
                    results['analysis'][f"Respiratory: {metric_label}"] = stats
                
                results['plots'].extend(respiratory_plots)
                print(f"  ✓ Analyzed {len(respiratory_results)} respiratory metrics")
            
            print()
        except Exception as e:
            error_msg = f"Error analyzing respiratory data: {str(e)}"
            print(f"ERROR: {error_msg}")
            results['errors'].append(error_msg)
            import traceback
            traceback.print_exc()
            print()

    # ═══════════════════════════════════════════════════════════════════════════
    # ANALYZE CARDIAC DATA FILES
    # ═══════════════════════════════════════════════════════════════════════════
    if cardiac_configs and len(cardiac_configs) > 0:
        print(f"3c. ANALYZING CARDIAC DATA")
        print("-" * 80)
        
        try:
            cardiac_results, cardiac_plots = analyze_cardiac_data(
                manifest,
                cardiac_configs,
                comparison_groups,
                output_folder,
                batch_mode=batch_mode,
                selected_subjects=selected_subjects,
                analysis_method=analysis_method,
                plot_type=plot_type,
                cleaning_enabled=cleaning_enabled,
                cleaning_stages=cleaning_stages
            )
            
            if cardiac_results:
                # Merge cardiac results into main analysis results
                for metric_label, stats in cardiac_results.items():
                    results['analysis'][f"Cardiac: {metric_label}"] = stats
                
                results['plots'].extend(cardiac_plots)
                print(f"  ✓ Analyzed {len(cardiac_results)} cardiac metrics")
            
            print()
        except Exception as e:
            error_msg = f"Error analyzing cardiac data: {str(e)}"
            print(f"ERROR: {error_msg}")
            results['errors'].append(error_msg)
            import traceback
            traceback.print_exc()
            print()

    # Analyze selected metrics
    if df_markers is not None and selected_metrics:
        print(f"4. ANALYZING SELECTED METRICS (Method: {get_method_label(analysis_method)})")
        print("-" * 80)
        
        # Synchronize HRV flag with selected metrics
        if 'HRV' in selected_metrics and not analyze_hrv:
            print("HRV detected in metrics list - enabling HRV analysis")
            analyze_hrv = True
        
        for metric in selected_metrics:
            if metric == 'HRV':
                # HRV is handled separately above
                print(f"\nSkipping HRV (handled in dedicated HRV analysis section)")
                continue
                
            print(f"\nAnalyzing metric: {metric}")
            print("-" * 40)
            
            try:
                # ═══════════════════════════════════════════════════════════
                # MULTI-SUBJECT HANDLING
                # ═══════════════════════════════════════════════════════════
                if batch_mode and selected_subjects and len(selected_subjects) >= 1:
                    
                    # INTRA-SUBJECT: Compare subjects together
                    if analysis_type == 'intra':
                        print(f"Intra-subject comparison: {len(selected_subjects)} subjects")
                        
                        metric_results, metric_plots = analyze_metric_multi_subject(
                            manifest,
                            selected_subjects,
                            comparison_groups,
                            metric,
                            analysis_method,
                            plot_type,
                            output_folder,
                            cleaning_enabled=cleaning_enabled,
                            cleaning_stages=cleaning_stages
                        )
                        
                        if metric_results:
                            results['analysis'][metric] = metric_results
                            results['plots'].extend(metric_plots)
                    
                    # INTER-SUBJECT: Analyze each subject separately
                    else:
                        print(f"Inter-subject analysis: {len(selected_subjects)} subjects")
                        print(f"Running single-subject analysis for each subject...\n")
                        
                        for subject in selected_subjects:
                            print(f"  {'='*60}")
                            print(f"  Subject: {subject}")
                            print(f"  {'='*60}")
                            
                            subject_files = get_subject_files(manifest, subject)
                            
                            if not subject_files['event_markers']:
                                print(f"No event markers - skipping")
                                continue
                            
                            em_path = subject_files['event_markers']['path']
                            print(f"Loading event markers: {os.path.basename(em_path)}")
                            df_subject_markers = pd.read_csv(em_path)
                            df_subject_markers = prepare_event_markers_timestamps(df_subject_markers)
                            
                            metric_file = find_metric_file_for_subject(subject_files, metric)
                            if not metric_file:
                                print(f"No {metric} file found - skipping")
                                continue
                            
                            # Run single-subject analysis
                            try:
                                subject_short = subject[:30]  # First 30 chars to keep filename reasonable

                                metric_results, metric_plots = analyze_metric(
                                    metric_file,
                                    df_subject_markers,
                                    comparison_groups,
                                    metric,
                                    analysis_method,
                                    plot_type,
                                    output_folder,
                                    subject_suffix=f"_{subject_short}",
                                    subject_label=subject,
                                    cleaning_enabled=cleaning_enabled,
                                    cleaning_stages=cleaning_stages
                                )
                                                                
                                if metric_results:
                                    if metric not in results['analysis']:
                                        results['analysis'][metric] = {}
                                    
                                    for group_label, stats in metric_results.items():
                                        composite_key = f"{subject} - {group_label}"
                                        results['analysis'][metric][composite_key] = stats
                                    
                                    results['plots'].extend(metric_plots)
                                    
                            except Exception as e:
                                print(f"Error analyzing subject: {e}")
                                continue
                            
                            print()  
                
                # ═══════════════════════════════════════════════════════════
                # SINGLE SUBJECT MODE (ORIGINAL LOGIC)
                # ═══════════════════════════════════════════════════════════
                else:
                    print(f"Single subject analysis")
                    
                    event_markers_file = manifest.get('event_markers')
                    if event_markers_file:
                        em_path_parts = event_markers_file.get('path', '').split('/')
                        subject_from_em = em_path_parts[-2] if len(em_path_parts) >= 2 else None
                        print(f"Subject from event markers: {subject_from_em}")
                        
                        print(f"\n  Available EmotiBit files:")
                        for idx, eb_file in enumerate(manifest['emotibit_files']):
                            print(f"[{idx}] {eb_file.get('filename', 'NO_FILENAME')}")
                            print(f"Path: {eb_file.get('path', 'NO_PATH')}")
                            print(f"Subject field: {eb_file.get('subject', 'NO_SUBJECT_FIELD')}")
                        print()
                        
                        metric_file = None
                        for emotibit_file in manifest['emotibit_files']:
                            if f'_{metric}.csv' in emotibit_file['filename']:
                                file_path = emotibit_file.get('path', '')
                                file_subject = emotibit_file.get('subject', '')
                                
                                print(f"  Checking file: {os.path.basename(emotibit_file['filename'])}")
                                print(f"- File subject field: {file_subject}")
                                print(f"- Subject in path: {subject_from_em in file_path if subject_from_em else False}")
                                print(f"- Subject field match: {file_subject == subject_from_em}")
                                
                                if subject_from_em and (file_subject == subject_from_em or subject_from_em in file_path):
                                    metric_file = emotibit_file['path']
                                    print(f"Matched metric file to subject: {os.path.basename(metric_file)}")
                                    break
                        
                        if not metric_file:
                            print(f"WARNING: Could not match subject, using first {metric} file found")
                            for emotibit_file in manifest['emotibit_files']:
                                if f'_{metric}.csv' in emotibit_file['filename']:
                                    metric_file = emotibit_file['path']
                                    break
                    else:
                        for emotibit_file in manifest['emotibit_files']:
                            if f'_{metric}.csv' in emotibit_file['filename']:
                                metric_file = emotibit_file['path']
                                break
                                    
                    if not metric_file:
                        print(f"Warning: File for metric {metric} not found - skipping")
                        continue
                    
                    try:
                        test_df = pd.read_csv(metric_file)
                        actual_metric_col = test_df.columns[-1]
                        print(f"Verified metric column: '{actual_metric_col}'")
                        
                        if test_df.shape[0] == 0:
                            print(f"Warning: Metric file is empty - skipping")
                            continue
                            
                    except Exception as e:
                        print(f"Error validating metric file: {e}")
                        continue
                    
                    # Use original single-subject logic
                    metric_results, metric_plots = analyze_metric(
                        metric_file, 
                        df_markers, 
                        comparison_groups, 
                        metric,
                        analysis_method,
                        plot_type,
                        output_folder,
                        cleaning_enabled=cleaning_enabled,
                        cleaning_stages=cleaning_stages
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
        print("Skipping analysis - no event markers or metrics selected\n")
    
    print("5. FINALIZING RESULTS")
    print("-" * 80)
    
    results['status'] = 'completed' if len(results['errors']) == 0 else 'completed_with_errors'
    
    print(f"Analysis complete!")
    print(f". Status: {results['status']}")
    print(f"Plots generated: {len(results['plots'])}")
    print(f"Metrics analyzed: {len(results.get('analysis', {}))}")
    if results['errors']:
        print(f"Errors: {len(results['errors'])}")
    if results['warnings']:
        print(f"Warnings: {len(results['warnings'])}")
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80 + "\n")
    
    return results


def analyze_metric(metric_file, df_markers, comparison_groups, metric, 
                   analysis_method, plot_type, output_folder, subject_suffix='', 
                   subject_label='', cleaning_enabled=False, cleaning_stages=None):
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
    print(f"Loading: {os.path.basename(metric_file)}")
    df_metric = pd.read_csv(metric_file)
    print(f"Loaded {df_metric.shape[0]} rows")
    
    # Apply data cleaning if enabled
    if cleaning_enabled:
        from DataCleaner import BiometricDataCleaner
        cleaner = BiometricDataCleaner(metric_type=metric)
        metric_col = df_metric.columns[-1]  
        df_metric = cleaner.clean(
            df_metric, 
            metric_col, 
            timestamp_col='LocalTimestamp',
            stages=cleaning_stages
        )

    if len(df_metric) == 0:
        print(f"ERROR: All data removed during cleaning")
        print(f"Metric: {metric}")
        print(f"This suggests the data may be in wrong units or have fundamental issues")
        return None, []
    
    print(f"Calculating timestamp offset...")
    offset = find_timestamp_offset(df_markers, df_metric)
    
    group_data_raw = {}
    
    for group in comparison_groups:
        group_label = group['label']
        print(f"\nExtracting data for '{group_label}'...")
        
        data = extract_window_data(df_metric, df_markers, offset, group)
        
        if len(data) == 0:
            print(f"Warning: No data for group '{group_label}' - skipping")
            continue
        
        group_data_raw[group_label] = data
    
    if len(group_data_raw) < 1:
        print(f"Warning: No groups with data - skipping {metric}")
        return None, []
    
    print(f"\nApplying analysis method: {get_method_label(analysis_method)}")
    
    metric_col = df_metric.columns[-1]
    group_data_processed = {}
    
    for group_label, data in group_data_raw.items():
        try:
            processed_data = apply_analysis_method(data, metric_col, analysis_method)
            group_data_processed[group_label] = processed_data
            print(f"Processed '{group_label}': {len(processed_data)} data points")
        except Exception as e:
            print(f"Error processing '{group_label}': {e}")
            continue
    
    if len(group_data_processed) == 0:
        print(f"Warning: No successfully processed groups - skipping {metric}")
        return None, []
    
    # Calculate statistics
    print(f"\nCalculating statistics...")
    metric_results = {}
    
    for group_label, data in group_data_processed.items():
        stats = calculate_statistics(data, metric_col, analysis_method)
        metric_results[group_label] = stats
        
        print(f"{group_label}: mean={stats['mean']:.2f}, std={stats['std']:.2f}, n={stats['count']}")
    
    # Generate plots
    # Generate plots
    print(f"\nCreating visualizations (Plot type: {plot_type})...")
    plots = []
    
    # Main plot based on selected type (skip for barchart - it's the comparison plot)
    if plot_type != 'barchart':
        plot1 = generate_plot(
            group_data_processed, 
            metric_col, 
            metric, 
            plot_type,
            analysis_method,
            output_folder,
            suffix=subject_suffix,
            subject_label=subject_label
        )
        if plot1:
            plots.append(plot1)
    
    # Comparison/Bar chart - only generate if there's something to compare
    if len(group_data_processed) >= 2:
        plot2 = generate_comparison_plot(
            metric_results, 
            metric, 
            analysis_method,
            output_folder,
            suffix=subject_suffix,
            subject_label=subject_label
        )
        if plot2:
            plots.append(plot2)
    elif plot_type == 'barchart':
        print(f"Skipping bar chart - only {len(group_data_processed)} event window selected (need 2+ for comparison)")
    else:
        print(f"Skipping comparison plot - single group analysis")
    
    return metric_results, plots

def analyze_metric_multi_subject(manifest, selected_subjects, comparison_groups, 
                                  metric, analysis_method, plot_type, output_folder,
                                  cleaning_enabled=False, cleaning_stages=None):
    """
    Analyze a metric across multiple subjects (intra-subject analysis).
    Creates subject event combinations for comparison.
    
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
    print(f"Loading data for {len(selected_subjects)} subjects...")
    
    # Data structure: {composite_label: DataFrame}
    group_data_raw = {}
    
    # ═══════════════════════════════════════════════════════════════
    # STEP 1: Load data for each subject × event combination
    # ═══════════════════════════════════════════════════════════════
    metric_col_name = None 
    for subject in selected_subjects:
        print(f"\nProcessing subject: {subject}")
        
        # Get files specific to this subject
        subject_files = get_subject_files(manifest, subject)
        
        if not subject_files['emotibit_files']:
            print(f"No EmotiBit files found for {subject} - skipping")
            continue
        
        if not subject_files['event_markers']:
            print(f"No event markers found for {subject} - skipping")
            continue
        
        # Load metric file for this subject
        metric_file = find_metric_file_for_subject(subject_files, metric)
        if not metric_file:
            print(f"No {metric} file found for {subject} - skipping")
            continue
        
        print(f"Loading: {os.path.basename(metric_file)}")
        df_metric = pd.read_csv(metric_file)
        
        if metric_col_name is None:
            metric_col_name = df_metric.columns[-1]
            print(f"Detected metric column: '{metric_col_name}'")

        # Apply data cleaning if enabled
        if cleaning_enabled:
            from DataCleaner import BiometricDataCleaner
            cleaner = BiometricDataCleaner(metric_type=metric)
           
            df_metric = cleaner.clean(
                df_metric,
                metric_col_name, 
                timestamp_col='LocalTimestamp',
                stages=cleaning_stages
            )
        
        if len(df_metric) == 0:
            print(f"WARNING: All data removed during cleaning for {subject}")
            print(f"This suggests the data may be in wrong units or have fundamental issues")
            print(f"Skipping this subject...")
            continue

        event_markers_path = subject_files['event_markers']['path']
        print(f"Loading: {os.path.basename(event_markers_path)}")
        df_markers = pd.read_csv(event_markers_path)
        df_markers = prepare_event_markers_timestamps(df_markers)
        
        print(f"Calculating timestamp offset...")
        offset = find_timestamp_offset(df_markers, df_metric)
        
        for group in comparison_groups:
            group_label = group['label']
            composite_label = f"{subject} - {group_label}"
            
            print(f"Extracting: {composite_label}")
            
            data = extract_window_data(df_metric, df_markers, offset, group)
            
            if len(data) == 0:
                print(f"No data found - skipping")
                continue
            
            group_data_raw[composite_label] = data
            print(f"{len(data)} data points")
    
    if len(group_data_raw) == 0:
        print(f"Warning: No data extracted for any subject-event combination")
        return None, []
    
    print(f"\nSuccessfully loaded {len(group_data_raw)} subject-event combinations")
    
    # ═══════════════════════════════════════════════════════════
    # STEP 2: Apply analysis method to all combinations
    # ═══════════════════════════════════════════════════════════
    print(f"\nApplying analysis method: {get_method_label(analysis_method)}")
    print(f"Using metric column: '{metric_col_name}'")

    group_data_processed = {}
    
    for composite_label, data in group_data_raw.items():
        try:
            processed_data = apply_analysis_method(data, metric_col_name, analysis_method)
            group_data_processed[composite_label] = processed_data
            print(f"{composite_label}: {len(processed_data)} points")
        except Exception as e:
            print(f"Error processing '{composite_label}': {e}")
            continue
    
    if len(group_data_processed) == 0:
        print(f"Warning: No successfully processed data")
        return None, []
    
    # ═══════════════════════════════════════════════════════════════
    # STEP 3: Calculate statistics for all combinations
    # ═══════════════════════════════════════════════════════════════
    print(f"\nCalculating statistics...")
    metric_results = {}
    
    for composite_label, data in group_data_processed.items():
        stats = calculate_statistics(data, metric_col_name, analysis_method)
        metric_results[composite_label] = stats
        print(f"{composite_label}: mean={stats['mean']:.2f}, std={stats['std']:.2f}, n={stats['count']}")
    
    # ═══════════════════════════════════════════════════════════════
    # STEP 4: Generate visualizations
    # ═══════════════════════════════════════════════════════════════
    print(f"\nCreating visualizations (Plot type: {plot_type})...")
    plots = []
    
    if plot_type != 'barchart':
        plot1 = generate_plot(
            group_data_processed, 
            metric_col_name,  # ✅ Use metric_col_name
            metric, 
            plot_type,
            analysis_method,
            output_folder,
            suffix='_multi_subject'
        )
        if plot1:
            plots.append(plot1)
    
    if len(group_data_processed) >= 2:
        plot2 = generate_comparison_plot(
            metric_results, 
            metric, 
            analysis_method,
            output_folder,
            suffix='_multi_subject'
        )
        if plot2:
            plots.append(plot2)
    elif plot_type == 'barchart':
        print(f"Skipping bar chart - only {len(group_data_processed)} event window selected (need 2+ for comparison)")
    
    return metric_results, plots

def analyze_hrv_from_ppg(manifest, df_markers, comparison_groups, output_folder):
    """
    Analyze HRV from PPG signals.
    [PRESERVED - No changes to this function]
    """
    print("Loading PPG data files...")
    
    pi_file = None
    for emotibit_file in manifest['emotibit_files']:
        if '_PI.csv' in emotibit_file['filename']:
            pi_file = emotibit_file['path']
            break
    
    if not pi_file:
        raise FileNotFoundError("PI (Infrared) PPG file not found")
    
    print(f"Found PI file")
    
    pi_data = pd.read_csv(pi_file)
    pi_signal = pi_data.iloc[:, -1].values
    timestamps = pi_data['LocalTimestamp'].values
    
    sampling_rate = int(round(1 / np.mean(np.diff(timestamps))))
    pi_signal = pi_signal[~np.isnan(pi_signal)]
    pi_cleaned = nk.ppg_clean(pi_signal, sampling_rate=sampling_rate)
    
    print(f"Processing PPG signal...")
    signals, info = nk.ppg_process(pi_cleaned, sampling_rate=sampling_rate)
    peaks = info["PPG_Peaks"]
    
    num_peaks = len(peaks)
    duration = len(pi_signal) / sampling_rate / 60
    avg_hr = num_peaks / duration if duration > 0 else 0
    
    print(f"Detected {num_peaks} peaks, {duration:.2f} min, {avg_hr:.2f} bpm")
    
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
        
        print(f"Saved: {filename}")
        return {'name': name, 'path': plot_path, 'filename': filename, 'url': f'/api/plot/{filename}'}
    except Exception as e:
        print(f"Could not generate {plot_type} plot: {e}")
        plt.close('all')
        return None
    
def analyze_external_data(manifest, external_configs, comparison_groups, output_folder,
                          batch_mode=False, selected_subjects=None, analysis_method='raw',
                          plot_type='lineplot', cleaning_enabled=False, cleaning_stages=None):
    """
    Analyze external CSV data files based on user configuration.
    
    Args:
        manifest: File manifest with external_files
        external_configs: Dict of {subject: {filename: config}}
        comparison_groups: List of event/condition groups
        output_folder: Where to save plots
        batch_mode: Whether analyzing multiple subjects
        selected_subjects: List of subjects to analyze
        analysis_method: 'raw', 'mean', 'moving_average', 'rmssd'
        plot_type: Type of visualization
        cleaning_enabled: Whether to apply data cleaning
        cleaning_stages: Which cleaning stages to apply
        
    Returns:
        Tuple of (results_dict, plots_list)
    """
    print(f"  Processing external data files from {len(external_configs)} subject(s)")
    
    all_results = {}
    all_plots = []
    
    # Process each subject's external files
    for subject, files_config in external_configs.items():
        print(f"\n  Subject: {subject}")
        
        # Skip if subject not selected
        if batch_mode and selected_subjects and subject not in selected_subjects:
            print(f"    Skipping (not in selected subjects)")
            continue
        
        # Load event markers for this subject
        df_markers = load_event_markers_for_subject(manifest, subject, batch_mode)
        if df_markers is None:
            print(f"    No event markers found - skipping")
            continue
        
        # Process each selected external file for this subject
        for filename, config in files_config.items():
            if not config.get('selected', True):
                print(f"    Skipping {filename} (not selected)")
                continue
            
            print(f"\n    Processing: {filename}")
            
            # Find the file in manifest
            external_file = find_external_file_in_manifest(manifest, subject, filename)
            if not external_file:
                print(f"      File not found in manifest")
                continue
            
            # Process each configured data column
            for data_col_config in config.get('dataColumns', []):
                if not data_col_config.get('column'):
                    continue
                
                try:
                    results, plots = process_external_file_column(
                        external_file['path'],
                        config,
                        data_col_config,
                        df_markers,
                        comparison_groups,
                        analysis_method,
                        plot_type,
                        output_folder,
                        subject_label=subject,
                        filename_label=filename,
                        cleaning_enabled=cleaning_enabled,
                        cleaning_stages=cleaning_stages
                    )
                    
                    if results:
                        # Create composite label
                        display_name = data_col_config.get('displayName') or data_col_config['column']
                        composite_label = f"{subject} - {filename} - {display_name}"
                        
                        all_results[composite_label] = results
                        all_plots.extend(plots)
                    
                except Exception as e:
                    print(f"      Error processing column {data_col_config['column']}: {e}")
                    continue
    
    print(f"\n  External data analysis complete: {len(all_results)} data series processed")
    return all_results, all_plots


def load_event_markers_for_subject(manifest, subject, batch_mode):
    """Load event markers for a specific subject."""
    if batch_mode:
        em_info = manifest.get('event_markers_by_subject', {}).get(subject)
    else:
        em_info = manifest.get('event_markers')
    
    if not em_info:
        return None
    
    df = pd.read_csv(em_info['path'])
    return prepare_event_markers_timestamps(df)


def find_external_file_in_manifest(manifest, subject, filename):
    """Find external file entry in manifest."""
    for ext_file in manifest.get('external_files', []):
        if ext_file.get('subject') == subject and ext_file.get('filename') == filename:
            return ext_file
    return None


def process_external_file_column(file_path, config, data_col_config, df_markers,
                                  comparison_groups, analysis_method, plot_type,
                                  output_folder, subject_label='', filename_label='',
                                  cleaning_enabled=False, cleaning_stages=None):
    """
    Process a single data column from an external CSV file.
    
    Args:
        file_path: Path to external CSV file
        config: File configuration from frontend
        data_col_config: Configuration for this specific data column
        df_markers: Event markers DataFrame
        comparison_groups: Event/condition groups
        analysis_method: Analysis method to apply
        plot_type: Visualization type
        output_folder: Where to save plots
        subject_label: Subject identifier
        filename_label: Filename for labeling
        cleaning_enabled: Whether to clean data
        cleaning_stages: Cleaning stages to apply
        
    Returns:
        Tuple of (results_dict, plots_list)
    """
    print(f"      Loading column: {data_col_config['column']}")
    
    # Load external CSV
    df = pd.read_csv(file_path)
    
    # Get column names from config
    timestamp_col = config['timestampColumn']
    data_col = data_col_config['column']
    display_name = data_col_config.get('displayName') or data_col
    
    if timestamp_col not in df.columns or data_col not in df.columns:
        print(f"        ERROR: Required columns not found")
        return None, []
    
    # Convert timestamp to unix format based on user's selection
    timestamp_format = config.get('timestampFormat', 'seconds')
    
    if timestamp_format == 'seconds':
        # Seconds since experiment start - need to align with event markers
        df['UnixTimestamp'] = df[timestamp_col]
    elif timestamp_format == 'milliseconds':
        # Convert milliseconds to seconds
        df['UnixTimestamp'] = df[timestamp_col] / 1000.0
    elif timestamp_format == 'unix':
        # Already unix timestamp
        df['UnixTimestamp'] = df[timestamp_col]
    
    # Create a standardized DataFrame structure similar to EmotiBit
    df_processed = pd.DataFrame({
        'LocalTimestamp': df['UnixTimestamp'],
        data_col: df[data_col]
    })
    
    # Apply data cleaning if enabled
    if cleaning_enabled:
        from DataCleaner import BiometricDataCleaner
        # Try to infer metric type from display name, otherwise use generic
        metric_type = 'default'
        cleaner = BiometricDataCleaner(metric_type=metric_type)
        df_processed = cleaner.clean(
            df_processed,
            data_col,
            timestamp_col='LocalTimestamp',
            stages=cleaning_stages
        )
    
    if len(df_processed) == 0:
        print(f"        WARNING: All data removed during cleaning")
        return None, []
    
    # Calculate timestamp offset (external data might start at different time)
    # If format is 'seconds' or 'milliseconds', we need to align with event markers
    if timestamp_format in ['seconds', 'milliseconds']:
        # Assume external data starts at same time as first event marker
        first_event_time = df_markers['unix_timestamp'].min()
        first_data_time = df_processed['LocalTimestamp'].min()
        offset = first_event_time - first_data_time
    else:
        # Unix timestamp - calculate offset normally
        offset = find_timestamp_offset(df_markers, df_processed)
    
    print(f"        Timestamp offset: {offset:.2f}s")
    
    # Extract data for each comparison group
    group_data_raw = {}
    
    for group in comparison_groups:
        group_label = group['label']
        data = extract_window_data(df_processed, df_markers, offset, group)
        
        if len(data) > 0:
            group_data_raw[group_label] = data
            print(f"        {group_label}: {len(data)} points")
    
    if len(group_data_raw) == 0:
        print(f"        No data extracted for any event")
        return None, []
    
    # Apply analysis method
    group_data_processed = {}
    for group_label, data in group_data_raw.items():
        try:
            processed = apply_analysis_method(data, data_col, analysis_method)
            group_data_processed[group_label] = processed
        except Exception as e:
            print(f"        Error processing {group_label}: {e}")
            continue
    
    # Calculate statistics
    results = {}
    for group_label, data in group_data_processed.items():
        stats = calculate_statistics(data, data_col, analysis_method)
        results[group_label] = stats
    
    # Generate plots
    plots = []
    
    # Main plot
    if plot_type != 'barchart':
        suffix = f"_ext_{subject_label}_{filename_label.replace('.csv', '')}"
        plot = generate_plot(
            group_data_processed,
            data_col,
            display_name,
            plot_type,
            analysis_method,
            output_folder,
            suffix=suffix,
            subject_label=f"{subject_label} - {filename_label}"
        )
        if plot:
            plots.append(plot)
    
    # Comparison plot
    if len(group_data_processed) >= 2:
        suffix = f"_ext_{subject_label}_{filename_label.replace('.csv', '')}"
        comp_plot = generate_comparison_plot(
            results,
            display_name,
            analysis_method,
            output_folder,
            suffix=suffix,
            subject_label=f"{subject_label} - {filename_label}"
        )
        if comp_plot:
            plots.append(comp_plot)
    
    return results, plots

def analyze_respiratory_data(manifest, respiratory_configs, comparison_groups, output_folder,
                             batch_mode=False, selected_subjects=None, analysis_method='raw',
                             plot_type='lineplot', cleaning_enabled=False, cleaning_stages=None):
    """
    Analyze respiratory (Vernier) data files.
    
    Args:
        manifest: File manifest with respiration_files
        respiratory_configs: Dict of {subject: {selected, analyzeRR, analyzeForce}}
        comparison_groups: List of event/condition groups
        output_folder: Where to save plots
        batch_mode: Whether analyzing multiple subjects
        selected_subjects: List of subjects to analyze
        analysis_method: 'raw', 'mean', 'moving_average', 'rmssd'
        plot_type: Type of visualization
        cleaning_enabled: Whether to apply data cleaning
        cleaning_stages: Which cleaning stages to apply
        
    Returns:
        Tuple of (results_dict, plots_list)
    """
    print(f"  Processing respiratory data from {len(respiratory_configs)} subject(s)")
    
    all_results = {}
    all_plots = []
    
    # Process each subject's respiratory data
    for subject, config in respiratory_configs.items():
        if not config.get('selected', True):
            print(f"  Skipping {subject} (not selected)")
            continue
        
        # Skip if subject not selected
        if batch_mode and selected_subjects and subject not in selected_subjects:
            print(f"  Skipping {subject} (not in selected subjects)")
            continue
        
        print(f"\n  Subject: {subject}")
        
        # Load event markers for this subject
        df_markers = load_event_markers_for_subject(manifest, subject, batch_mode)
        if df_markers is None:
            print(f"    No event markers found - skipping")
            continue
        
        # Find respiratory file for this subject
        resp_file = find_respiratory_file_for_subject(manifest, subject)
        if not resp_file:
            print(f"    No respiratory file found - skipping")
            continue
        
        print(f"    Loading: {os.path.basename(resp_file)}")
        
        # Load respiratory data
        df_resp = pd.read_csv(resp_file)
        
        # Detect header format (old vs new)
        has_new_format = 'timestamp_unix' in df_resp.columns
        
        if has_new_format:
            print(f"    Detected new header format")
            # New format already has proper timestamps
            if 'timestamp_unix' in df_resp.columns:
                df_resp['LocalTimestamp'] = df_resp['timestamp_unix']
            elif 'timestamp' in df_resp.columns:
                # Need to parse ISO timestamp
                df_resp['LocalTimestamp'] = pd.to_datetime(df_resp['timestamp']).apply(lambda x: x.timestamp())
        else:
            print(f"    Detected old header format")
            # Old format: convert timestamp to unix
            if 'timestamp' in df_resp.columns:
                # Check if already numeric (unix) or string (ISO)
                if pd.api.types.is_numeric_dtype(df_resp['timestamp']):
                    df_resp['LocalTimestamp'] = df_resp['timestamp']
                else:
                    df_resp['LocalTimestamp'] = pd.to_datetime(df_resp['timestamp']).apply(lambda x: x.timestamp())
        
        # Calculate timestamp offset
        offset = find_timestamp_offset(df_markers, df_resp)
        
        # Analyze RR if selected
        if config.get('analyzeRR', True) and 'RR' in df_resp.columns:
            print(f"\n    Analyzing RR (Respiratory Rate)")
            try:
                results, plots = analyze_respiratory_metric(
                    df_resp,
                    'RR',
                    df_markers,
                    offset,
                    comparison_groups,
                    analysis_method,
                    plot_type,
                    output_folder,
                    subject_label=subject,
                    cleaning_enabled=cleaning_enabled,
                    cleaning_stages=cleaning_stages
                )
                
                if results:
                    for group_label, stats in results.items():
                        composite_label = f"{subject} - RR - {group_label}"
                        all_results[composite_label] = stats
                
                if plots:
                    all_plots.extend(plots)
                else:
                    print(f"      No plots generated for RR (likely due to sparse data)")
                    
            except Exception as e:
                print(f"      Error analyzing RR: {e}")
                import traceback
                traceback.print_exc()
        
        # Analyze Force if selected
        if config.get('analyzeForce', True) and 'force' in df_resp.columns:
            print(f"\n    Analyzing Force (Respiratory Effort)")
            try:
                results, plots = analyze_respiratory_metric(
                    df_resp,
                    'force',
                    df_markers,
                    offset,
                    comparison_groups,
                    analysis_method,
                    plot_type,
                    output_folder,
                    subject_label=subject,
                    cleaning_enabled=cleaning_enabled,
                    cleaning_stages=cleaning_stages
                )
                
                if results:
                    for group_label, stats in results.items():
                        composite_label = f"{subject} - Force - {group_label}"
                        all_results[composite_label] = stats
                if plots:
                    all_plots.extend(plots)
                    
            except Exception as e:
                print(f"      Error analyzing Force: {e}")
    
    print(f"\n  Respiratory data analysis complete: {len(all_results)} metrics processed")
    return all_results, all_plots


def find_respiratory_file_for_subject(manifest, subject):
    """Find respiratory file for a specific subject."""
    for resp_file in manifest.get('respiration_files', []):
        if (resp_file.get('subject') == subject or 
            subject in resp_file.get('path', '')):
            return resp_file['path']
    return None


def analyze_respiratory_metric(df_resp, metric_col, df_markers, offset, comparison_groups,
                               analysis_method, plot_type, output_folder, subject_label='',
                               cleaning_enabled=False, cleaning_stages=None):
    """
    Analyze a single respiratory metric (RR or force).
    
    Args:
        df_resp: DataFrame with respiratory data
        metric_col: Column name ('RR' or 'force')
        df_markers: Event markers DataFrame
        offset: Timestamp offset
        comparison_groups: Event/condition groups
        analysis_method: Analysis method to apply
        plot_type: Visualization type
        output_folder: Where to save plots
        subject_label: Subject identifier
        cleaning_enabled: Whether to clean data
        cleaning_stages: Cleaning stages to apply
        
    Returns:
        Tuple of (results_dict, plots_list)
    """
    df_processed = pd.DataFrame({
        'LocalTimestamp': df_resp['LocalTimestamp'],
        metric_col: df_resp[metric_col]
    })

    # Check data sparsity for RR (which is typically measured per breath cycle)
    non_null_count = df_processed[metric_col].notna().sum()
    total_count = len(df_processed)
    sparsity_ratio = non_null_count / total_count if total_count > 0 else 0

    print(f"        Data sparsity: {non_null_count}/{total_count} ({sparsity_ratio*100:.1f}% non-null)")

    if sparsity_ratio < 0.1:
        print(f"        WARNING: Very sparse data for {metric_col} (<10% non-null values)")
        print(f"        This may affect analysis quality")

   # Apply data cleaning if enabled
    if cleaning_enabled:
        from DataCleaner import BiometricDataCleaner
        
        # Check if metric is sparse (common for RR which is per-breath, not per-sample)
        non_null_count = df_processed[metric_col].notna().sum()
        total_count = len(df_processed)
        sparsity_ratio = non_null_count / total_count if total_count > 0 else 0
        
        print(f"        Data density: {non_null_count}/{total_count} ({sparsity_ratio*100:.1f}% non-null)")
        
        if sparsity_ratio < 0.5:  # If more than 50% sparse
            print(f"        Detected sparse metric - cleaning only non-null values without removing rows")
            
            # For sparse metrics, only clean the non-null values
            # Create a mask for non-null values
            valid_mask = df_processed[metric_col].notna()
            
            if valid_mask.sum() > 0:
                # Extract only non-null rows for cleaning
                df_to_clean = df_processed[valid_mask].copy()
                
                metric_type = 'RR' if metric_col == 'RR' else 'default'
                cleaner = BiometricDataCleaner(metric_type=metric_type)
                
                # Clean only the valid data
                df_cleaned = cleaner.clean(
                    df_to_clean,
                    metric_col,
                    timestamp_col='LocalTimestamp',
                    stages=cleaning_stages
                )
                
                # Merge cleaned values back into original dataframe structure
                # This preserves the timeline with NaN values intact
                df_processed.loc[valid_mask, metric_col] = df_cleaned[metric_col].values
                
                print(f"        Cleaned {len(df_cleaned)}/{non_null_count} non-null values")
            else:
                print(f"        No non-null values to clean")
        else:
            # Continuous data - clean normally
            print(f"        Continuous metric - applying standard cleaning")
            metric_type = 'RR' if metric_col == 'RR' else 'default'
            cleaner = BiometricDataCleaner(metric_type=metric_type)
            df_processed = cleaner.clean(
                df_processed,
                metric_col,
                timestamp_col='LocalTimestamp',
                stages=cleaning_stages
            )
    
    # Check if we have any valid data after cleaning
    valid_data_count = df_processed[metric_col].notna().sum()
    if valid_data_count == 0:
        print(f"        WARNING: No valid data available after cleaning")
        return None, []
    
    # Extract data for each comparison group
    group_data_raw = {}
    
    for group in comparison_groups:
        group_label = group['label']
        data = extract_window_data(df_processed, df_markers, offset, group)
        
        if len(data) > 0:
            group_data_raw[group_label] = data
            print(f"        {group_label}: {len(data)} points")
    
    if len(group_data_raw) == 0:
        print(f"        No data extracted for any event")
        return None, []
    
    # Apply analysis method
    group_data_processed = {}
    for group_label, data in group_data_raw.items():
        try:
            processed = apply_analysis_method(data, metric_col, analysis_method)
            group_data_processed[group_label] = processed
        except Exception as e:
            print(f"        Error processing {group_label}: {e}")
            continue
    
    # Calculate statistics
    results = {}
    for group_label, data in group_data_processed.items():
        stats = calculate_statistics(data, metric_col, analysis_method)
        results[group_label] = stats
    
    # Generate plots
    plots = []
    
    # Use clean metric name for filename, display name for plot title
    metric_name = 'RR' if metric_col == 'RR' else 'Force'
    display_name = 'Respiratory Rate (RR)' if metric_col == 'RR' else 'Respiratory Effort (Force)'

    # Main plot
    if plot_type != 'barchart':
        suffix = f"_resp_{subject_label}_{metric_col}"
        plot = generate_plot(
            group_data_processed,
            metric_col,
            metric_name,  # ✅ Use clean name for filename: 'RR' or 'Force'
            plot_type,
            analysis_method,
            output_folder,
            suffix=suffix,
            subject_label=f"{subject_label} - Respiratory"
        )
        if plot:
            plots.append(plot)
    
    # Comparison plot
    if len(group_data_processed) >= 2:
        suffix = f"_resp_{subject_label}_{metric_col}"
        comp_plot = generate_comparison_plot(
            results,
            metric_name,
            analysis_method,
            output_folder,
            suffix=suffix,
            subject_label=f"{subject_label} - Respiratory"
        )
        if comp_plot:
            plots.append(comp_plot)
    
    return results, plots

def analyze_cardiac_data(manifest, cardiac_configs, comparison_groups, output_folder,
                        batch_mode=False, selected_subjects=None, analysis_method='raw',
                        plot_type='lineplot', cleaning_enabled=False, cleaning_stages=None):
    """
    Analyze cardiac (Polar H10) data files.
    
    Args:
        manifest: File manifest with cardiac_files
        cardiac_configs: Dict of {subject: {selected, analyzeHR, analyzeHRV}}
        comparison_groups: List of event/condition groups
        output_folder: Where to save plots
        batch_mode: Whether analyzing multiple subjects
        selected_subjects: List of subjects to analyze
        analysis_method: 'raw', 'mean', 'moving_average', 'rmssd'
        plot_type: Type of visualization
        cleaning_enabled: Whether to apply data cleaning
        cleaning_stages: Which cleaning stages to apply
        
    Returns:
        Tuple of (results_dict, plots_list)
    """
    print(f"  Processing cardiac data from {len(cardiac_configs)} subject(s)")
    
    all_results = {}
    all_plots = []
    
    # Process each subject's cardiac data
    for subject, config in cardiac_configs.items():
        if not config.get('selected', True):
            print(f"  Skipping {subject} (not selected)")
            continue
        
        # Skip if subject not selected
        if batch_mode and selected_subjects and subject not in selected_subjects:
            print(f"  Skipping {subject} (not in selected subjects)")
            continue
        
        print(f"\n  Subject: {subject}")
        
        # Load event markers for this subject
        df_markers = load_event_markers_for_subject(manifest, subject, batch_mode)
        if df_markers is None:
            print(f"    No event markers found - skipping")
            continue
        
        # Find cardiac file for this subject
        cardiac_file = find_cardiac_file_for_subject(manifest, subject)
        if not cardiac_file:
            print(f"    No cardiac file found - skipping")
            continue
        
        print(f"    Loading: {os.path.basename(cardiac_file)}")
        
        # Load cardiac data
        df_cardiac = pd.read_csv(cardiac_file)
        
        # Cardiac files already have timestamp_unix column
        if 'timestamp_unix' in df_cardiac.columns:
            df_cardiac['LocalTimestamp'] = df_cardiac['timestamp_unix']
        elif 'timestamp' in df_cardiac.columns:
            # Fallback: parse ISO timestamp
            df_cardiac['LocalTimestamp'] = pd.to_datetime(df_cardiac['timestamp']).apply(lambda x: x.timestamp())
        else:
            print(f"    ERROR: No timestamp column found - skipping")
            continue
        
        # Calculate timestamp offset
        offset = find_timestamp_offset(df_markers, df_cardiac)
        
        # Analyze HR if selected
        if config.get('analyzeHR', True) and 'HR' in df_cardiac.columns:
            print(f"\n    Analyzing HR (Heart Rate)")
            try:
                results, plots = analyze_cardiac_metric(
                    df_cardiac,
                    'HR',
                    df_markers,
                    offset,
                    comparison_groups,
                    analysis_method,
                    plot_type,
                    output_folder,
                    subject_label=subject,
                    cleaning_enabled=cleaning_enabled,
                    cleaning_stages=cleaning_stages
                )
                
                if results:
                    for group_label, stats in results.items():
                        composite_label = f"{subject} - HR - {group_label}"
                        all_results[composite_label] = stats

                # Always add plots if they exist, regardless of results
                if plots:
                    all_plots.extend(plots)
                    
            except Exception as e:
                print(f"      Error analyzing HR: {e}")
        
        # Analyze HRV if selected
        if config.get('analyzeHRV', True) and 'HRV' in df_cardiac.columns:
            print(f"\n    Analyzing HRV (Heart Rate Variability)")
            try:
                results, plots = analyze_cardiac_metric(
                    df_cardiac,
                    'HRV',
                    df_markers,
                    offset,
                    comparison_groups,
                    analysis_method,
                    plot_type,
                    output_folder,
                    subject_label=subject,
                    cleaning_enabled=cleaning_enabled,
                    cleaning_stages=cleaning_stages
                )
                
                if results:
                    for group_label, stats in results.items():
                        composite_label = f"{subject} - HRV - {group_label}"
                        all_results[composite_label] = stats
                    all_plots.extend(plots)
                    
            except Exception as e:
                print(f"      Error analyzing HRV: {e}")
    
    print(f"\n  Cardiac data analysis complete: {len(all_results)} metrics processed")
    return all_results, all_plots


def find_cardiac_file_for_subject(manifest, subject):
    """Find cardiac file for a specific subject."""
    for cardiac_file in manifest.get('cardiac_files', []):
        if (cardiac_file.get('subject') == subject or 
            subject in cardiac_file.get('path', '')):
            return cardiac_file['path']
    return None


def analyze_cardiac_metric(df_cardiac, metric_col, df_markers, offset, comparison_groups,
                           analysis_method, plot_type, output_folder, subject_label='',
                           cleaning_enabled=False, cleaning_stages=None):
    """
    Analyze a single cardiac metric (HR or HRV).
    
    Note: Polar H10 HRV is pre-calculated, unlike EmotiBit which computes from PPG.
    This function treats HRV as a standard metric (not specialized neurokit2 analysis).
    
    Args:
        df_cardiac: DataFrame with cardiac data
        metric_col: Column name ('HR' or 'HRV')
        df_markers: Event markers DataFrame
        offset: Timestamp offset
        comparison_groups: Event/condition groups
        analysis_method: Analysis method to apply
        plot_type: Visualization type
        output_folder: Where to save plots
        subject_label: Subject identifier
        cleaning_enabled: Whether to clean data
        cleaning_stages: Cleaning stages to apply
        
    Returns:
        Tuple of (results_dict, plots_list)
    """
    # Create standardized structure
    df_processed = pd.DataFrame({
        'LocalTimestamp': df_cardiac['LocalTimestamp'],
        metric_col: df_cardiac[metric_col]
    })
    
    # Apply data cleaning if enabled
    if cleaning_enabled:
        from DataCleaner import BiometricDataCleaner
        # Both HR and HRV use HR-type cleaning (physiological ranges)
        metric_type = 'HR'
        cleaner = BiometricDataCleaner(metric_type=metric_type)
        df_processed = cleaner.clean(
            df_processed,
            metric_col,
            timestamp_col='LocalTimestamp',
            stages=cleaning_stages
        )
    
    if len(df_processed) == 0:
        print(f"        WARNING: All data removed during cleaning")
        return None, []
    
    # Extract data for each comparison group
    group_data_raw = {}
    
    for group in comparison_groups:
        group_label = group['label']
        data = extract_window_data(df_processed, df_markers, offset, group)
        
        if len(data) > 0:
            group_data_raw[group_label] = data
            print(f"        {group_label}: {len(data)} points")
    
    if len(group_data_raw) == 0:
        print(f"        No data extracted for any event")
        return None, []
    
    # Apply analysis method
    group_data_processed = {}
    for group_label, data in group_data_raw.items():
        try:
            processed = apply_analysis_method(data, metric_col, analysis_method)
            group_data_processed[group_label] = processed
        except Exception as e:
            print(f"        Error processing {group_label}: {e}")
            continue
    
    # Calculate statistics
    results = {}
    for group_label, data in group_data_processed.items():
        stats = calculate_statistics(data, metric_col, analysis_method)
        results[group_label] = stats
    
    # Generate plots
    plots = []
    
    # Use metric name directly (already clean: 'HR', 'HRV')
    metric_name = metric_col
    
    # Main plot
    if plot_type != 'barchart':
        suffix = f"_cardiac_{subject_label}_{metric_col}"
        plot = generate_plot(
            group_data_processed,
            metric_col,
            metric_name,
            plot_type,
            analysis_method,
            output_folder,
            suffix=suffix,
            subject_label=f"{subject_label} - Cardiac"
        )
        if plot:
            plots.append(plot)
    
    # Comparison plot
    if len(group_data_processed) >= 2:
        suffix = f"_cardiac_{subject_label}_{metric_col}"
        comp_plot = generate_comparison_plot(
            results,
            metric_name,
            analysis_method,
            output_folder,
            suffix=suffix,
            subject_label=f"{subject_label} - Cardiac"
        )
        if comp_plot:
            plots.append(comp_plot)
    
    return results, plots