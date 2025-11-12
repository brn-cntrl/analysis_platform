"""
plot_generator.py

Modular plot generation for different visualization types.
Preserves existing styling while supporting multiple plot types.
"""

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import numpy as np
import os


def generate_plot(group_data, metric_col, metric, plot_type, analysis_method, 
                  output_folder, suffix='', subject_label=''):
    """
    Generate plot based on specified type.
    
    Args:
        group_data: Dict mapping group labels to DataFrames
        metric_col: Name of the column containing metric values
        metric: Metric name (e.g., 'HR', 'EDA')
        plot_type: Type of plot ('lineplot', 'boxplot', 'scatter', 'poincare')
        analysis_method: Analysis method used
        output_folder: Where to save plots
        suffix: Optional suffix for filename
        
    Returns:
        Plot info dict or None
    """
    if plot_type == 'lineplot':
        return generate_lineplot(group_data, metric_col, metric, analysis_method, output_folder, suffix, subject_label)
    elif plot_type == 'boxplot':
        return generate_boxplot(group_data, metric_col, metric, analysis_method, output_folder, suffix, subject_label)
    elif plot_type == 'scatter':
        return generate_scatter(group_data, metric_col, metric, analysis_method, output_folder, suffix, subject_label)
    elif plot_type == 'poincare':
        return generate_poincare(group_data, metric_col, metric, analysis_method, output_folder, suffix, subject_label)
    else:
        print(f"  ⚠ Warning: Unknown plot type '{plot_type}', defaulting to lineplot")
        return generate_lineplot(group_data, metric_col, metric, analysis_method, output_folder, suffix, subject_label)


def generate_lineplot(group_data, metric_col, metric, analysis_method, output_folder, suffix='', subject_label=''):    
    """
    Generate line plot (time series) - preserves existing styling.
    """
    colors = ['#4CAF50', '#2196F3', '#FF9800', '#9C27B0', '#F44336', 
              '#00BCD4', '#FFEB3B', '#795548', '#607D8B', '#E91E63']
    
    num_groups = len(group_data)
    fig, axes = plt.subplots(num_groups, 1, figsize=(14, 4 * num_groups), squeeze=False)
    
    for idx, (group_label, data) in enumerate(group_data.items()):
        ax = axes[idx, 0]
        values = data[metric_col].dropna()
        
        if len(values) == 0:
            continue
        
        timestamps = data['AdjustedTimestamp'].values
        start_time = timestamps.min()
        elapsed_seconds = timestamps - start_time
        
        color = colors[idx % len(colors)]
        
        # Plot line and scatter
        ax.plot(elapsed_seconds, values, color=color, linewidth=1.5, alpha=0.8)
        ax.scatter(elapsed_seconds, values, color=color, s=12, alpha=0.6)
        
        # Add mean line
        mean_val = values.mean()
        ax.axhline(y=mean_val, color='red', linestyle='--', alpha=0.5, 
                label=f'Mean: {mean_val:.2f}')
        
        # Statistics box
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
        
        # Add subject label at bottom if provided
        if subject_label:
            fig.text(0.5, 0.01, f"Subject: {subject_label}", 
                    ha='center', fontsize=10, style='italic', transform=fig.transFigure)
        
        filename = f'{metric}_lineplot{suffix}.png'
        plot_path = os.path.join(output_folder, filename)
        plt.savefig(plot_path, dpi=100, bbox_inches='tight')
        plt.close()
    
    print(f"    ✓ Saved: {filename}")
    
    return {
        'name': f'{metric} Line Plot',
        'path': plot_path,
        'filename': filename,
        'url': f'/api/plot/{filename}'
    }


