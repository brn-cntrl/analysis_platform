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
import subprocess

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

@app.route('/api/launch-emotibit-parser', methods=['POST'])
def launch_emotibit_parser():
    try:
        # TODO This will need to account for windows extenstions when ported
        executable_path = os.path.join(os.getcwd(), 'executables', 'EmotiBitDataParser.app')
        subprocess.Popen(['open', executable_path])
        
        return jsonify({
            "success": True, 
            "message": "EmotiBit DataParser launched successfully"
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False, 
            "error": str(e)
        }), 500

@app.route('/api/upload-folder-and-analyze', methods=['POST'])
def upload_folder_and_analyze():
    
    # ============================================================================
    # DEBUG: Log incoming request
    # ============================================================================
    print("\n" + "="*80)
    print("📥 UPLOAD AND ANALYZE REQUEST")
    print("="*80)
    print(f"Student ID: {request.form.get('student_id', 'unknown')}")
    print(f"Folder name: {request.form.get('folder_name', 'subject_data')}")
    print(f"Files received: {len(request.files.getlist('files'))}")
    print(f"Selected metrics: {request.form.get('selected_metrics', '[]')}")
    print(f"Selected events: {request.form.get('selected_events', '[]')}")
    print(f"Analysis method: {request.form.get('analysis_method', 'raw')}")
    print(f"Plot type: {request.form.get('plot_type', 'lineplot')}")
    print(f"Batch mode: {request.form.get('batch_mode', 'false')}")
    print(f"Analyze HRV: {request.form.get('analyze_hrv', 'false')}")
    print(f"Has PsychoPy: {request.form.get('has_psychopy_data', 'false')}")
    print("="*80 + "\n")

    if 'files' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400
    
    # Extract form parameters
    student_id = request.form.get('student_id', 'unknown')
    folder_name = request.form.get('folder_name', 'subject_data')
    upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], student_id, secure_filename(folder_name))

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
    
    # Parse PsychoPy data
    has_psychopy_data = request.form.get('has_psychopy_data', 'false') == 'true'
    psychopy_configs = {}
    if has_psychopy_data:
        psychopy_configs_json = request.form.get('psychopy_configs', '{}')
        try:
            psychopy_configs = json.loads(psychopy_configs_json)
            print(f"✓ Parsed PsychoPy configs for {len(psychopy_configs)} subjects")
        except json.JSONDecodeError as e:
            print(f"⚠️ Failed to parse PsychoPy configs: {e}")

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
        # Organize files into manifest 
        file_manifest = {
            'emotibit_files': [],
            'respiration_files': [],
            'event_markers': None,  # Single subject backward compatibility
            'event_markers_by_subject': {},  # Multi-subject support
            'psychopy_files': [],  # PsychoPy data files
            'psychopy_configs': {},  # PsychoPy configurations
            'ser_file': None,
            'other_files': []
        }
        
        for file, path in zip(files, paths):
            if not allowed_file(file.filename):
                continue
            
            relative_path = path.split('/', 1)[1] if '/' in path else file.filename
            file_path = os.path.join(upload_folder, relative_path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            
            filename_lower = file.filename.lower()
            
            # Extract subject from path (format: root/subject_xxx/...)
            path_parts = path.split('/')
            subject_name = path_parts[1] if len(path_parts) >= 3 else None
            
            if 'emotibit_data' in path.lower():
                file_manifest['emotibit_files'].append({
                    'filename': file.filename,
                    'path': file_path,
                    'relative_path': relative_path,
                    'subject': subject_name  # Add subject tracking
                })
            elif 'respiration_data' in path.lower():
                file_manifest['respiration_files'].append({
                    'filename': file.filename,
                    'path': file_path,
                    'relative_path': relative_path,
                    'subject': subject_name
                })
            elif filename_lower.endswith('_event_markers.csv'):
                # CRITICAL FIX: Support per-subject event markers
                if batch_mode and subject_name:
                    file_manifest['event_markers_by_subject'][subject_name] = {
                        'filename': file.filename,
                        'path': file_path,
                        'relative_path': relative_path
                    }
                    print(f"  ✓ Event markers for {subject_name}: {file.filename}")
                else:
                    # Single subject - backward compatibility
                    file_manifest['event_markers'] = {
                        'filename': file.filename,
                        'path': file_path,
                        'relative_path': relative_path
                    }
            elif 'psychopy_data' in path.lower() and filename_lower.endswith('.csv'):
                # NEW: Track PsychoPy files
                print(f"   ✅ CLASSIFIED AS PSYCHOPY FILE")
                file_manifest['psychopy_files'].append({
                    'filename': file.filename,
                    'path': file_path,
                    'relative_path': relative_path,
                    'subject': subject_name
                })
                print(f"  ✓ PsychoPy file for {subject_name}: {file.filename}")
            else:
                # ============================================================================
                # DEBUG: Catch unclassified files
                # ============================================================================
                print(f"   ⚠️  UNCLASSIFIED - adding to other_files")
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
        
        # Add PsychoPy configuration to manifest
        if has_psychopy_data and psychopy_configs:
            file_manifest['psychopy_configs'] = psychopy_configs
            print(f"✓ Added PsychoPy configs to manifest")

        manifest_path = os.path.join(upload_folder, 'file_manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump(file_manifest, f, indent=2)
        
        print(f"Files organized in: {upload_folder}")
        print(f"Event markers file: {file_manifest['event_markers']}")

        # ============================================================================
        # VALIDATION: Check analysis method and plot type compatibility
        # ============================================================================
        incompatible_combinations = {
            'mean': ['lineplot', 'scatter'],  # Mean is single value
            'rmssd': ['poincare'],  # Poincaré is for HRV analysis
        }
        
        if analysis_method in incompatible_combinations:
            if plot_type in incompatible_combinations[analysis_method]:
                error_msg = f"Plot type '{plot_type}' is incompatible with analysis method '{analysis_method}'. Please choose a different combination."
                print(f"❌ VALIDATION ERROR: {error_msg}")
                return jsonify({'error': error_msg}), 400
        
        # ============================================================================
        # DEBUG: Print manifest summary
        # ============================================================================
        print("\n📋 MANIFEST SUMMARY:")
        print(f"  EmotiBit files: {len(file_manifest['emotibit_files'])}")
        print(f"  PsychoPy files: {len(file_manifest.get('psychopy_files', []))}")
        if batch_mode:
            print(f"  Event markers (by subject): {len(file_manifest.get('event_markers_by_subject', {}))}")
            for subj, em_file in file_manifest.get('event_markers_by_subject', {}).items():
                print(f"    - {subj}: {em_file['filename']}")
        else:
            em = file_manifest.get('event_markers')
            print(f"  Event markers: {em['filename'] if em else 'None'}")
        print()
        
        print("Running analysis...")

        analysis_type = request.form.get('analysis_type', 'inter')

        # Call analysis with all parameters
        results = run_analysis(
            upload_folder=upload_folder,
            manifest=file_manifest,
            selected_metrics=selected_metrics,
            comparison_groups=comparison_groups,
            analysis_method=analysis_method,
            plot_type=plot_type,
            analyze_hrv=analyze_hrv,
            output_folder=OUTPUT_FOLDER,
            batch_mode=batch_mode,
            selected_subjects=selected_subjects,
            psychopy_configs=psychopy_configs,
            analysis_type=analysis_type
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
    Scans provided EmotiBit filenames and optional event markers, 
    and handles PsychoPy paths (no files uploaded).
    """
    try:
        # --- EmotiBit filenames ---
        emotibit_filenames_json = request.form.get('emotibit_filenames')
        if not emotibit_filenames_json:
            return jsonify({'error': 'No emotibit filenames provided'}), 400
        
        emotibit_filenames = json.loads(emotibit_filenames_json)
        print(f"Scanning {len(emotibit_filenames)} EmotiBit files")
        
        # --- Detected subjects (batch mode) ---
        detected_subjects_json = request.form.get('detected_subjects')
        detected_subjects = json.loads(detected_subjects_json) if detected_subjects_json else []
        if detected_subjects:
            print(f"Batch mode detected: {len(detected_subjects)} subjects found")
            print(f"Subjects: {detected_subjects}")

        psychopy_metadata_json = request.form.get('psychopy_metadata')
        psychopy_files_by_subject = {}

        if psychopy_metadata_json:
            psychopy_files_by_subject = json.loads(psychopy_metadata_json)
            print(f"DEBUG: Received PsychoPy metadata for {len(psychopy_files_by_subject)} subject(s)")
            
            for subject, files in psychopy_files_by_subject.items():
                print(f"  Subject {subject}: {len(files)} file(s)")
                for file_data in files:
                    print(f"    - {file_data['filename']}: {len(file_data.get('columns', []))} columns")

        # --- Process EmotiBit metrics and event markers ---
        exclude_tags = {'timesyncs', 'timesyncmap'}
        subject_availability = {}
        if detected_subjects:
            # batch mode
            for subject in detected_subjects:
                subject_availability[subject] = {'metrics': set(), 'event_markers': set(), 'conditions': set()}
            
            # Metrics
            for filename in emotibit_filenames:
                parts = filename.split('/')
                if len(parts) >= 3:
                    subject = parts[1]
                    if subject in subject_availability:
                        # Try old format first
                        match = re.search(r'_emotibit_ground_truth_([A-Z0-9%]+)\.csv$', filename)
                        if not match:
                            # Try new EmotiBit format: 2-4 uppercase letter codes (HR, EDA, PI, PR, PG, TEMP, etc.)
                            match = re.search(r'_([A-Z]{2,4})\.csv$', filename)
                        
                        if match:
                            tag = match.group(1)
                            if tag.lower() not in exclude_tags:
                                subject_availability[subject]['metrics'].add(tag)

            # Event markers
            event_markers_files = request.files.getlist('event_markers_files')
            event_markers_paths = request.form.getlist('event_markers_paths')
            for em_file, em_path in zip(event_markers_files, event_markers_paths):
                parts = em_path.split('/')
                if len(parts) >= 2:
                    subject = parts[1]
                    if subject in subject_availability:
                        try:
                            content_str = em_file.read().decode('utf-8', errors='replace')
                            df = pd.read_csv(io.StringIO(content_str))

                            if 'event_marker' in df.columns:
                                processed_markers = set()
                                for marker in df['event_marker'].dropna().unique():
                                    marker_str = str(marker)
                                    if 'prs_' in marker_str.lower():
                                        prs_match = re.search(r'(prs_\d+)', marker_str, re.IGNORECASE)
                                        processed_markers.add(prs_match.group(1).lower() if prs_match else marker_str)
                                    else:
                                        processed_markers.add(marker_str)
                                subject_availability[subject]['event_markers'].update(processed_markers)
                            
                            if 'condition' in df.columns:
                                subject_availability[subject]['conditions'].update(str(c) for c in df['condition'].dropna().unique())
                            em_file.seek(0)
                        except Exception as e:
                            print(f"ERROR processing event markers for {subject}: {e}")

            # Compute intersections
            subjects_list = list(subject_availability.keys())
            metrics_list = sorted(list(set.intersection(*(subject_availability[s]['metrics'] for s in subjects_list))))
            event_markers = sorted(list(set.intersection(*(subject_availability[s]['event_markers'] for s in subjects_list))))
            conditions = sorted(list(set.intersection(*(subject_availability[s]['conditions'] for s in subjects_list))))

            subject_availability_json = {s: {'metrics': sorted(list(subject_availability[s]['metrics'])),
                                             'event_markers': sorted(list(subject_availability[s]['event_markers'])),
                                             'conditions': sorted(list(subject_availability[s]['conditions']))}
                                         for s in subjects_list}

            batch_mode = True

        else:
            # single subject mode
            metrics = set()
            exclude_tags = {'timesyncs', 'timesyncmap'}
            
            for filename in emotibit_filenames:
                # Try old format first
                match = re.search(r'_emotibit_ground_truth_([A-Z0-9%]+)\.csv$', filename)
                if not match:
                    # Try new EmotiBit format: 2-4 uppercase letter codes (HR, EDA, PI, PR, PG, TEMP, etc.)
                    match = re.search(r'_([A-Z]{2,4})\.csv$', filename)
                
                if match:
                    metric_tag = match.group(1)
                    if metric_tag.lower() not in exclude_tags:
                        metrics.add(metric_tag)
            
            metrics_list = sorted(list(metrics))
            print(f"Found {len(metrics_list)} metrics: {metrics_list}")
            
            event_markers = []
            conditions = []

            if 'event_markers_file' in request.files:
                em_file = request.files['event_markers_file']
                try:
                    content_str = em_file.read().decode('utf-8', errors='replace')
                    df = pd.read_csv(io.StringIO(content_str))
                    if 'event_marker' in df.columns:
                        processed_markers = set()
                        for marker in df['event_marker'].dropna().unique():
                            marker_str = str(marker)
                            if 'prs_' in marker_str.lower():
                                prs_match = re.search(r'(prs_\d+)', marker_str, re.IGNORECASE)
                                processed_markers.add(prs_match.group(1).lower() if prs_match else marker_str)
                            else:
                                processed_markers.add(marker_str)
                        event_markers = sorted(list(processed_markers))
                    if 'condition' in df.columns:
                        conditions = sorted([str(c) for c in df['condition'].dropna().unique()])
                    em_file.seek(0)
                except Exception as e:
                    print(f"ERROR reading event markers file: {e}")

            subject_availability_json = {}
            batch_mode = False

        return jsonify({
            'metrics': metrics_list,
            'metrics_count': len(metrics_list),
            'event_markers': event_markers,
            'event_markers_count': len(event_markers),
            'conditions': conditions,
            'conditions_count': len(conditions),
            'subjects': detected_subjects if detected_subjects else [],
            'subjects_count': len(detected_subjects) if detected_subjects else 0,
            'batch_mode': batch_mode,
            'subject_availability': subject_availability_json,
            'psychopy_data': {
                'has_files': len(psychopy_files_by_subject) > 0,
                'files_by_subject': psychopy_files_by_subject,
                'subjects_with_psychopy': list(psychopy_files_by_subject.keys())
            }
        }), 200

    except Exception as e:
        print(f"Error scanning folder data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# @app.route('/api/scan-folder-data', methods=['POST'])
# def scan_folder_data():
#     """
#     Scans provided EmotiBit filenames and an optional event markers file to extract available 
#     metrics, event markers, and conditions.
    
#     This route expects a POST request with the following form data:
#         - 'emotibit_filenames': A JSON-encoded list of EmotiBit CSV filenames.
#         - 'event_markers_file' (optional): A CSV file containing event markers and conditions.
    
#     The function performs the following:
#         - Parses the filenames to extract unique metric tags, excluding 'timesyncs' and 'timesyncmap'.
#         - If an event markers file is provided, reads the CSV to extract unique event markers 
#           (with normalization for PRS markers) and conditions.
#         - Returns a JSON response containing:
#             - 'metrics': List of unique metric tags found.
#             - 'metrics_count': Number of metrics.
#             - 'event_markers': List of unique event markers found.
#             - 'event_markers_count': Number of event markers.
#             - 'conditions': List of unique conditions found.
#             - 'conditions_count': Number of conditions.
    
#     Returns:
#         Response: JSON object with extracted metrics, event markers, and conditions, 
#                   or an error message with appropriate HTTP status code.
#     """
#     try:
#         emotibit_filenames_json = request.form.get('emotibit_filenames')
#         if not emotibit_filenames_json:
#             return jsonify({'error': 'No emotibit filenames provided'}), 400
        
#         emotibit_filenames = json.loads(emotibit_filenames_json)
#         print(f"Scanning {len(emotibit_filenames)} EmotiBit files")
        
#         detected_subjects_json = request.form.get('detected_subjects')
#         detected_subjects = []
#         if detected_subjects_json:
#             detected_subjects = json.loads(detected_subjects_json)
#             print(f"Batch mode detected: {len(detected_subjects)} subjects found")
#             print(f"Subjects: {detected_subjects}")

#         # Scan for PsychoPy files
#         psychopy_files_by_subject = {}
#         files = request.files.getlist('files') if 'files' in request.files else []
#         paths = request.form.getlist('paths')
#         print(f"DEBUG: len(files)={len(files)}, len(paths)={len(paths)}")

#         print(f"\n=== Scanning for PsychoPy files ===")
#         for file, path in zip(files, paths):
#             print(f"Checking file: {file.filename}, path: {path}")
#             if 'psychopy_data' in path.lower() and file.filename.lower().endswith('.csv'):
#                 parts = path.split('/')
#                 if len(parts) >= 3:
#                     subject = parts[1]
                    
#                     if subject not in psychopy_files_by_subject:
#                         psychopy_files_by_subject[subject] = []
                    
#                     # Parse experiment type from filename
#                     # Format: <date>_<subject_name>_<experiment_name>_<experiment_number>.csv
#                     filename_parts = file.filename.replace('.csv', '').split('_')
#                     experiment_name = 'Unknown'
#                     if len(filename_parts) >= 3:
#                         experiment_name = filename_parts[2] if len(filename_parts) > 2 else filename_parts[-1]
                    
#                     print(f"Found PsychoPy file: {file.filename} for subject {subject}, experiment: {experiment_name}")
                    
#                     try:
#                         file_content = file.read()
#                         try:
#                             content_str = file_content.decode('utf-8')
#                         except UnicodeDecodeError:
#                             content_str = file_content.decode('latin-1')
                        
#                         df = pd.read_csv(io.StringIO(content_str))
                        
#                         valid_columns = [col for col in df.columns if not str(col).startswith('Unnamed:')]
#                         df = df[valid_columns]
                        
#                         columns = df.columns.tolist()
#                         column_types = []
                        
#                         for col in columns:
#                             dtype = df[col].dtype
                            
#                             if pd.api.types.is_numeric_dtype(dtype):
#                                 col_type = 'numeric'
#                             elif pd.api.types.is_datetime64_any_dtype(dtype):
#                                 col_type = 'datetime'
#                             else:
#                                 non_null_values = df[col].dropna()
#                                 if len(non_null_values) > 0:
#                                     sample_val = str(non_null_values.iloc[0])
#                                     if any(pattern in sample_val.lower() for pattern in ['_', ':', 'am', 'pm']) and \
#                                        any(char.isdigit() for char in sample_val):
#                                         col_type = 'datetime'
#                                     else:
#                                         col_type = 'string'
#                                 else:
#                                     col_type = 'string'
                            
#                             column_types.append(col_type)
                        
#                         # Get sample data (first 5 rows)
#                         sample_size = min(5, len(df))
#                         sample_df = df.head(sample_size)
                        
#                         sample_data = []
#                         for idx, row in sample_df.iterrows():
#                             row_dict = {}
#                             for col in columns:
#                                 val = row[col]
#                                 if pd.isna(val):
#                                     row_dict[col] = None
#                                 else:
#                                     row_dict[col] = val
#                             sample_data.append(row_dict)
                        
#                         psychopy_files_by_subject[subject].append({
#                             'filename': file.filename,
#                             'path': path,
#                             'experiment_name': experiment_name,
#                             'columns': columns,
#                             'column_types': column_types,
#                             'sample_data': sample_data,
#                             'row_count': len(df)
#                         })
                        
#                         print(f"  Parsed {len(columns)} valid columns, {len(df)} rows")
#                         file.seek(0)
                        
#                     except Exception as e:
#                         print(f"  ERROR parsing {file.filename}: {str(e)}")
#                         continue
        
#         print(f"=== PsychoPy scan complete: {len(psychopy_files_by_subject)} subject(s) with data ===\n")

#         # BATCH MODE: Multiple subjects
#         if len(detected_subjects) > 1:
#             print("\n=== BATCH MODE: Calculating intersection ===\n")
            
#             # Initialize per-subject data structures
#             subject_availability = {}
#             for subject in detected_subjects:
#                 subject_availability[subject] = {
#                     'metrics': set(),
#                     'event_markers': set(),
#                     'conditions': set()
#                 }
            
#             # Extract metrics from filenames organized by subject
#             exclude_tags = {'timesyncs', 'timesyncmap'}
#             for filename in emotibit_filenames:
#                 # Extract subject from filename path
#                 # Assuming format: root/subject_xxx/emotibit_data/file.csv
#                 parts = filename.split('/')
#                 if len(parts) >= 3:
#                     subject = parts[1]
#                     if subject in subject_availability:
#                         match = re.search(r'_emotibit_ground_truth_([A-Z0-9%]+)\.csv$', filename)
#                         if match:
#                             metric_tag = match.group(1)
#                             if metric_tag.lower() not in exclude_tags:
#                                 subject_availability[subject]['metrics'].add(metric_tag)
            
#             # Process event markers files (one per subject)
#             event_markers_files = request.files.getlist('event_markers_files')
#             event_markers_paths = request.form.getlist('event_markers_paths')
            
#             print(f"Processing {len(event_markers_files)} event markers files")
            
#             for em_file, em_path in zip(event_markers_files, event_markers_paths):
#                 parts = em_path.split('/')
#                 if len(parts) >= 2:
#                     subject = parts[1]
#                     print(f"  Processing event markers for subject: {subject}")
                    
#                     if subject in subject_availability:
#                         try:
#                             file_content = em_file.read()
#                             try:
#                                 content_str = file_content.decode('utf-8')
#                             except UnicodeDecodeError:
#                                 content_str = file_content.decode('latin-1')
                            
#                             df = pd.read_csv(io.StringIO(content_str))
                            
#                             if 'event_marker' in df.columns:
#                                 unique_markers = df['event_marker'].dropna().unique()
#                                 processed_markers = set()
#                                 for marker in unique_markers:
#                                     marker_str = str(marker)
#                                     if 'prs_' in marker_str.lower():
#                                         prs_match = re.search(r'(prs_\d+)', marker_str, re.IGNORECASE)
#                                         if prs_match:
#                                             processed_markers.add(prs_match.group(1).lower())
#                                         else:
#                                             processed_markers.add(marker_str)
#                                     else:
#                                         processed_markers.add(marker_str)
                                
#                                 subject_availability[subject]['event_markers'].update(processed_markers)
#                                 print(f"    Found {len(processed_markers)} event markers")
                            
#                             if 'condition' in df.columns:
#                                 unique_conditions = df['condition'].dropna().unique()
#                                 subject_availability[subject]['conditions'].update([str(c) for c in unique_conditions])
#                                 print(f"    Found {len(unique_conditions)} conditions")
                            
#                             em_file.seek(0)
#                         except Exception as e:
#                             print(f"    ERROR processing event markers for {subject}: {e}")
            
#             # Calculate intersection across all subjects
#             if len(subject_availability) > 0:
#                 subjects_list = list(subject_availability.keys())
                
#                 # Metrics intersection
#                 common_metrics = subject_availability[subjects_list[0]]['metrics'].copy()
#                 for subject in subjects_list[1:]:
#                     common_metrics &= subject_availability[subject]['metrics']
#                 metrics_list = sorted(list(common_metrics))
                
#                 # Event markers intersection
#                 common_markers = subject_availability[subjects_list[0]]['event_markers'].copy()
#                 for subject in subjects_list[1:]:
#                     common_markers &= subject_availability[subject]['event_markers']
#                 event_markers = sorted(list(common_markers))
                
#                 # Conditions intersection
#                 common_conditions = subject_availability[subjects_list[0]]['conditions'].copy()
#                 for subject in subjects_list[1:]:
#                     common_conditions &= subject_availability[subject]['conditions']
#                 conditions = sorted(list(common_conditions))
                
#                 print(f"\nIntersection results:")
#                 print(f"  Common metrics: {len(metrics_list)}")
#                 print(f"  Common event markers: {len(event_markers)}")
#                 print(f"  Common conditions: {len(conditions)}")
#             else:
#                 metrics_list = []
#                 event_markers = []
#                 conditions = []
            
#             subject_availability_json = {}
#             for subject, data in subject_availability.items():
#                 subject_availability_json[subject] = {
#                     'metrics': sorted(list(data['metrics'])),
#                     'event_markers': sorted(list(data['event_markers'])),
#                     'conditions': sorted(list(data['conditions']))
#                 }
            
#             return jsonify({
#                 'metrics': metrics_list,
#                 'metrics_count': len(metrics_list),
#                 'event_markers': event_markers,
#                 'event_markers_count': len(event_markers),
#                 'conditions': conditions,
#                 'conditions_count': len(conditions),
#                 'subjects': detected_subjects,
#                 'subjects_count': len(detected_subjects),
#                 'batch_mode': True,
#                 'subject_availability': subject_availability_json,
#                 'psychopy_data': {
#                     'has_files': len(psychopy_files_by_subject) > 0,
#                     'files_by_subject': psychopy_files_by_subject,
#                     'subjects_with_psychopy': list(psychopy_files_by_subject.keys())
#                 }
#             }), 200

#         # SINGLE SUBJECT MODE
#         else:
#             print("\n=== SINGLE SUBJECT MODE ===\n")
            
#             metrics = set()
#             exclude_tags = {'timesyncs', 'timesyncmap'}
            
#             for filename in emotibit_filenames:
#                 match = re.search(r'_emotibit_ground_truth_([A-Z0-9%]+)\.csv$', filename)
#                 if match:
#                     metric_tag = match.group(1)
#                     if metric_tag.lower() not in exclude_tags:
#                         metrics.add(metric_tag)
            
#             metrics_list = sorted(list(metrics))
#             print(f"Found {len(metrics_list)} metrics: {metrics_list}")
            
#             event_markers = []
#             conditions = []
#             if 'event_markers_file' in request.files:
#                 event_markers_file = request.files['event_markers_file']
#                 print(f"Processing event markers file: {event_markers_file.filename}")
                
#                 try:
#                     file_content = event_markers_file.read()
                    
#                     try:
#                         content_str = file_content.decode('utf-8')
#                     except UnicodeDecodeError:
#                         content_str = file_content.decode('latin-1')
                    
#                     df = pd.read_csv(io.StringIO(content_str))
                    
#                     print(f"Event markers CSV columns: {df.columns.tolist()}")
                    
#                     if 'event_marker' in df.columns:
#                         unique_markers = df['event_marker'].dropna().unique()
                        
#                         processed_markers = set()
#                         for marker in unique_markers:
#                             marker_str = str(marker)
                            
#                             if 'prs_' in marker_str.lower():
#                                 prs_match = re.search(r'(prs_\d+)', marker_str, re.IGNORECASE)
#                                 if prs_match:
#                                     normalized_prs = prs_match.group(1).lower()
#                                     processed_markers.add(normalized_prs)
#                                 else:
#                                     processed_markers.add(marker_str)
#                             else:
#                                 processed_markers.add(marker_str)
                        
#                         event_markers = sorted(list(processed_markers))
#                         print(f"Found {len(event_markers)} unique event markers: {event_markers}")
#                     else:
#                         print(f"WARNING: 'event_marker' column not found in CSV")
                    
#                     if 'condition' in df.columns:
#                         unique_conditions = df['condition'].dropna().unique()
#                         conditions = sorted([str(cond) for cond in unique_conditions])
#                         print(f"Found {len(conditions)} unique conditions: {conditions}")
#                     else:
#                         print(f"WARNING: 'condition' column not found in CSV")
                        
#                 except Exception as e:
#                     error_msg = f"Error reading event markers file: {str(e)}"
#                     print(error_msg)
#                     import traceback
#                     traceback.print_exc()
#             else:
#                 print("No event markers file provided")
            
#             return jsonify({
#                 'metrics': metrics_list,
#                 'metrics_count': len(metrics_list),
#                 'event_markers': event_markers,
#                 'event_markers_count': len(event_markers),
#                 'conditions': conditions,
#                 'conditions_count': len(conditions),
#                 'subjects': detected_subjects if detected_subjects else [],
#                 'subjects_count': len(detected_subjects) if detected_subjects else 0,
#                 'batch_mode': False,
#                 'psychopy_data': {
#                     'has_files': len(psychopy_files_by_subject) > 0,
#                     'files_by_subject': psychopy_files_by_subject,
#                     'subjects_with_psychopy': list(psychopy_files_by_subject.keys())
#                 }
#             }), 200
        
#     except Exception as e:
#         error_msg = f"Error scanning folder data: {str(e)}"
#         print(error_msg)
#         import traceback
#         traceback.print_exc()
#         return jsonify({'error': error_msg}), 500

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
            
            # ============================================================================
            # DEBUG: Print every file being processed
            # ============================================================================
            print(f"\n🔍 Processing file:")
            print(f"   Filename: {file.filename}")
            print(f"   Path: {path}")
            print(f"   Lowercase path: {path.lower()}")
            print(f"   Has 'psychopy_data': {'psychopy_data' in path.lower()}")
            print(f"   Ends with .csv: {file.filename.lower().endswith('.csv')}")
            
            filename_lower = file.filename.lower()
            
            # Extract subject from path (format: root/subject_xxx/...)
            path_parts = path.split('/')
            subject_name = path_parts[1] if len(path_parts) >= 3 else None
            print(f"   Extracted subject: {subject_name}")

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