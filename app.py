from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import subprocess
import json
import shutil
import re
import pandas as pd
import io
from datetime import datetime
import numpy as np

from analysis_utils import (
    prepare_event_markers_timestamps,
    find_timestamp_offset,
    match_event_markers_to_biometric
)

app = Flask(__name__, static_folder='frontend/build', static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max
CORS(app)

UPLOAD_FOLDER = 'data'
OUTPUT_FOLDER = 'data/outputs'
NOTEBOOK_PATH = 'data_analysis.ipynb'
ALLOWED_EXTENSIONS = {'csv'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/hello', methods=['GET'])
def hello():
    return jsonify({'message': 'Hello from Flask!'})

@app.route('/api/upload-folder-and-analyze', methods=['POST'])
def upload_folder_and_analyze():
    """Upload subject folder and execute notebook analysis"""
    
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('files')
    paths = request.form.getlist('paths')
    folder_name = request.form.get('folder_name', 'subject_data')
    
    # Get analysis configuration
    selected_metrics = json.loads(request.form.get('selected_metrics', '[]'))
    comparison_groups = json.loads(request.form.get('comparison_groups', '[]'))
    
    print(f"Analysis Configuration:")
    print(f"  Selected Metrics: {selected_metrics}")
    
    if not files or len(files) == 0:
        return jsonify({'error': 'No files in upload'}), 400
    
    try:
        subject_folder = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(folder_name))
        
        if os.path.exists(subject_folder):
            shutil.rmtree(subject_folder)
        
        os.makedirs(subject_folder, exist_ok=True)
        
        file_manifest = {
            'emotibit_files': [],
            'respiration_files': [],
            'event_markers': None,
            'ser_file': None,
            'other_files': []
        }
        
        for file, path in zip(files, paths):
            if not allowed_file(file.filename):
                continue
            
            relative_path = path.split('/', 1)[1] if '/' in path else file.filename
            file_path = os.path.join(subject_folder, relative_path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            filename_lower = file.filename.lower()
            path_depth = len(path.split('/'))
            
            if 'emotibit_data' in path.lower():
                file_manifest['emotibit_files'].append({
                    'filename': file.filename,
                    'path': file_path,
                    'relative_path': relative_path
                })
            elif 'respiration_data' in path.lower():
                file_manifest['respiration_files'].append({
                    'filename': file.filename,
                    'path': file_path,
                    'relative_path': relative_path
                })
            elif path_depth == 2 and filename_lower.endswith('_event_markers.csv'):
                file_manifest['event_markers'] = {
                    'filename': file.filename,
                    'path': file_path,
                    'relative_path': relative_path
                }
            elif 'ser' in filename_lower or 'transcription' in filename_lower:
                file_manifest['ser_file'] = {
                    'filename': file.filename,
                    'path': file_path,
                    'relative_path': relative_path
                }
            else:
                file_manifest['other_files'].append({
                    'filename': file.filename,
                    'path': file_path,
                    'relative_path': relative_path
                })
        
        # Add analysis configuration to manifest
        file_manifest['analysis_config'] = {
            'selected_metrics': selected_metrics,
            'comparison_groups': comparison_groups
        }
        
        manifest_path = os.path.join(subject_folder, 'file_manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump(file_manifest, f, indent=2)
        
        print(f"Files organized in: {subject_folder}")
        print(f"Event markers file: {file_manifest['event_markers']}")
        
        if file_manifest['emotibit_files']:
            ground_truth_path = os.path.join(app.config['UPLOAD_FOLDER'], 'ground_truth.csv')
            shutil.copy(file_manifest['emotibit_files'][0]['path'], ground_truth_path)
        
        if file_manifest['event_markers']:
            markers_path = os.path.join(app.config['UPLOAD_FOLDER'], 'markers.csv')
            shutil.copy(file_manifest['event_markers']['path'], markers_path)
        else:
            print("WARNING: No event markers file found!")
        
        print("Executing notebook...")
        result = subprocess.run(
            [
                'jupyter', 'nbconvert',
                '--to', 'notebook',
                '--execute',
                '--inplace',
                NOTEBOOK_PATH
            ],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            error_msg = f"Notebook execution failed: {result.stderr}"
            print(error_msg)
            return jsonify({'error': error_msg}), 500
        
        print("Notebook executed successfully")
        
        results_path = os.path.join(OUTPUT_FOLDER, 'results.json')
        if os.path.exists(results_path):
            with open(results_path, 'r') as f:
                results = json.load(f)
            
            for plot in results.get('plots', []):
                plot['url'] = f"/api/plot/{plot['filename']}"
            
            results['file_manifest'] = file_manifest
            
            return jsonify({
                'message': 'Analysis completed successfully',
                'results': results,
                'folder_name': folder_name
            }), 200
        else:
            return jsonify({'error': 'Results file not found'}), 500
        
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Notebook execution timed out'}), 500
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return jsonify({'error': error_msg}), 500
    
@app.route('/api/plot/<filename>', methods=['GET'])
def serve_plot(filename):
    """Serve matplotlib plot images"""
    try:
        file_path = os.path.join(OUTPUT_FOLDER, filename)
        if os.path.exists(file_path):
            return send_file(file_path, mimetype='image/png')
        else:
            return jsonify({'error': 'Plot not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/results', methods=['GET'])
def get_results():
    """Get the latest analysis results"""
    try:
        results_path = os.path.join(OUTPUT_FOLDER, 'results.json')
        if os.path.exists(results_path):
            with open(results_path, 'r') as f:
                results = json.load(f)
            
            for plot in results.get('plots', []):
                plot['url'] = f"/api/plot/{plot['filename']}"
            
            return jsonify(results), 200
        else:
            return jsonify({'error': 'No results available'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/save_images', methods=['POST'])
def save_images():
    """Save all PNG images from OUTPUT_FOLDER to a specified target folder"""
    try:
        data = request.get_json()
        folder_name = data.get('folder_name', 'default_folder')
        target_folder = os.path.join('data', secure_filename(folder_name))
        os.makedirs(target_folder, exist_ok=True)
        
        for filename in os.listdir(OUTPUT_FOLDER):
            if filename.endswith('.png'):
                src_path = os.path.join(OUTPUT_FOLDER, filename)
                dst_path = os.path.join(target_folder, filename)
                shutil.copy2(src_path, dst_path)
        
        return jsonify({'message': f'Images saved to {target_folder}'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scan-folder-data', methods=['POST'])
def scan_folder_data():
    """Scan folder for metrics, event markers, and conditions"""
    try:
        # Get emotibit filenames
        emotibit_filenames_json = request.form.get('emotibit_filenames')
        if not emotibit_filenames_json:
            return jsonify({'error': 'No emotibit filenames provided'}), 400
        
        emotibit_filenames = json.loads(emotibit_filenames_json)
        print(f"Scanning {len(emotibit_filenames)} EmotiBit files")
        
        # Extract metric tags from filenames
        metrics = set()
        exclude_tags = {'timesyncs', 'timesyncmap'}
        
        for filename in emotibit_filenames:
            match = re.search(r'_emotibit_ground_truth_([A-Z0-9%]+)\.csv$', filename)
            if match:
                metric_tag = match.group(1)
                if metric_tag.lower() not in exclude_tags:
                    metrics.add(metric_tag)
        
        metrics_list = sorted(list(metrics))
        print(f"Found {len(metrics_list)} metrics: {metrics_list}")
        
        # Extract event markers and conditions from event markers file
        event_markers = []
        conditions = []
        if 'event_markers_file' in request.files:
            event_markers_file = request.files['event_markers_file']
            print(f"Processing event markers file: {event_markers_file.filename}")
            
            try:
                # Read the CSV file
                import pandas as pd
                import io
                
                # Read file content
                file_content = event_markers_file.read()
                
                # Try to decode with different encodings
                try:
                    content_str = file_content.decode('utf-8')
                except UnicodeDecodeError:
                    content_str = file_content.decode('latin-1')
                
                # Parse CSV
                df = pd.read_csv(io.StringIO(content_str))
                
                print(f"Event markers CSV columns: {df.columns.tolist()}")
                
                # Extract event markers
                if 'event_marker' in df.columns:
                    # Get unique event markers, excluding NaN/None
                    unique_markers = df['event_marker'].dropna().unique()
                    
                    # Process markers - normalize PRS markers
                    processed_markers = set()
                    for marker in unique_markers:
                        marker_str = str(marker)
                        
                        # Check if marker contains PRS (case insensitive)
                        if 'prs_' in marker_str.lower():
                            # Extract just prs_N format
                            prs_match = re.search(r'(prs_\d+)', marker_str, re.IGNORECASE)
                            if prs_match:
                                # Normalize to lowercase
                                normalized_prs = prs_match.group(1).lower()
                                processed_markers.add(normalized_prs)
                            else:
                                # If no number found, just add the original
                                processed_markers.add(marker_str)
                        else:
                            # Not a PRS marker, add as-is
                            processed_markers.add(marker_str)
                    
                    event_markers = sorted(list(processed_markers))
                    print(f"Found {len(event_markers)} unique event markers: {event_markers}")
                else:
                    print(f"WARNING: 'event_marker' column not found in CSV")
                
                # Extract conditions
                if 'condition' in df.columns:
                    # Get unique conditions, excluding NaN/None
                    unique_conditions = df['condition'].dropna().unique()
                    conditions = sorted([str(cond) for cond in unique_conditions])
                    print(f"Found {len(conditions)} unique conditions: {conditions}")
                else:
                    print(f"WARNING: 'condition' column not found in CSV")
                    
            except Exception as e:
                error_msg = f"Error reading event markers file: {str(e)}"
                print(error_msg)
                import traceback
                traceback.print_exc()
        else:
            print("No event markers file provided")
        
        return jsonify({
            'metrics': metrics_list,
            'metrics_count': len(metrics_list),
            'event_markers': event_markers,
            'event_markers_count': len(event_markers),
            'conditions': conditions,
            'conditions_count': len(conditions)
        }), 200
        
    except Exception as e:
        error_msg = f"Error scanning folder data: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return jsonify({'error': error_msg}), 500

@app.route('/api/test-timestamp-matching', methods=['POST'])
def test_timestamp_matching():
    """Test route to verify timestamp offset correction and matching"""
    try:
        files = request.files.getlist('files')
        paths = request.form.getlist('paths')
        selected_metric = request.form.get('selected_metric')
        
        if not selected_metric:
            return jsonify({'error': 'No metric selected'}), 400
        
        if not files or len(files) == 0:
            return jsonify({'error': 'No files uploaded'}), 400
        
        print(f"\n{'='*60}")
        print(f"TESTING TIMESTAMP MATCHING FOR METRIC: {selected_metric}")
        print(f"{'='*60}\n")
        
        # Organize uploaded files temporarily for testing
        test_folder = os.path.join(UPLOAD_FOLDER, 'test_temp')
        if os.path.exists(test_folder):
            shutil.rmtree(test_folder)
        os.makedirs(test_folder, exist_ok=True)
        
        event_markers_file = None
        metric_file = None
        
        print("Processing uploaded files...")
        for file, path in zip(files, paths):
            if not allowed_file(file.filename):
                continue
            
            relative_path = path.split('/', 1)[1] if '/' in path else file.filename
            file_path = os.path.join(test_folder, relative_path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            
            filename_lower = file.filename.lower()
            path_depth = len(path.split('/'))
            
            # Find event markers file
            if path_depth == 2 and filename_lower.endswith('_event_markers.csv'):
                event_markers_file = file_path
                print(f"  Found event markers: {file.filename}")
            
            # Find the metric file
            if f'_{selected_metric}.csv' in file.filename:
                metric_file = file_path
                print(f"  Found metric file: {file.filename}")
        
        if not event_markers_file:
            shutil.rmtree(test_folder)
            return jsonify({'error': 'Event markers file not found in uploaded folder'}), 404
        
        if not metric_file:
            shutil.rmtree(test_folder)
            return jsonify({'error': f'Could not find file for metric {selected_metric}'}), 404
        
        print(f"\nLoading event markers from: {event_markers_file}")
        event_markers_df = pd.read_csv(event_markers_file)
        print(f"Event markers shape: {event_markers_df.shape}")
        print(f"Event markers columns: {event_markers_df.columns.tolist()}\n")
        
        # Prepare timestamps (handles backward compatibility)
        print("Preparing event marker timestamps...")
        try:
            event_markers_df = prepare_event_markers_timestamps(event_markers_df)
        except ValueError as e:
            shutil.rmtree(test_folder)
            return jsonify({'error': str(e)}), 400
        print()
        
        print(f"Loading biometric data from: {metric_file}")
        emotibit_df = pd.read_csv(metric_file)
        print(f"Biometric data shape: {emotibit_df.shape}")
        print(f"Biometric data columns: {emotibit_df.columns.tolist()}\n")
        
        # Verify required columns exist
        if 'LocalTimestamp' not in emotibit_df.columns:
            shutil.rmtree(test_folder)
            return jsonify({'error': f'LocalTimestamp column not found in {selected_metric} file. Columns: {emotibit_df.columns.tolist()}'}), 400
        
        # Calculate offset using ALL timestamps
        print("Calculating timestamp offset...")
        offset = find_timestamp_offset(event_markers_df, emotibit_df)
        print()
        
        # Test alignment by sampling timestamps across both files
        print("Testing timestamp alignment across both continuous streams...")
        
        # Apply offset to emotibit timestamps
        emotibit_df['AdjustedTimestamp'] = emotibit_df['LocalTimestamp'] + offset
        
        # Sample timestamps from event markers file (every Nth row for performance)
        sample_size = min(100, len(event_markers_df))
        sample_indices = np.linspace(0, len(event_markers_df)-1, sample_size, dtype=int)
        
        matches_within_tolerance = 0
        tolerance = 2.0  # seconds
        time_diffs = []
        
        print(f"Testing {sample_size} sampled timestamps from event marker stream...")
        for idx in sample_indices:
            event_time = event_markers_df.iloc[idx]['unix_timestamp']
            
            # Find closest timestamp in emotibit data
            time_diffs_abs = (emotibit_df['AdjustedTimestamp'] - event_time).abs()
            min_diff = time_diffs_abs.min()
            time_diffs.append(min_diff)
            
            if min_diff <= tolerance:
                matches_within_tolerance += 1
        
        avg_diff = np.mean(time_diffs)
        max_diff = np.max(time_diffs)
        min_diff_val = np.min(time_diffs)
        
        print(f"\nAlignment Test Results:")
        print(f"  Sampled {sample_size} timestamps")
        print(f"  Matches within {tolerance}s tolerance: {matches_within_tolerance}/{sample_size}")
        print(f"  Average time difference: {avg_diff:.3f}s")
        print(f"  Min time difference: {min_diff_val:.3f}s")
        print(f"  Max time difference: {max_diff:.3f}s")
        print(f"{'='*80}\n")
        
        # Clean up test folder
        shutil.rmtree(test_folder)
        
        return jsonify({
            'message': 'Timestamp alignment test completed',
            'metric': selected_metric,
            'offset_seconds': float(offset),
            'offset_hours': float(offset / 3600),
            'total_sampled': int(sample_size),
            'matches_within_tolerance': int(matches_within_tolerance),
            'avg_time_diff': float(avg_diff),
            'max_time_diff': float(max_diff),
            'min_time_diff': float(min_diff_val)
        }), 200
        
    except Exception as e:
        error_msg = f"Error in timestamp matching test: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        # Clean up on error
        test_folder = os.path.join(UPLOAD_FOLDER, 'test_temp')
        if os.path.exists(test_folder):
            shutil.rmtree(test_folder)
        return jsonify({'error': error_msg}), 500
    
@app.route('/')
def serve():
    return send_from_directory(app.static_folder, 'index.html')

@app.errorhandler(404)
def not_found(e):
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5001)