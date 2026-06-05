import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import seaborn as sns
import os

def analyze_sart_files(sart_configs, output_folder, subject_label='', upload_folder=''):
    """
    Analyze SART data across multiple files for a single subject.
    
    Args:
        sart_configs: Dict with SART file configurations including:
            - files: List of {path, filename, column_mapping}
            - column_mapping: Dict mapping required columns
        output_folder: Where to save plots
        subject_label: Subject identifier
        upload_folder: Base folder path for resolving relative paths
        
    Returns:
        Tuple of (results_dict, plots_list)
    """
    import os
    
    files_data = sart_configs.get('files', [])
    column_mapping = sart_configs.get('column_mapping', {})
    
    for file_info in files_data:
        path = file_info.get('path', '')
        if path and not os.path.isabs(path):
            file_info['path'] = os.path.join(upload_folder, path) if upload_folder else path
    
    required_cols = ['trial', 'is_target', 'response', 'rt', 'correct']
    for col in required_cols:
        if col not in column_mapping or not column_mapping[col]:
            print(f"ERROR: Missing column mapping for '{col}'")
            return None, []
    
    sart_data = []
    sart_names = []
    
    for file_info in files_data:
        if not file_info.get('selected', True):
            continue
            
        try:
            df = pd.read_csv(file_info['path'])
            df_mapped = pd.DataFrame({
                'trial': df[column_mapping['trial']],
                'is_target': df[column_mapping['is_target']],
                'response': df[column_mapping['response']],
                'rt': df[column_mapping['rt']],
                'correct': df[column_mapping['correct']]
            })
            
            is_target_col = df_mapped['is_target']
            if is_target_col.dtype == 'object':
                # Try string conversion first
                df_mapped['is_target'] = is_target_col.map({
                    'True': True, 'true': True, 'TRUE': True, '1': True, 1: True,
                    'False': False, 'false': False, 'FALSE': False, '0': False, 0: False
                })
            elif pd.api.types.is_numeric_dtype(is_target_col):
                df_mapped['is_target'] = is_target_col.astype(bool)

            # Fill any remaining NaN with False (assume Go trials)
            df_mapped['is_target'] = df_mapped['is_target'].fillna(False)
            
            sart_data.append(df_mapped)
            sart_names.append(file_info.get('display_name', file_info['filename']))
            print(f"Loaded {len(df_mapped)} trials from {file_info['filename']}")
            
        except Exception as e:
            print(f"Error loading SART file {file_info['filename']}: {e}")
            continue
    
    if len(sart_data) == 0:
        print("No valid SART files loaded")
        return None, []

    results = plot_sart_changes(
        sart_data, 
        sart_names, 
        output_folder,
        subject_label=subject_label
    )
    
    return results


