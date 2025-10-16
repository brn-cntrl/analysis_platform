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

# @app.route('/api/hello', methods=['GET'])
# def hello():
#     return jsonify({'message': 'Hello from Flask!'})

@app.route('/api/upload-folder-and-analyze', methods=['POST'])
def upload_folder_and_analyze():
    """
    Handles the upload of multiple files and folders, organizes them into a structured directory,
    generates a manifest of uploaded files, and triggers analysis by executing a Jupyter notebook.
    Workflow:
    - Validates the presence of uploaded files in the request.
    - Extracts file objects, their relative paths, folder name, selected metrics, and comparison groups from the request.
    - Organizes files into a subject-specific folder, preserving their relative paths.
    - Categorizes files into emotibit data, respiration data, event markers, SER/transcription files, and others.
    - Generates a manifest JSON file describing the uploaded files and analysis configuration.
    - Copies key files (emotibit and event markers) to standard locations for analysis.
    - Executes a Jupyter notebook for analysis, capturing output and errors.
    - Returns analysis results and manifest as a JSON response, or appropriate error messages.
    Returns:
        Response: JSON response containing analysis results, manifest, and status message,
                  or error details with appropriate HTTP status code.
    """
    
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('files')
    paths = request.form.getlist('paths')
    folder_name = request.form.get('folder_name', 'subject_data')

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
    """
    Serves a plot image file from the output folder.
    Args:
        filename (str): The name of the plot image file to serve.
    Returns:
        Response: If the file exists, returns the image file with 'image/png' MIME type.
                  If the file does not exist, returns a JSON error message with a 404 status code.
                  If an exception occurs, returns a JSON error message with a 500 status code.
    """

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
    """
    Retrieves analysis results from the results.json file and returns them as a JSON response.
    If the results file exists, the function loads its contents, updates plot URLs for API access,
    and returns the results with a 200 status code. If the file does not exist, returns a 404 error.
    Handles unexpected errors by returning a 500 error with the exception message.
    Returns:
        Response: Flask JSON response containing results data or error message.
    """
    
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
    """
    Saves PNG images from the output folder to a specified target folder.
    This route expects a JSON payload containing a 'folder_name' key. It creates a target folder under 'data/' using the provided folder name (sanitized for security), and copies all PNG images from the OUTPUT_FOLDER to the target folder. If the folder does not exist, it will be created.
    Returns:
        JSON response with a success message and HTTP 200 status code if images are saved successfully.
        JSON response with an error message and HTTP 500 status code if an exception occurs.
    """
    
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
    """
    Scans provided EmotiBit filenames and an optional event markers file to extract available metrics, event markers, and conditions.
    This route expects a POST request with the following form data:
        - 'emotibit_filenames': A JSON-encoded list of EmotiBit CSV filenames.
        - 'event_markers_file' (optional): A CSV file containing event markers and conditions.
    The function performs the following:
        - Parses the filenames to extract unique metric tags, excluding 'timesyncs' and 'timesyncmap'.
        - If an event markers file is provided, reads the CSV to extract unique event markers (with normalization for PRS markers) and conditions.
        - Returns a JSON response containing:
            - 'metrics': List of unique metric tags found.
            - 'metrics_count': Number of metrics.
            - 'event_markers': List of unique event markers found.
            - 'event_markers_count': Number of event markers.
            - 'conditions': List of unique conditions found.
            - 'conditions_count': Number of conditions.
    Returns:
        Response: JSON object with extracted metrics, event markers, and conditions, or an error message with appropriate HTTP status code.
    """
    
    try:
        emotibit_filenames_json = request.form.get('emotibit_filenames')
        if not emotibit_filenames_json:
            return jsonify({'error': 'No emotibit filenames provided'}), 400
        
        emotibit_filenames = json.loads(emotibit_filenames_json)
        print(f"Scanning {len(emotibit_filenames)} EmotiBit files")
        
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
        
        event_markers = []
        conditions = []
        if 'event_markers_file' in request.files:
            event_markers_file = request.files['event_markers_file']
            print(f"Processing event markers file: {event_markers_file.filename}")
            
            try:
                file_content = event_markers_file.read()
                
                try:
                    content_str = file_content.decode('utf-8')
                except UnicodeDecodeError:
                    content_str = file_content.decode('latin-1')
                
                df = pd.read_csv(io.StringIO(content_str))
                
                print(f"Event markers CSV columns: {df.columns.tolist()}")
                
                if 'event_marker' in df.columns:
                    unique_markers = df['event_marker'].dropna().unique()
                    
                    processed_markers = set()
                    for marker in unique_markers:
                        marker_str = str(marker)
                        
                        # Check if marker contains PRS. Needed because of unique PRS markers.
                        if 'prs_' in marker_str.lower():
                            prs_match = re.search(r'(prs_\d+)', marker_str, re.IGNORECASE)
                            if prs_match:
                                normalized_prs = prs_match.group(1).lower()
                                processed_markers.add(normalized_prs)
                            else:
                                processed_markers.add(marker_str)
                        else:
                            processed_markers.add(marker_str)
                    
                    event_markers = sorted(list(processed_markers))
                    print(f"Found {len(event_markers)} unique event markers: {event_markers}")
                else:
                    print(f"WARNING: 'event_marker' column not found in CSV")
                
                if 'condition' in df.columns:
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
    """
        NOTE:
            This is a test route to verify timestamp offset correction and matching.
            This endpoint is only for testing. It is replicated in the notebook analysis
            but leave this here for easy debugging.
    """
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
            
            if path_depth == 2 and filename_lower.endswith('_event_markers.csv'):
                event_markers_file = file_path
                print(f"  Found event markers: {file.filename}")
            
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
        
        if 'LocalTimestamp' not in emotibit_df.columns:
            shutil.rmtree(test_folder)
            return jsonify({'error': f'LocalTimestamp column not found in {selected_metric} file. Columns: {emotibit_df.columns.tolist()}'}), 400
        
        print("Calculating timestamp offset...")
        offset = find_timestamp_offset(event_markers_df, emotibit_df)
        print()
        
        print("Testing timestamp alignment across both continuous streams...")
        
        emotibit_df['AdjustedTimestamp'] = emotibit_df['LocalTimestamp'] + offset
        sample_size = min(100, len(event_markers_df))
        sample_indices = np.linspace(0, len(event_markers_df)-1, sample_size, dtype=int)
        
        matches_within_tolerance = 0
        tolerance = 2.0  # seconds
        time_diffs = []
        
        print(f"Testing {sample_size} sampled timestamps from event marker stream...")
        for idx in sample_indices:
            event_time = event_markers_df.iloc[idx]['unix_timestamp']
            
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