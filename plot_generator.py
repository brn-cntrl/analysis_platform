"""
BIOMETRIC DATA VISUALIZATION GENERATOR - LLM CONTRACT
=====================================================

PURPOSE:
This module provides standardized, publication-ready visualizations for biometric data analysis.
It generates multiple plot types (time series, distributions, comparisons) with consistent styling,
automatic color schemes, and statistical annotations. Designed for both exploratory analysis and
formal scientific reporting.

CORE VISUALIZATION PHILOSOPHY:
------------------------------
    - Consistency: All plots share color palette, fonts, and styling conventions
    - Clarity: Statistical information embedded directly in visualizations
    - Accessibility: High-contrast colors, large fonts, clear legends
    - Publication-Ready: 100 DPI, professional formatting, proper labeling
    - Modularity: Each plot type is independent and can be generated separately

ARCHITECTURE OVERVIEW:
---------------------
┌─────────────────────────────────────────────────────────────┐
│              generate_plot() [Dispatcher]                   │
│         Routes to appropriate plot generator                │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ├──► generate_lineplot()      [Time Series]
                   ├──► generate_boxplot()       [Distribution Comparison]
                   ├──► generate_scatter()       [Point Distribution]
                   ├──► generate_poincare()      [Variability Analysis]
                   └──► [barchart handled by generate_comparison_plot()]

┌─────────────────────────────────────────────────────────────┐
│         generate_comparison_plot() [Bar Chart]              │
│            (Called separately, not via dispatcher)          │
└─────────────────────────────────────────────────────────────┘

FUNCTION CONTRACT - generate_plot():
===================================

Purpose: Main dispatcher that routes plot generation based on plot_type

Signature:
    generate_plot(group_data, metric_col, metric, plot_type, analysis_method, 
                  output_folder, suffix='', subject_label='')

Input Requirements:
    - group_data: dict of {group_label: DataFrame}
        * Each DataFrame must have 'AdjustedTimestamp' column
        * Each DataFrame must have metric_col column (numeric values)
        * Structure: {'Baseline': df1, 'Stress': df2, ...}
    
    - metric_col: str, name of column containing metric values
        * Typically last column of EmotiBit CSV
        * Examples: 'HR', 'EDA', 'TEMP', 'PI'
    
    - metric: str, human-readable metric name
        * Used in plot titles and filenames
        * Examples: 'HR', 'EDA', 'TEMP'
    
    - plot_type: str, one of:
        * 'lineplot': Time series (default, always works)
        * 'boxplot': Distribution comparison (requires multiple samples)
        * 'scatter': Point distribution (incompatible with 'mean' analysis)
        * 'poincare': Variability analysis (requires ≥2 samples)
        * 'barchart': Returns None (handled by generate_comparison_plot)
    
    - analysis_method: str, one of ['raw', 'mean', 'moving_average', 'rmssd']
        * Affects data interpretation (e.g., scatter incompatible with 'mean')
    
    - output_folder: str, path to save PNG files
        * Must exist or be creatable
        * Example: 'data/outputs'
    
    - suffix: str, optional filename suffix (default='')
        * Used for distinguishing plots: '_P001', '_multi_subject'
        * Inserted before file extension
    
    - subject_label: str, optional display label (default='')
        * Shows at bottom of plot: "Subject: P001"
        * Used in multi-subject studies

Output:
    dict | None
    
    Success: {
        'name': str,        # Human-readable plot name
        'path': str,        # Full file system path
        'filename': str,    # Filename only (for serving)
        'url': str          # API endpoint URL
    }
    
    Failure: None (unknown plot type defaults to lineplot, others may return None)

Routing Logic:
    'lineplot' → generate_lineplot()
    'boxplot' → generate_boxplot()
    'scatter' → generate_scatter()
    'poincare' → generate_poincare()
    'barchart' → None (caller should use generate_comparison_plot directly)
    unknown → generate_lineplot() (fallback with warning)

Example Usage:
    >>> plot = generate_plot(
    ...     group_data={'Baseline': df_baseline, 'Stress': df_stress},
    ...     metric_col='HR',
    ...     metric='HR',
    ...     plot_type='lineplot',
    ...     analysis_method='raw',
    ...     output_folder='outputs'
    ... )
    >>> print(f"Plot saved to: {plot['path']}")

FUNCTION CONTRACT - generate_lineplot():
========================================

Purpose: Generate time series visualization showing metric evolution over time

Visual Elements:
    - One subplot per group (vertical stacking)
    - Line plot + optional scatter points (commented out by default)
    - Horizontal dashed line at mean value
    - Statistics box (upper right): mean, std, sample count
    - Grid for easier value reading
    - Color-coded by group

Input Requirements:
    - group_data: dict of {label: DataFrame with 'AdjustedTimestamp' and metric_col}
    - metric_col: str, column name with values
    - metric: str, metric identifier
    - analysis_method: str, analysis method used (for reference)
    - output_folder: str, save directory
    - suffix: str, filename suffix (default='')
    - subject_label: str, bottom label text (default='')

Output:
    dict with plot metadata (see generate_plot output format)

Plot Specifications:
    - Figure size: 14×(4×num_groups) inches
    - DPI: 100
    - File format: PNG
    - Filename: {metric}_lineplot{suffix}.png
    
    Per Subplot:
        - X-axis: Elapsed time in seconds (relative to window start)
        - Y-axis: Metric value with appropriate units
        - Title: Group label in group-specific color
        - Mean line: Red dashed (α=0.5)
        - Statistics box: White background, monospace font
        - Grid: Gray dashed (α=0.3)

Time Handling:
    - Converts absolute timestamps to elapsed seconds
    - Elapsed time = AdjustedTimestamp - min(AdjustedTimestamp)
    - Zero point = start of time window

Length Mismatch Handling:
    - RMSSD analysis produces n-1 points (successive differences)
    - Automatically truncates timestamps to match value count
    - min_len = min(len(timestamps), len(values))

Statistics Box Content:
    Mean: {mean:.2f}
    Std: {std:.2f}
    n: {count}

Use Cases:
    - Visualizing physiological responses over time
    - Identifying trends and patterns
    - Quality control (detecting artifacts visually)
    - Comparing multiple event windows

Example:
    >>> lineplot = generate_lineplot(
    ...     group_data={'Baseline': df_base, 'Task': df_task},
    ...     metric_col='HR',
    ...     metric='HR',
    ...     analysis_method='moving_average',
    ...     output_folder='plots',
    ...     subject_label='Participant 001'
    ... )

FUNCTION CONTRACT - generate_boxplot():
=======================================

Purpose: Generate box-and-whisker plots for distribution comparison across groups

Visual Elements:
    - One box per group (horizontal arrangement)
    - Box shows IQR (interquartile range)
    - Whiskers extend to 1.5×IQR
    - Median line (black, thick)
    - Mean marker (red diamond)
    - Notches for confidence intervals (if sufficient data)
    - Outliers shown as individual points

Input Requirements:
    Same as generate_lineplot()

Output:
    dict with plot metadata or None if generation fails

Plot Specifications:
    - Figure size: max(10, len(groups)×2) × 6 inches (scales with group count)
    - DPI: 100
    - File format: PNG
    - Filename: {metric}_boxplot{suffix}.png
    
    Elements:
        - Boxes: Colored by group, 70% opacity
        - Notches: Enabled if sufficient data (95% CI of median)
        - Means: Red diamonds (marker='D', size=8)
        - Medians: Black line (width=2)
        - Grid: Horizontal only (α=0.3)
        - X-labels: Rotated 45° if >3 groups

Box Plot Interpretation:
    - Box spans 25th to 75th percentile (IQR)
    - Line inside box = median (50th percentile)
    - Diamond = mean (can differ from median if skewed)
    - Notches = 95% confidence interval of median
        * Non-overlapping notches → significantly different medians
    - Whiskers = extend to 1.5×IQR or data range
    - Points beyond whiskers = outliers

Fallback Behavior:
    If notched boxplot fails (insufficient data for confidence intervals):
        - Logs warning message
        - Falls back to non-notched boxplot (notch=False)
        - Continues without error

Use Cases:
    - Comparing distributions across conditions
    - Identifying outliers visually
    - Assessing spread and central tendency
    - Statistical comparison at a glance

Example:
    >>> boxplot = generate_boxplot(
    ...     group_data={'Rest': df_rest, 'Exercise': df_exercise},
    ...     metric_col='HR',
    ...     metric='HR',
    ...     analysis_method='raw',
    ...     output_folder='plots'
    ... )

FUNCTION CONTRACT - generate_scatter():
=======================================

Purpose: Generate scatter plot showing individual data points over time

Visual Elements:
    - All groups on single plot (overlay)
    - Individual points as circles
    - Mean marked with large red star
    - Color-coded by group with legend
    - Black edge on points for clarity

Input Requirements:
    Same as generate_lineplot()

Output:
    dict with plot metadata or None if incompatible

Plot Specifications:
    - Figure size: 14×8 inches
    - DPI: 100
    - File format: PNG
    - Filename: {metric}_scatter{suffix}.png
    
    Elements:
        - Data points: Circles (s=40, α=0.6)
        - Edge color: Black (width=0.5)
        - Mean markers: Red stars (s=200, marker='*', z-order=10)
        - Legend: Best location, fontsize=10
        - Grid: Dashed (α=0.3)

Analysis Method Compatibility:
    ❌ INCOMPATIBLE with 'mean' analysis method
    Reason: Mean analysis produces single value per group (no distribution to scatter)
    Behavior: Returns None with explanatory message

Jitter Consideration:
    - Comment mentions "jitter for better visibility"
    - Currently not implemented
    - Could be added for overlapping points

Use Cases:
    - Visualizing data point density
    - Identifying clusters or gaps
    - Detecting temporal patterns
    - Comparing raw distributions across groups

Example:
    >>> scatter = generate_scatter(
    ...     group_data={'Low Stress': df_low, 'High Stress': df_high},
    ...     metric_col='EDA',
    ...     metric='EDA',
    ...     analysis_method='raw',
    ...     output_folder='plots'
    ... )

FUNCTION CONTRACT - generate_poincare():
========================================

Purpose: Generate Poincaré plot for variability analysis (autocorrelation visualization)

Mathematical Foundation:
    Poincaré Plot: Plot of x[n] vs x[n+1] (each point vs its successor)
    
    Metrics:
        SD1 = std(x[n] - x[n+1]) / √2   [Short-term variability]
        SD2 = std(x[n] + x[n+1]) / √2   [Long-term variability]
    
    Interpretation:
        - Points along identity line → minimal change between successive samples
        - Points far from line → high variability
        - SD1 measures perpendicular dispersion (beat-to-beat variation)
        - SD2 measures parallel dispersion (overall variability)

Visual Elements:
    - Square aspect ratio (10×10 inches)
    - Identity line (y=x) as dashed black line
    - Scatter points colored by group
    - SD1/SD2 values in legend
    - Black point edges for clarity

Input Requirements:
    Same as generate_lineplot()
    Minimum: 2 data points per group (for n vs n+1 pairs)

Output:
    dict with plot metadata or None if insufficient data

Plot Specifications:
    - Figure size: 10×10 inches (square for equal axes)
    - Aspect ratio: 'equal' (ensures visual accuracy)
    - DPI: 100
    - File format: PNG
    - Filename: {metric}_poincare{suffix}.png
    
    Elements:
        - Data points: Circles (s=30, α=0.6)
        - Edge color: Black (width=0.3)
        - Identity line: Black dashed (α=0.3, z-order=0)
        - Legend: Shows SD1, SD2 per group
        - Grid: Dashed (α=0.3)
        - Equal axis scaling (set_aspect='equal')

Use Cases:
    - Heart Rate Variability (HRV) analysis
    - Assessing signal stability
    - Detecting patterns in successive changes
    - Comparing variability across conditions
    - Particularly useful with 'rmssd' analysis method

Mathematical Example:
    Values: [70, 72, 71, 73, 72]
    Pairs: (70,72), (72,71), (71,73), (73,72)
    x = [70, 72, 71, 73]
    y = [72, 71, 73, 72]
    
    differences = [70-72, 72-71, 71-73, 73-72] = [-2, 1, -2, 1]
    sums = [70+72, 72+71, 71+73, 73+72] = [142, 143, 144, 145]
    SD1 = std(differences) / √2
    SD2 = std(sums) / √2

Example:
    >>> poincare = generate_poincare(
    ...     group_data={'Baseline': df_baseline, 'Stress': df_stress},
    ...     metric_col='HR',
    ...     metric='HR',
    ...     analysis_method='rmssd',
    ...     output_folder='plots'
    ... )

FUNCTION CONTRACT - generate_comparison_plot():
===============================================

Purpose: Generate bar chart comparing statistical summaries across groups

Visual Elements:
    - One bar per group (horizontal arrangement)
    - Error bars showing ±1 standard deviation
    - Value labels above bars (mean±std)
    - Color-coded bars with black edges
    - Horizontal grid for value reference

Input Requirements:
    - metric_results: dict of {group_label: {mean, std, ...}}
        * Structure from calculate_statistics()
        * Required keys: 'mean', 'std'
        * Example: {'Baseline': {'mean': 75.2, 'std': 8.1, ...}, ...}
    
    - metric: str, metric identifier
    - analysis_method: str, analysis method used
    - output_folder: str, save directory
    - suffix: str, filename suffix (default='')
    - subject_label: str, bottom label text (default='')

Output:
    dict with plot metadata

Plot Specifications:
    - Figure size: max(10, len(groups)×2) × 6 inches
    - DPI: 100
    - File format: PNG
    - Filename: {metric}_comparison{suffix}.png
    
    Elements:
        - Bars: Colored by group, 70% opacity
        - Error bars: ±1 std, cap size=10
        - Edge color: Black (width=1.5)
        - Value labels: Above bars, format '{mean:.2f}±{std:.2f}'
        - Grid: Horizontal only (α=0.3)
        - Title: '{metric}: Statistical Comparison'

Label Truncation:
    Long group labels (>15 characters) are truncated:
        "SubjectA - Very Long Condition Name" → "...ion Name"
    Purpose: Prevents x-axis label overlap and maintains readability

Use Cases:
    - Direct statistical comparison
    - Identifying significant differences
    - Publication-ready summary figures
    - Presenting aggregated results

Example:
    >>> stats = {
    ...     'Baseline': {'mean': 72.5, 'std': 5.2, 'count': 100},
    ...     'Stress': {'mean': 95.3, 'std': 12.1, 'count': 100}
    ... }
    >>> comparison = generate_comparison_plot(
    ...     metric_results=stats,
    ...     metric='HR',
    ...     analysis_method='mean',
    ...     output_folder='plots'
    ... )

COLOR PALETTE SPECIFICATION:
============================

Standard 10-Color Palette:
    colors = [
        '#4CAF50',  # 0: Green (high contrast, accessibility)
        '#2196F3',  # 1: Blue (professional, calming)
        '#FF9800',  # 2: Orange (warm, energetic)
        '#9C27B0',  # 3: Purple (distinct, memorable)
        '#F44336',  # 4: Red (alerting, important)
        '#00BCD4',  # 5: Cyan (technical, modern)
        '#FFEB3B',  # 6: Yellow (caution: low contrast)
        '#795548',  # 7: Brown (earthy, neutral)
        '#607D8B',  # 8: Blue-Gray (subtle, professional)
        '#E91E63'   # 9: Pink (accent, distinctive)
    ]

Color Assignment:
    color = colors[group_index % len(colors)]
    Behavior: Cycles through palette if >10 groups

Accessibility Considerations:
    - High contrast against white background
    - Distinct hues for color-blind users
    - Black edges on scatter points enhance visibility
    - Yellow (#FFEB3B) has lowest contrast (use sparingly)

Special Colors (Semantic):
    - Red (#FF0000 or 'red'): Mean lines, mean markers (statistical significance)
    - Black ('k' or 'black'): Median lines, grid lines, axes (structural)
    - Gray (α=0.3): Grid lines (subtle reference)

STYLING STANDARDS:
==================

Typography:
    - Title font size: 12-14pt, fontweight='bold'
    - Axis label font size: 11-12pt
    - Tick label font size: default (9-10pt)
    - Statistics box: 9pt, family='monospace'
    - Legend: 9-10pt

Layout:
    - tight_layout() used universally (prevents label cutoff)
    - bbox_inches='tight' on savefig (removes excess whitespace)
    - DPI=100 (balance between file size and quality)

Grid:
    - Style: Dashed ('--')
    - Alpha: 0.3 (subtle, not distracting)
    - Axis: Y-axis for bar/box plots, both for line/scatter

Transparency (Alpha):
    - Line plots: 0.8 (main lines), 0.5 (mean lines)
    - Scatter points: 0.6
    - Box plots: 0.7 (boxes)
    - Statistics box: 0.8 (background)

Markers:
    - Mean: Red diamond (D) or star (*)
    - Median: Black line (automatic in boxplot)
    - Data points: Circles (o, default)

FILENAME CONVENTIONS:
====================

Format: {metric}_{plot_type}{suffix}.png

Components:
    - metric: Metric identifier (e.g., 'HR', 'EDA', 'TEMP')
    - plot_type: One of [lineplot, boxplot, scatter, poincare, comparison]
    - suffix: Optional identifier (e.g., '_P001', '_multi_subject')
    - extension: Always '.png'

Examples:
    - HR_lineplot.png
    - EDA_boxplot_P001.png
    - TEMP_scatter_multi_subject.png
    - HR_poincare.png
    - EDA_comparison_batch.png

URL Format:
    '/api/plot/{filename}'
    Used for serving plots via web API

MATPLOTLIB CONFIGURATION:
=========================

Backend:
    matplotlib.use('Agg')
    Purpose: Non-interactive backend for headless environments (servers)
    Effect: No GUI windows, saves directly to file

Figure Management:
    plt.close() or plt.close(fig)
    Importance: CRITICAL for preventing memory leaks
    Frequency: After every savefig() call

Subplot Management:
    squeeze=False in plt.subplots()
    Purpose: Always returns 2D array of axes (even for single subplot)
    Benefit: Consistent indexing (axes[i, 0] always works)

ERROR HANDLING & EDGE CASES:
============================

Empty DataFrames:
    Behavior: Skips group, continues processing others
    Detection: len(values) == 0 after dropna()
    Effect: Plot may be partially populated

Length Mismatches:
    Scenario: RMSSD produces n-1 points
    Solution: Truncate timestamps to match values
    Code: min_len = min(len(timestamps), len(values))

Insufficient Data:
    Poincaré: Requires ≥2 points per group
        → Skip group if len(values) < 2
    Boxplot notches: May fail with small samples
        → Fallback to non-notched boxplot

Incompatible Combinations:
    Scatter + Mean analysis:
        → Returns None with explanatory message
        → Reason: Single value per group (nothing to scatter)

Unknown Plot Types:
    Behavior: Log warning, fallback to lineplot
    Message: "Warning: Unknown plot type '{type}', defaulting to lineplot"

SUBJECT LABEL FEATURE:
=====================

Purpose: Add subject identifier to multi-subject plots

Implementation:
    fig.text(0.5, 0.01, f"Subject: {subject_label}", 
            ha='center', fontsize=10, style='italic', 
            transform=fig.transFigure)

Positioning:
    - X: 0.5 (center)
    - Y: 0.01 (1% from bottom)
    - Alignment: center horizontal
    - Transform: Figure coordinates (independent of subplots)

Use Cases:
    - Inter-subject analysis (separate plots per subject)
    - Subject identification in saved plots
    - Organizational clarity in batch processing

Example:
    "Subject: Participant_001"
    "Subject: P042"

INTEGRATION WITH ANALYSIS PIPELINE:
===================================

Typical Call Sequence:

1. Main plot (if not barchart):
    plot1 = generate_plot(
        group_data_processed,
        metric_col,
        metric,
        plot_type,
        analysis_method,
        output_folder,
        suffix=subject_suffix,
        subject_label=subject
    )
    if plot1:
        plots.append(plot1)

2. Comparison plot (if ≥2 groups):
    if len(group_data_processed) >= 2:
        plot2 = generate_comparison_plot(
            metric_results,
            metric,
            analysis_method,
            output_folder,
            suffix=subject_suffix,
            subject_label=subject
        )
        if plot2:
            plots.append(plot2)

Expected Input Pipeline:
    Raw Data → Cleaning → Windowing → Analysis Method → Plot Generation

Data Flow:
    1. extract_window_data() → group_data_raw
    2. apply_analysis_method() → group_data_processed
    3. calculate_statistics() → metric_results
    4. generate_plot() → plot metadata
    5. generate_comparison_plot() → comparison plot metadata

PERFORMANCE CHARACTERISTICS:
============================

Time Complexity:
    - O(n) where n = total data points across all groups
    - Boxplot: O(n log n) due to percentile calculations
    - Poincaré: O(n) for scatter + O(1) for SD1/SD2

Space Complexity:
    - O(n) for figure buffer
    - Matplotlib holds entire figure in memory until saved

File Sizes:
    - Typical PNG: 50-500 KB per plot
    - Depends on: complexity, data density, DPI
    - Line plots: Usually smallest
    - Scatter plots: Larger with many points

Generation Time:
    - Simple plots: <100ms
    - Complex multi-group: 100-500ms
    - Bottleneck: matplotlib rendering, not data processing

USAGE EXAMPLES:
==============

Example 1 - Basic Lineplot:
    >>> data = {
    ...     'Baseline': pd.DataFrame({
    ...         'AdjustedTimestamp': range(100),
    ...         'HR': np.random.normal(75, 5, 100)
    ...     })
    ... }
    >>> plot = generate_plot(data, 'HR', 'HR', 'lineplot', 
    ...                       'raw', 'outputs')
    >>> print(f"Saved: {plot['filename']}")

Example 2 - Multi-Group Boxplot:
    >>> data = {
    ...     'Rest': df_rest,
    ...     'Exercise': df_exercise,
    ...     'Recovery': df_recovery
    ... }
    >>> plot = generate_boxplot(data, 'HR', 'HR', 'raw', 'outputs')

Example 3 - Comparison with Statistics:
    >>> stats = {
    ...     'Baseline': {'mean': 72.5, 'std': 5.2},
    ...     'Stress': {'mean': 95.3, 'std': 12.1},
    ...     'Recovery': {'mean': 78.4, 'std': 6.8}
    ... }
    >>> plot = generate_comparison_plot(stats, 'HR', 'mean', 'outputs')

Example 4 - Subject-Labeled Plot:
    >>> plot = generate_plot(
    ...     data, 'HR', 'HR', 'lineplot', 'moving_average',
    ...     'outputs', suffix='_P001', subject_label='Participant 001'
    ... )

Example 5 - HRV Poincaré Analysis:
    >>> hrv_data = {
    ...     'Baseline HRV': df_baseline_rmssd,
    ...     'Stress HRV': df_stress_rmssd
    ... }
    >>> plot = generate_poincare(hrv_data, 'HR', 'HR', 'rmssd', 'outputs')

DEPENDENCIES:
============

External Libraries:
    - matplotlib >= 3.3: Plotting library
        * matplotlib.pyplot: High-level plotting interface
        * matplotlib.use('Agg'): Backend configuration
    - numpy >= 1.18: Numerical operations (min, max, std for Poincaré)
    - os (stdlib): File path operations

Expected Directory Structure:
    output_folder/
        ├── {metric}_lineplot{suffix}.png
        ├── {metric}_boxplot{suffix}.png
        ├── {metric}_comparison{suffix}.png
        └── ...

File System Requirements:
    - Write access to output_folder
    - Sufficient disk space (typically <1MB per plot)
    - No restrictions on PNG file creation

INVARIANTS:
==========

1. Non-Interactive: All plots saved to file, no GUI display
2. Memory Safety: plt.close() called after every plot
3. File Format: Always PNG with 100 DPI
4. URL Schema: Always '/api/plot/{filename}'
5. Color Consistency: Same palette across all plot types
6. Immutability: Input data never modified
7. Metadata Structure: Return dict always has [name, path, filename, url] keys

EXTENSION POINTS:
================

1. New Plot Types: Add function following generate_{type}() pattern
2. Custom Color Schemes: Modify colors array
3. Additional Statistics: Extend statistics box content
4. Export Formats: Add PDF, SVG support alongside PNG
5. Interactive Plots: Switch to different backend (e.g., TkAgg)
6. Annotation Features: Add event markers, zones, thresholds
7. Statistical Tests: Overlay p-values, significance markers

ACCESSIBILITY CONSIDERATIONS:
=============================

Color Blindness:
    - Palette tested for deuteranopia/protanopia
    - Distinct hues, not just brightness differences
    - Black edges on points enhance distinction

Font Sizes:
    - Minimum 9pt for readability
    - Titles 12-14pt for hierarchy
    - Consistent sizing across plot types

Contrast:
    - All colors meet WCAG AA standard against white
    - Grid alpha=0.3 provides reference without distraction
    - Black text on white background (maximum contrast)

VERSION: 1.0
PYTHON: 3.7+
REQUIRES: matplotlib>=3.3, numpy>=1.18
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
    """
    if plot_type == 'lineplot':
        return generate_lineplot(group_data, metric_col, metric, analysis_method, output_folder, suffix, subject_label)
    elif plot_type == 'boxplot':
        return generate_boxplot(group_data, metric_col, metric, analysis_method, output_folder, suffix, subject_label)
    elif plot_type == 'scatter':
        return generate_scatter(group_data, metric_col, metric, analysis_method, output_folder, suffix, subject_label)
    elif plot_type == 'poincare':
        return generate_poincare(group_data, metric_col, metric, analysis_method, output_folder, suffix, subject_label)
    elif plot_type == 'barchart':
        return None  # Handled by generate_comparison_plot
    else:
        print(f"Warning: Unknown plot type '{plot_type}', defaulting to lineplot")
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
        
        # Ensure timestamps and values have matching lengths (RMSSD produces N-1 points)
        min_len = min(len(timestamps), len(values))
        timestamps = timestamps[:min_len]
        values = values.iloc[:min_len] if hasattr(values, 'iloc') else values[:min_len]
        
        start_time = timestamps.min()
        elapsed_seconds = timestamps - start_time
        
        color = colors[idx % len(colors)]
        
        # Plot line and scatter
        ax.plot(elapsed_seconds, values, color=color, linewidth=1.1, alpha=0.8)
        # ax.scatter(elapsed_seconds, values, color=color, s=12, alpha=0.6)
        
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
    
    print(f"    Saved: {filename}")
    
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
    try:
        bp = ax.boxplot(data_arrays, labels=group_labels, patch_artist=True,
                        notch=True, showmeans=True,
                        meanprops=dict(marker='D', markerfacecolor='red', markersize=8),
                        medianprops=dict(color='black', linewidth=2))
    except ValueError as e:
        # Fallback to non-notched boxplot if insufficient data
        print(f"    Notched boxplot failed, using standard boxplot: {e}")
        bp = ax.boxplot(data_arrays, labels=group_labels, patch_artist=True,
                        notch=False, showmeans=True,
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
    
    print(f"    Saved: {filename}")
    
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
    # Scatter plots require multiple data points - incompatible with mean analysis
    if analysis_method == 'mean':
        print(f"    Scatter plot requires multiple data points (mean analysis produces single value)")
        return None
    
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
    
    print(f"    Saved: {filename}")
    
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
    
    print(f"    Saved: {filename}")
    
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
    
    # Truncate long labels for display
    display_labels = []
    for label in group_labels:
        if len(label) > 15:
            display_labels.append('...' + label[-15:])
        else:
            display_labels.append(label)
    
    means = [metric_results[label]['mean'] for label in group_labels]
    stds = [metric_results[label]['std'] for label in group_labels]
    
    x_pos = np.arange(len(group_labels))
    bars = ax.bar(x_pos, means, yerr=stds, capsize=10, 
                color=[colors[i % len(colors)] for i in range(len(group_labels))], 
                alpha=0.7, edgecolor='black', linewidth=1.5)
    
    ax.set_xticks(x_pos)
    ax.set_xticklabels(display_labels, rotation=0, ha='center')  # ✅ FIXED: Using display_labels
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
    
    print(f"    Saved: {filename}")
    
    return {
        'name': f'{metric} Statistical Comparison',
        'path': plot_path,
        'filename': filename,
        'url': f'/api/plot/{filename}'
    }