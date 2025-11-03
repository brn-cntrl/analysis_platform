from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
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
from analysis_runner import run_analysis

app = Flask(__name__, static_folder='frontend/build', static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max
CORS(app)

UPLOAD_FOLDER = 'data'
OUTPUT_FOLDER = 'data/outputs'
ALLOWED_EXTENSIONS = {'csv'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max

STUDENTS_FILE = 'data/students.json'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_students():
    """Load students from JSON file"""
    if os.path.exists(STUDENTS_FILE):
        with open(STUDENTS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_students(students):
    """Save students to JSON file"""
    os.makedirs('data', exist_ok=True)
    with open(STUDENTS_FILE, 'w') as f:
        json.dump(students, f, indent=2)

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    student_id = data.get('student_id', '').lower().strip()
    
    students = load_students()
    
    if student_id in students:
        return jsonify({
            'success': True, 
            'name': students[student_id]['name']
        }), 200
    
    return jsonify({'error': 'Student ID not found'}), 404

def generate_student_id(first_name, last_name, students):
    """Generate a unique student ID from first name and last name"""
    from datetime import datetime
    
    base_id = (first_name[0] + last_name).lower().replace(' ', '')
    year = datetime.now().year
    
    student_id = f"{base_id}{year}"

    counter = 1
    while student_id in students:
        student_id = f"{base_id}{year}_{counter}"
        counter += 1
    
    return student_id

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    email = data.get('email', '').strip()
    
    if not first_name or not last_name or not email:
        return jsonify({'error': 'First name, last name, and email are required'}), 400
    
    students = load_students()
    
    student_id = generate_student_id(first_name, last_name, students)
    full_name = f"{first_name} {last_name}"
    
    students[student_id] = {
        'name': full_name,
        'email': email,
        'registered_at': datetime.now().isoformat()
    }
    
    save_students(students)
    
    return jsonify({
        'success': True,
        'student_id': student_id,  # Return generated ID
        'name': full_name
    }), 201

@app.route('/api/upload-folder-and-analyze', methods=['POST'])
def upload_folder_and_analyze():
    """
    Handle a multipart/form-data POST that uploads a subject (or batch of subjects) folder,
    organizes the uploaded files into a standardized manifest, and runs analysis on the
    organized data.
    This route expects a multipart/form-data request (typically from a browser or frontend
    uploader) containing one or more files and a set of form fields describing how to run
    the analysis. The function:
    - Validates that files were uploaded.
    - Extracts parameters from request.form and request.files.
    - Saves uploaded files into a subject-specific folder under app.config['UPLOAD_FOLDER'].
    - Builds a file_manifest describing categorized files (emotibit, respiration, event markers,
        SER/transcription, and other files).
    - Transforms frontend event selection into "comparison_groups" used by the analysis.
    - Persists file_manifest to disk (file_manifest.json).
    - Invokes run_analysis(...) with the assembled parameters.
    - Persists analysis results to OUTPUT_FOLDER/results.json and augments plot entries with
        URLs (/api/plot/<filename>).
    - Returns a JSON response containing the results or an error message.
    Expected HTTP form fields (all values are strings as sent by form/data inputs):
    - files: uploaded file parts (multipart file list). Required.
    - paths: list of path strings matching each uploaded file's relative path inside the
        subject folder (must align 1:1 with files list). Each path helps recreate the folder
        structure when saving files on the server.
    - student_id: (optional) string to namespace uploads per student. Defaults to 'unknown'.
    - folder_name: (optional) subfolder name under the student's folder. Defaults to 'subject_data'.
    - selected_metrics: JSON-encoded array of metric identifiers (e.g. '["eda", "hr", ...]').
    - selected_events: JSON-encoded array of event selector objects, each expected to be:
            { "event": "<event_marker>" , "condition": "<condition_marker_or_all>" }
        Example: [{"event":"stimulus_onset","condition":"A"},{"event":"all","condition":"all"}]
    - analysis_method: (optional) string denoting the analysis pipeline to use (default 'raw').
    - plot_type: (optional) string indicating plot style (default 'lineplot').
    - analyze_hrv: JSON-encoded boolean string ("true"/"false") indicating whether to run HRV.
    - batch_mode: "true" or "false" as string. When "true", perform analysis across multiple
        selected_subjects.
    - selected_subjects: JSON-encoded list of subject identifiers (used only if batch_mode is true).
    File categorization rules (when building file_manifest):
    - If the provided path contains "emotibit_data" (case-insensitive), the file is added to
        emotibit_files.
    - If the path contains "respiration_data", the file is added to respiration_files.
    - If the filename lowercased ends with "_event_markers.csv", it is recorded as event_markers.
    - If the filename contains "ser" or "transcription" (case-insensitive), it is recorded as ser_file.
    - All other allowed files are appended to other_files.
    - Files are only saved and recorded if allowed_file(file.filename) returns True.
    Comparison groups transformation:
    - Each entry in selected_events is converted to a comparison_group dict:
            {
                'label': <human readable label>,
                'eventMarker': <event marker string>,
                'conditionMarker': <condition string or empty if 'all'>,
                'timeWindowType': 'full',
    - Special handling: event == 'all' -> label 'Entire Experiment'. condition == 'all'
        -> conditionMarker set to empty string.
    Output / side effects:
    - Files are saved under: os.path.join(app.config['UPLOAD_FOLDER'], student_id, secure_filename(folder_name))
    - A file_manifest.json is written into the subject folder describing the uploaded files and
        analysis configuration.
    - run_analysis(...) is invoked with the following keyword parameters:
            subject_folder, manifest, selected_metrics, comparison_groups,
            analysis_method, plot_type, analyze_hrv, output_folder, batch_mode, selected_subjects
    - Results returned by run_analysis are saved to OUTPUT_FOLDER/results.json.
    - Any plot entries in results['plots'] will be annotated with a URL of the form:
        "/api/plot/<filename>"
    Responses:
    - 200: JSON body with message, results, and folder_name on successful analysis.
    - 400: JSON error when required inputs are missing (e.g. no files uploaded or no files in upload).
    - 500: JSON error with exception details on unexpected server-side failure.
    Errors and exceptions:
    - The route catches all exceptions raised during file handling or analysis, logs the traceback,
        and returns a 500 response with the exception message.
    - The function skips files that do not satisfy allowed_file(filename) and will proceed with
        the remaining valid files.
    """
    
    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    # Extract form parameters
    student_id = request.form.get('student_id', 'unknown')
    folder_name = request.form.get('folder_name', 'subject_data')
    subject_folder = os.path.join(app.config['UPLOAD_FOLDER'], student_id, secure_filename(folder_name))

    files = request.files.getlist('files')
    paths = request.form.getlist('paths')

    # Parse frontend parameters
    selected_metrics = json.loads(request.form.get('selected_metrics', '[]'))
    selected_events = json.loads(request.form.get('selected_events', '[]'))
    analysis_method = request.form.get('analysis_method', 'raw')
    plot_type = request.form.get('plot_type', 'lineplot')
    analyze_hrv = json.loads(request.form.get('analyze_hrv', 'false'))
    
    # Multi-subject parameters
    batch_mode = request.form.get('batch_mode', 'false') == 'true'
    selected_subjects = []
    if batch_mode:
        selected_subjects = json.loads(request.form.get('selected_subjects', '[]'))
    
    print(f"\n{'='*80}")
    print(f"ANALYSIS REQUEST RECEIVED")
    print(f"{'='*80}")
    print(f"Student ID: {student_id}")
    print(f"Folder: {folder_name}")
    print(f"Metrics: {selected_metrics}")
    print(f"Events: {selected_events}")
    print(f"Analysis Method: {analysis_method}")
    print(f"Plot Type: {plot_type}")
    print(f"Analyze HRV: {analyze_hrv}")
    print(f"Batch Mode: {batch_mode}")
    if batch_mode:
        print(f"Selected Subjects: {selected_subjects}")
    print(f"{'='*80}\n")
    
    # Transform selected_events to comparison_groups format
    comparison_groups = []
    for idx, event_config in enumerate(selected_events):
        event_marker = event_config.get('event', '')
        condition_marker = event_config.get('condition', 'all')
        
        if not event_marker or event_marker == '':
            continue
        
        # Create label for this comparison group
        if event_marker == 'all':
            label = 'Entire Experiment'
        else:
            label = event_marker
            if condition_marker and condition_marker != 'all':
                label += f" ({condition_marker})"
        
        comparison_group = {
            'label': label,
            'eventMarker': event_marker,
            'conditionMarker': condition_marker if condition_marker != 'all' else '',
            'timeWindowType': 'full',  # Default to full window
            'customStart': 0,
            'customEnd': 0
        }
        
        comparison_groups.append(comparison_group)
    
    print(f"Transformed comparison groups:")
    for group in comparison_groups:
        print(f"  - {group['label']}")
    print()
    
    if not files or len(files) == 0:
        return jsonify({'error': 'No files in upload'}), 400
    
    try:
        # Organize files into manifest (existing code preserved)
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
            elif filename_lower.endswith('_event_markers.csv'):
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
            'comparison_groups': comparison_groups,
            'analysis_method': analysis_method,
            'plot_type': plot_type,
            'batch_mode': batch_mode,
            'selected_subjects': selected_subjects
        }
        
        manifest_path = os.path.join(subject_folder, 'file_manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump(file_manifest, f, indent=2)
        
        print(f"Files organized in: {subject_folder}")
        print(f"Event markers file: {file_manifest['event_markers']}")
        print("Running analysis...")

        # Call analysis with all parameters
        results = run_analysis(
            subject_folder=subject_folder,
            manifest=file_manifest,
            selected_metrics=selected_metrics,
            comparison_groups=comparison_groups,
            analysis_method=analysis_method,
            plot_type=plot_type,
            analyze_hrv=analyze_hrv,
            output_folder=OUTPUT_FOLDER,
            batch_mode=batch_mode,
            selected_subjects=selected_subjects
        )
        
        print("Analysis completed successfully")
        
        # Update plot URLs
        for plot in results.get('plots', []):
            plot['url'] = f"/api/plot/{plot['filename']}"
        
        results['file_manifest'] = file_manifest
        
        # Save results to JSON file
        results_path = os.path.join(OUTPUT_FOLDER, 'results.json')
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        return jsonify({
            'message': 'Analysis completed successfully',
            'results': results,
            'folder_name': folder_name
        }), 200
        
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
    
    This route expects a JSON payload containing a 'folder_name' key. It creates a target folder 
    under 'data/' using the provided folder name (sanitized for security), and copies all PNG 
    images from the OUTPUT_FOLDER to the target folder. If the folder does not exist, it will be created.
    
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
    Scans provided EmotiBit filenames and an optional event markers file to extract available 
    metrics, event markers, and conditions.
    
    This route expects a POST request with the following form data:
        - 'emotibit_filenames': A JSON-encoded list of EmotiBit CSV filenames.
        - 'event_markers_file' (optional): A CSV file containing event markers and conditions.
    
    The function performs the following:
        - Parses the filenames to extract unique metric tags, excluding 'timesyncs' and 'timesyncmap'.
        - If an event markers file is provided, reads the CSV to extract unique event markers 
          (with normalization for PRS markers) and conditions.
        - Returns a JSON response containing:
            - 'metrics': List of unique metric tags found.
            - 'metrics_count': Number of metrics.
            - 'event_markers': List of unique event markers found.
            - 'event_markers_count': Number of event markers.
            - 'conditions': List of unique conditions found.
            - 'conditions_count': Number of conditions.
    
    Returns:
        Response: JSON object with extracted metrics, event markers, and conditions, 
                  or an error message with appropriate HTTP status code.
    """
    try:
        emotibit_filenames_json = request.form.get('emotibit_filenames')
        if not emotibit_filenames_json:
            return jsonify({'error': 'No emotibit filenames provided'}), 400
        
        emotibit_filenames = json.loads(emotibit_filenames_json)
        print(f"Scanning {len(emotibit_filenames)} EmotiBit files")
        
        detected_subjects_json = request.form.get('detected_subjects')
        detected_subjects = []
        if detected_subjects_json:
            detected_subjects = json.loads(detected_subjects_json)
            print(f"Batch mode detected: {len(detected_subjects)} subjects found")
            print(f"Subjects: {detected_subjects}")

        # BATCH MODE: Multiple subjects
        if len(detected_subjects) > 1:
            print("\n=== BATCH MODE: Calculating intersection ===\n")
            
            # Initialize per-subject data structures
            subject_availability = {}
            for subject in detected_subjects:
                subject_availability[subject] = {
                    'metrics': set(),
                    'event_markers': set(),
                    'conditions': set()
                }
            
            # Extract metrics from filenames organized by subject
            exclude_tags = {'timesyncs', 'timesyncmap'}
            for filename in emotibit_filenames:
                # Extract subject from filename path
                # Assuming format: root/subject_xxx/emotibit_data/file.csv
                parts = filename.split('/')
                if len(parts) >= 3:
                    subject = parts[1]
                    if subject in subject_availability:
                        match = re.search(r'_emotibit_ground_truth_([A-Z0-9%]+)\.csv$', filename)
                        if match:
                            metric_tag = match.group(1)
                            if metric_tag.lower() not in exclude_tags:
                                subject_availability[subject]['metrics'].add(metric_tag)
            
            # Process event markers files (one per subject)
            event_markers_files = request.files.getlist('event_markers_files')
            event_markers_paths = request.form.getlist('event_markers_paths')
            
            print(f"Processing {len(event_markers_files)} event markers files")
            
            for em_file, em_path in zip(event_markers_files, event_markers_paths):
                # Extract subject from path
                parts = em_path.split('/')
                if len(parts) >= 2:
                    subject = parts[1]
                    print(f"  Processing event markers for subject: {subject}")
                    
                    if subject in subject_availability:
                        try:
                            file_content = em_file.read()
                            try:
                                content_str = file_content.decode('utf-8')
                            except UnicodeDecodeError:
                                content_str = file_content.decode('latin-1')
                            
                            df = pd.read_csv(io.StringIO(content_str))
                            
                            # Extract event markers
                            if 'event_marker' in df.columns:
                                unique_markers = df['event_marker'].dropna().unique()
                                processed_markers = set()
                                for marker in unique_markers:
                                    marker_str = str(marker)
                                    if 'prs_' in marker_str.lower():
                                        prs_match = re.search(r'(prs_\d+)', marker_str, re.IGNORECASE)
                                        if prs_match:
                                            processed_markers.add(prs_match.group(1).lower())
                                        else:
                                            processed_markers.add(marker_str)
                                    else:
                                        processed_markers.add(marker_str)
                                
                                subject_availability[subject]['event_markers'].update(processed_markers)
                                print(f"    Found {len(processed_markers)} event markers")
                            
                            # Extract conditions
                            if 'condition' in df.columns:
                                unique_conditions = df['condition'].dropna().unique()
                                subject_availability[subject]['conditions'].update([str(c) for c in unique_conditions])
                                print(f"    Found {len(unique_conditions)} conditions")
                            
                            # Reset file pointer
                            em_file.seek(0)
                        except Exception as e:
                            print(f"    ERROR processing event markers for {subject}: {e}")
            
            # Calculate intersection across all subjects
            if len(subject_availability) > 0:
                subjects_list = list(subject_availability.keys())
                
                # Metrics intersection
                common_metrics = subject_availability[subjects_list[0]]['metrics'].copy()
                for subject in subjects_list[1:]:
                    common_metrics &= subject_availability[subject]['metrics']
                metrics_list = sorted(list(common_metrics))
                
                # Event markers intersection
                common_markers = subject_availability[subjects_list[0]]['event_markers'].copy()
                for subject in subjects_list[1:]:
                    common_markers &= subject_availability[subject]['event_markers']
                event_markers = sorted(list(common_markers))
                
                # Conditions intersection
                common_conditions = subject_availability[subjects_list[0]]['conditions'].copy()
                for subject in subjects_list[1:]:
                    common_conditions &= subject_availability[subject]['conditions']
                conditions = sorted(list(common_conditions))
                
                print(f"\nIntersection results:")
                print(f"  Common metrics: {len(metrics_list)}")
                print(f"  Common event markers: {len(event_markers)}")
                print(f"  Common conditions: {len(conditions)}")
            else:
                metrics_list = []
                event_markers = []
                conditions = []
            
            # Convert sets to lists for JSON serialization
            subject_availability_json = {}
            for subject, data in subject_availability.items():
                subject_availability_json[subject] = {
                    'metrics': sorted(list(data['metrics'])),
                    'event_markers': sorted(list(data['event_markers'])),
                    'conditions': sorted(list(data['conditions']))
                }
            
            return jsonify({
                'metrics': metrics_list,
                'metrics_count': len(metrics_list),
                'event_markers': event_markers,
                'event_markers_count': len(event_markers),
                'conditions': conditions,
                'conditions_count': len(conditions),
                'subjects': detected_subjects,
                'subjects_count': len(detected_subjects),
                'batch_mode': True,
                'subject_availability': subject_availability_json
            }), 200

        # SINGLE SUBJECT MODE
        else:
            print("\n=== SINGLE SUBJECT MODE ===\n")
            
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
                'conditions_count': len(conditions),
                'subjects': detected_subjects if detected_subjects else [],
                'subjects_count': len(detected_subjects) if detected_subjects else 0,
                'batch_mode': False
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