def plot_sart_changes(sart_data, sart_names, output_folder, subject_label=''):
    """
    Plot changes in Go and No-go accuracy and response time across SART files.
    Adapted from plot_all_sart_changes with configurable file selection.
    """
    print(f"\nAnalyzing {len(sart_data)} SART files...")
    
    def analyze_sart_performance(df, task_name):
        """Analyze Go and No-go performance for a single SART file"""
        
        # Separate Go and No-go trials
        go_trials = df[df['is_target'] == False].copy()
        nogo_trials = df[df['is_target'] == True].copy()
        
        # Go trial analysis
        if len(go_trials) > 0:
            go_accuracy = go_trials['correct'].mean()
            correct_go_trials = go_trials[go_trials['correct'] == True]
            go_rt = correct_go_trials['rt'].mean() if len(correct_go_trials) > 0 else np.nan
        else:
            go_accuracy = np.nan
            go_rt = np.nan
        
        # No-go trial analysis
        if len(nogo_trials) > 0:
            nogo_accuracy = nogo_trials['correct'].mean()
        else:
            nogo_accuracy = np.nan
        
        print(f"{task_name}: Go trials={len(go_trials)}, No-go trials={len(nogo_trials)}, "
              f"Go Acc={go_accuracy:.3f}, Go RT={go_rt:.3f}s, No-go Acc={nogo_accuracy:.3f}")
        
        return {
            'go_accuracy': go_accuracy,
            'go_rt': go_rt,
            'nogo_accuracy': nogo_accuracy,
            'go_trials_count': len(go_trials),
            'nogo_trials_count': len(nogo_trials)
        }
    
    go_rt_values = []
    go_accuracy_values = []
    nogo_accuracy_values = []
    
    for i, data in enumerate(sart_data):
        metrics = analyze_sart_performance(data, sart_names[i])
        go_rt_values.append(metrics['go_rt'])
        go_accuracy_values.append(metrics['go_accuracy'])
        nogo_accuracy_values.append(metrics['nogo_accuracy'])
    
    plot_data = pd.DataFrame({
        'task': sart_names,
        'go_response_time': go_rt_values,
        'go_accuracy': go_accuracy_values,
        'nogo_accuracy': nogo_accuracy_values,
        'task_number': range(len(sart_names))
    })
    
    sns.set_style("whitegrid")
    sns.set_palette("muted")
    sns.set_context("notebook", font_scale=1.1)
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(18, 12))
    palette = sns.color_palette("husl", 3)
    
    # Go Response Time
    sns.lineplot(data=plot_data, x='task_number', y='go_response_time', 
                marker='o', linewidth=3, markersize=10, color=palette[0], ax=ax1)
    ax1.set_title('Go Trial Response Time\n(RT for correct responses to non-targets)', fontsize=14)
    ax1.set_xlabel('SART Task')
    ax1.set_ylabel('Response Time (seconds)')
    ax1.set_xticks(range(len(sart_names)))
    ax1.set_xticklabels(sart_names)
    
    for i, rt in enumerate(go_rt_values):
        if not np.isnan(rt):
            ax1.text(i, rt + 0.005, f'{rt:.3f}s', ha='center', va='bottom', fontweight='bold')
    
    # Go Accuracy
    sns.lineplot(data=plot_data, x='task_number', y='go_accuracy', 
                marker='s', linewidth=3, markersize=10, color=palette[1], ax=ax2)
    ax2.set_title('Go Trial Accuracy\n(Correct responses to non-targets)', fontsize=14)
    ax2.set_xlabel('SART Task')
    ax2.set_ylabel('Accuracy (proportion correct)')
    ax2.set_xticks(range(len(sart_names)))
    ax2.set_xticklabels(sart_names)
    ax2.set_ylim([0, 1])
    
    if not all(np.isnan(go_accuracy_values)):
        min_acc = np.nanmin(go_accuracy_values)
        max_acc = np.nanmax(go_accuracy_values)
        acc_range = max_acc - min_acc
        y_min = max(0, min_acc - acc_range * 0.3)
        y_max = min(1, max_acc + acc_range * 0.3)
        ax2.set_ylim([y_min, y_max])
    
    for i, acc in enumerate(go_accuracy_values):
        if not np.isnan(acc):
            ax2.text(i, acc + (ax2.get_ylim()[1] - ax2.get_ylim()[0]) * 0.03, 
                    f'{acc:.3f}', ha='center', va='bottom', fontweight='bold')
    
    # No-go Accuracy
    sns.lineplot(data=plot_data, x='task_number', y='nogo_accuracy', 
                marker='^', linewidth=3, markersize=10, color=palette[2], ax=ax3)
    ax3.set_title('No-go Trial Accuracy\n(Successful inhibition of targets)', fontsize=14)
    ax3.set_xlabel('SART Task')
    ax3.set_ylabel('Accuracy (proportion correct)')
    ax3.set_xticks(range(len(sart_names)))
    ax3.set_xticklabels(sart_names)
    ax3.set_ylim([0, 1])
    
    for i, acc in enumerate(nogo_accuracy_values):
        if not np.isnan(acc):
            ax3.text(i, acc + 0.02, f'{acc:.3f}', ha='center', va='bottom', fontweight='bold')
    
    # Combined comparison
    x_pos = np.arange(len(sart_names))
    width = 0.25
    
    ax4.bar(x_pos - width, go_accuracy_values, width, label='Go Accuracy', 
            color=palette[1], alpha=0.8)
    ax4.bar(x_pos, nogo_accuracy_values, width, label='No-go Accuracy', 
            color=palette[2], alpha=0.8)
    
    # Normalize Go RT for comparison
    if len(go_rt_values) > 0 and not all(np.isnan(go_rt_values)):
        go_rt_clean = [rt for rt in go_rt_values if not np.isnan(rt)]
        if len(go_rt_clean) > 0:
            min_rt = min(go_rt_clean)
            max_rt = max(go_rt_clean)
            if max_rt > min_rt:
                go_rt_normalized = [(rt - min_rt) / (max_rt - min_rt) if not np.isnan(rt) else 0 
                                   for rt in go_rt_values]
            else:
                go_rt_normalized = [1.0 if not np.isnan(rt) else 0 for rt in go_rt_values]
        else:
            go_rt_normalized = [0] * len(go_rt_values)
    else:
        go_rt_normalized = [0] * len(go_rt_values)
    
    ax4.bar(x_pos + width, go_rt_normalized, width, label='Go RT (normalized)', 
            color=palette[0], alpha=0.8)
    
    ax4.set_title('Performance Comparison Across Tasks', fontsize=14)
    ax4.set_xlabel('SART Task')
    ax4.set_ylabel('Performance Measure')
    ax4.set_xticks(x_pos)
    ax4.set_xticklabels(sart_names)
    ax4.legend()
    ax4.set_ylim([0, 1])
    
    # Add intervention labels if 6 files (original design)
    if len(sart_names) == 6:
        interventions = ['Stressor 1', 'PRS 1', 'Break 1', 'Stressor 2', 'PRS 2']
        for ax in [ax1, ax2, ax3]:
            for i, intervention in enumerate(interventions):
                x_pos_int = i + 0.5
                y_max = ax.get_ylim()[1]
                ax.annotate(intervention, xy=(x_pos_int, y_max * 0.95), ha='center', va='top',
                           fontsize=9, rotation=45, alpha=0.7, 
                           bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray", alpha=0.5))
    
    sns.despine(fig=fig, top=True, right=True)
    plt.tight_layout()
    
    if subject_label:
        fig.text(0.5, 0.01, f"Subject: {subject_label}", 
                ha='center', fontsize=10, style='italic', transform=fig.transFigure)
    
    suffix = f"_{subject_label}" if subject_label else ""
    filename = f'SART_performance_changes{suffix}.png'
    plot_path = os.path.join(output_folder, filename)
    plt.savefig(plot_path, dpi=100, bbox_inches='tight', pad_inches=0.5)
    plt.close()
    
    print(f"Saved: {filename}")
    
    # Calculate changes between consecutive tasks
    changes = []
    for i in range(len(sart_names) - 1):
        go_rt_change = go_rt_values[i+1] - go_rt_values[i] if not np.isnan(go_rt_values[i+1]) and not np.isnan(go_rt_values[i]) else np.nan
        go_acc_change = go_accuracy_values[i+1] - go_accuracy_values[i] if not np.isnan(go_accuracy_values[i+1]) and not np.isnan(go_accuracy_values[i]) else np.nan
        nogo_acc_change = nogo_accuracy_values[i+1] - nogo_accuracy_values[i] if not np.isnan(nogo_accuracy_values[i+1]) and not np.isnan(nogo_accuracy_values[i]) else np.nan
        
        changes.append({
            'from_task': sart_names[i],
            'to_task': sart_names[i+1],
            'go_rt_change': float(go_rt_change) if not np.isnan(go_rt_change) else 0.0,
            'go_accuracy_change': float(go_acc_change) if not np.isnan(go_acc_change) else 0.0,
            'nogo_accuracy_change': float(nogo_acc_change) if not np.isnan(nogo_acc_change) else 0.0
        })
    
    # Summary statistics
    print(f"\n=== SART SUMMARY STATISTICS ===")
    print(f"Go RT - Mean: {np.nanmean(go_rt_values):.3f}s, Std: {np.nanstd(go_rt_values):.3f}s")
    print(f"Go Accuracy - Mean: {np.nanmean(go_accuracy_values):.3f}, Std: {np.nanstd(go_accuracy_values):.3f}")
    print(f"No-go Accuracy - Mean: {np.nanmean(nogo_accuracy_values):.3f}, Std: {np.nanstd(nogo_accuracy_values):.3f}")
    
    results = {
        'summary': {
            'go_rt_mean': float(np.nanmean(go_rt_values)),
            'go_rt_std': float(np.nanstd(go_rt_values)),
            'go_accuracy_mean': float(np.nanmean(go_accuracy_values)),
            'go_accuracy_std': float(np.nanstd(go_accuracy_values)),
            'nogo_accuracy_mean': float(np.nanmean(nogo_accuracy_values)),
            'nogo_accuracy_std': float(np.nanstd(nogo_accuracy_values))
        },
        'by_task': {
            name: {
                'go_rt': float(go_rt_values[i]) if not np.isnan(go_rt_values[i]) else 0.0,
                'go_accuracy': float(go_accuracy_values[i]) if not np.isnan(go_accuracy_values[i]) else 0.0,
                'nogo_accuracy': float(nogo_accuracy_values[i]) if not np.isnan(nogo_accuracy_values[i]) else 0.0
            }
            for i, name in enumerate(sart_names)
        },
        'changes': changes
    }
    
    plot_info = {
        'name': 'SART Performance Changes',
        'path': plot_path,
        'filename': filename,
        'url': f'/api/plot/{filename}'
    }
    
    return results, [plot_info]