def generate_boxplot(group_data, metric_col, metric, analysis_method, output_folder, suffix='', subject_label=''):    
    """
    Generate box plot for distribution comparison.
    """
    colors = ['#4CAF50', '#2196F3', '#FF9800', '#9C27B0', '#F44336', 
              '#00BCD4', '#FFEB3B', '#795548', '#607D8B', '#E91E63']
    
    fig, ax = plt.subplots(figsize=(max(10, len(group_data) * 2), 6))
    
    group_labels = list(group_data.keys())
    data_arrays = []
    
    for group_label in group_labels:
        values = group_data[group_label][metric_col].dropna().values
        data_arrays.append(values)
    
    # Create box plot
    bp = ax.boxplot(data_arrays, labels=group_labels, patch_artist=True,
                    notch=True, showmeans=True,
                    meanprops=dict(marker='D', markerfacecolor='red', markersize=8),
                    medianprops=dict(color='black', linewidth=2))
    
    # Color the boxes
    for patch, color in zip(bp['boxes'], colors[:len(group_labels)]):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    
    ax.set_xlabel('Event/Condition', fontsize=12)
    ax.set_ylabel(f'{metric} Value', fontsize=12)
    ax.set_title(f'{metric} Distribution Comparison', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y', linestyle='--')
    
    # Rotate x labels if needed
    if len(group_labels) > 3:
        plt.xticks(rotation=45, ha='right')
    
    plt.tight_layout()
    
    # Add subject label at bottom if provided
    if subject_label:
        fig.text(0.5, 0.01, f"Subject: {subject_label}", 
                ha='center', fontsize=10, style='italic', transform=fig.transFigure)
    
    filename = f'{metric}_boxplot{suffix}.png'
    plot_path = os.path.join(output_folder, filename)
    plt.savefig(plot_path, dpi=100, bbox_inches='tight')
    plt.close()
    
    print(f"    ✓ Saved: {filename}")
    
    return {
        'name': f'{metric} Box Plot',
        'path': plot_path,
        'filename': filename,
        'url': f'/api/plot/{filename}'
    }


def generate_scatter(group_data, metric_col, metric, analysis_method, output_folder, suffix='', subject_label=''):
    """
    Generate scatter plot showing data point distribution.
    """
    colors = ['#4CAF50', '#2196F3', '#FF9800', '#9C27B0', '#F44336', 
              '#00BCD4', '#FFEB3B', '#795548', '#607D8B', '#E91E63']
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    for idx, (group_label, data) in enumerate(group_data.items()):
        values = data[metric_col].dropna()
        
        if len(values) == 0:
            continue
        
        timestamps = data['AdjustedTimestamp'].values
        start_time = timestamps.min()
        elapsed_seconds = timestamps - start_time
        
        color = colors[idx % len(colors)]
        
        # Scatter plot with jitter for better visibility
        ax.scatter(elapsed_seconds, values, 
                  color=color, s=40, alpha=0.6, 
                  label=group_label, edgecolors='black', linewidths=0.5)
        
        # Add mean marker
        mean_val = values.mean()
        mean_time = elapsed_seconds.mean()
        ax.scatter(mean_time, mean_val, color='red', s=200, 
                  marker='*', edgecolors='black', linewidths=2,
                  zorder=10)
    
    ax.set_xlabel('Elapsed Time (seconds)', fontsize=12)
    ax.set_ylabel(f'{metric} Value', fontsize=12)
    ax.set_title(f'{metric} Scatter Plot', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10, loc='best')
    ax.grid(True, alpha=0.3, linestyle='--')
    plt.tight_layout()
    
    # Add subject label at bottom if provided
    if subject_label:
        fig.text(0.5, 0.01, f"Subject: {subject_label}", 
                ha='center', fontsize=10, style='italic', transform=fig.transFigure)
    
    filename = f'{metric}_scatter{suffix}.png'
    plot_path = os.path.join(output_folder, filename)
    plt.savefig(plot_path, dpi=100, bbox_inches='tight')
    plt.close()
    
    print(f"    ✓ Saved: {filename}")
    
    return {
        'name': f'{metric} Scatter Plot',
        'path': plot_path,
        'filename': filename,
        'url': f'/api/plot/{filename}'
    }


def generate_poincare(group_data, metric_col, metric, analysis_method, output_folder, suffix='', subject_label=''):
    """
    Generate Poincaré plot (n vs n+1 values) for variability analysis.
    Particularly useful for HRV and successive difference analysis.
    """
    colors = ['#4CAF50', '#2196F3', '#FF9800', '#9C27B0', '#F44336', 
              '#00BCD4', '#FFEB3B', '#795548', '#607D8B', '#E91E63']
    
    fig, ax = plt.subplots(figsize=(10, 10))
    
    for idx, (group_label, data) in enumerate(group_data.items()):
        values = data[metric_col].dropna().values
        
        if len(values) < 2:
            continue
        
        # Create n vs n+1 pairs
        x = values[:-1]
        y = values[1:]
        
        color = colors[idx % len(colors)]
        
        ax.scatter(x, y, color=color, s=30, alpha=0.6, 
                  label=group_label, edgecolors='black', linewidths=0.3)
        
        # Calculate SD1 and SD2 (Poincaré plot parameters)
        sd1 = np.std(np.subtract(x, y)) / np.sqrt(2.0)
        sd2 = np.std(np.add(x, y)) / np.sqrt(2.0)
        
        # Add to label
        ax.plot([], [], ' ', label=f'{group_label}: SD1={sd1:.2f}, SD2={sd2:.2f}')
    
    # Add identity line
    lims = [
        np.min([ax.get_xlim(), ax.get_ylim()]),
        np.max([ax.get_xlim(), ax.get_ylim()])
    ]
    ax.plot(lims, lims, 'k--', alpha=0.3, zorder=0, label='Identity Line')
    
    ax.set_xlabel(f'{metric} at time n', fontsize=12)
    ax.set_ylabel(f'{metric} at time n+1', fontsize=12)
    ax.set_title(f'{metric} Poincaré Plot', fontsize=14, fontweight='bold')
    ax.legend(fontsize=9, loc='best')
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_aspect('equal')
    plt.tight_layout()
    
    # Add subject label at bottom if provided
    if subject_label:
        fig.text(0.5, 0.01, f"Subject: {subject_label}", 
                ha='center', fontsize=10, style='italic', transform=fig.transFigure)
    
    filename = f'{metric}_poincare{suffix}.png'
    plot_path = os.path.join(output_folder, filename)
    plt.savefig(plot_path, dpi=100, bbox_inches='tight')
    plt.close()
    
    print(f"    ✓ Saved: {filename}")
    
    return {
        'name': f'{metric} Poincaré Plot',
        'path': plot_path,
        'filename': filename,
        'url': f'/api/plot/{filename}'
    }


def generate_comparison_plot(metric_results, metric, analysis_method, output_folder, suffix='', subject_label=''):
    """
    Generate comparison bar chart - preserves existing styling.
    """
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
    
    # Add subject label at bottom if provided
    if subject_label:
        fig.text(0.5, 0.01, f"Subject: {subject_label}", 
                ha='center', fontsize=10, style='italic', transform=fig.transFigure)
    
    filename = f'{metric}_comparison{suffix}.png'
    plot_path = os.path.join(output_folder, filename)
    plt.savefig(plot_path, dpi=100, bbox_inches='tight')
    plt.close()
    
    print(f"    ✓ Saved: {filename}")
    
    return {
        'name': f'{metric} Statistical Comparison',
        'path': plot_path,
        'filename': filename,
        'url': f'/api/plot/{filename}'
    }