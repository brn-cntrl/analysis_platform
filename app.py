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
        'student_id': student_id,  
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
    print("UPLOAD AND ANALYZE REQUEST")
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
    print(f"Has External Data: {request.form.get('has_external_data', 'false')}")
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

    # Data cleaning parameters
    cleaning_enabled = json.loads(request.form.get('cleaning_enabled', 'false'))
    cleaning_stages = json.loads(request.form.get('cleaning_stages', '{}'))

    selected_subjects = []
    if batch_mode:
        selected_subjects = json.loads(request.form.get('selected_subjects', '[]'))
   
    # Parse external file data
    has_external_data = request.form.get('has_external_data', 'false') == 'true'
    external_configs = {}
    if has_external_data:
        external_configs_json = request.form.get('external_configs', '{}')
        try:
            external_configs = json.loads(external_configs_json)
            
            # Count selected vs total files
            total_files = 0
            selected_files = 0
            for subject, files_config in external_configs.items():
                for filename, config in files_config.items():
                    total_files += 1
                    if config.get('selected', True):  # Default to True if not specified
                        selected_files += 1
            
            print(f"Parsed external data configs for {len(external_configs)} subjects")
            print(f"Total external files: {total_files}")
            print(f"Selected for analysis: {selected_files}")
            
            # Filter to only selected files
            filtered_configs = {}
            for subject, files_config in external_configs.items():
                filtered_configs[subject] = {
                    filename: config 
                    for filename, config in files_config.items() 
                    if config.get('selected', True)
                }
            
            # Only include subjects that have at least one selected file
            external_configs = {
                subject: files 
                for subject, files in filtered_configs.items() 
                if len(files) > 0
            }
            
            print(f"Subjects with selected files: {len(external_configs)}")
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse external data configs: {e}")
            external_configs = {}

    # Parse respiratory data configs
    has_respiratory_data = request.form.get('has_respiratory_data', 'false') == 'true'
    respiratory_configs = {}
    if has_respiratory_data:
        respiratory_configs_json = request.form.get('respiratory_configs', '{}')
        try:
            respiratory_configs = json.loads(respiratory_configs_json)
            
            selected_count = sum(1 for config in respiratory_configs.values() if config.get('selected', True))
            print(f"✓ Parsed respiratory data configs for {len(respiratory_configs)} subjects")
            print(f"  Selected for analysis: {selected_count} subjects")
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse respiratory data configs: {e}")
            respiratory_configs = {}

    # Parse cardiac data configs
    has_cardiac_data = request.form.get('has_cardiac_data', 'false') == 'true'
    cardiac_configs = {}
    if has_cardiac_data:
        cardiac_configs_json = request.form.get('cardiac_configs', '{}')
        try:
            cardiac_configs = json.loads(cardiac_configs_json)
            
            selected_count = sum(1 for config in cardiac_configs.values() if config.get('selected', True))
            print(f"✓ Parsed cardiac data configs for {len(cardiac_configs)} subjects")
            print(f"  Selected for analysis: {selected_count} subjects")
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse cardiac data configs: {e}")
            cardiac_configs = {}

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

    comparison_groups = []
    for idx, event_config in enumerate(selected_events):
        event_marker = event_config.get('event', '')
        condition_marker = event_config.get('condition', 'all')
        
        if not event_marker or event_marker == '':
            continue
        
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
        file_manifest = {
            'emotibit_files': [],
            'cardiac_files': [],
            'respiration_files': [],
            'event_markers': None,  # Single subject backward compatibility
            'event_markers_by_subject': {},  # Multi-subject support
            'external_files': [],  
            'external_configs': {},
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
                    'subject': subject_name  
                })
            elif any(folder in path.lower() for folder in ['respiratory_data', 'respiration_data', 'vernier_data']):
                file_manifest['respiration_files'].append({
                    'filename': file.filename,
                    'path': file_path,
                    'relative_path': relative_path,
                    'subject': subject_name
                })
            elif any(folder in path.lower() for folder in ['cardiac_data', 'polar_data']):
                file_manifest['cardiac_files'].append({
                    'filename': file.filename,
                    'path': file_path,
                    'relative_path': relative_path,
                    'subject': subject_name
                })
            elif filename_lower.endswith('_event_markers.csv'):
                if batch_mode and subject_name:
                    file_manifest['event_markers_by_subject'][subject_name] = {
                        'filename': file.filename,
                        'path': file_path,
                        'relative_path': relative_path
                    }
                    print(f"Event markers for {subject_name}: {file.filename}")
                else:
                    # Single subject - backward compatibility
                    file_manifest['event_markers'] = {
                        'filename': file.filename,
                        'path': file_path,
                        'relative_path': relative_path
                    }
            elif 'external_data' in path.lower() and filename_lower.endswith('.csv'):
                print(f"CLASSIFIED AS EXTERNAL DATA FILE")
                file_manifest['external_files'].append({
                    'filename': file.filename,
                    'path': file_path,
                    'relative_path': relative_path,
                    'subject': subject_name
                })
                print(f"External data file for {subject_name}: {file.filename}")
            else:
                # ============================================================================
                # DEBUG: Catch unclassified files
                # ============================================================================
                print(f"UNCLASSIFIED - adding to other_files")
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
        
        if has_external_data and external_configs:
            file_manifest['external_configs'] = external_configs
            print(f"Added external data file configs to manifest")

        manifest_path = os.path.join(upload_folder, 'file_manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump(file_manifest, f, indent=2)
        
        print(f"Files organized in: {upload_folder}")
        print(f"Event markers file: {file_manifest['event_markers']}")

        # ============================================================================
        # VALIDATION: Check analysis method and plot type compatibility
        # ============================================================================
        incompatible_combinations = {
            'mean': ['lineplot', 'scatter', 'boxplot', 'poincare'],  # Mean is single value
            'rmssd': ['poincare'],  # RMSSD transforms data, incompatible with n vs n+1 Poincaré
            'moving_average': ['poincare']  # Smoothed data disrupts Poincaré interpretation
        }
        
        if analysis_method in incompatible_combinations:
            if plot_type in incompatible_combinations[analysis_method]:
                all_plots = ['lineplot', 'boxplot', 'scatter', 'poincare']
                valid_plots = [p for p in all_plots if p not in incompatible_combinations[analysis_method]]
                suggestions = ', '.join(valid_plots)
                
                error_msg = (f"Incompatible combination: '{plot_type}' plot cannot be used with '{analysis_method}' analysis. "
                           f"Valid plot types for {analysis_method}: {suggestions}")
                print(f"VALIDATION ERROR: {error_msg}")
                return jsonify({'error': error_msg}), 400
        
        # ============================================================================
        # DEBUG: Print manifest summary
        # ============================================================================
        print("\nMANIFEST SUMMARY:")
        print(f"EmotiBit files: {len(file_manifest['emotibit_files'])}")
        print(f"External files: {len(file_manifest.get('external_files', []))}")
        if batch_mode:
            print(f"Event markers (by subject): {len(file_manifest.get('event_markers_by_subject', {}))}")
            for subj, em_file in file_manifest.get('event_markers_by_subject', {}).items():
                print(f"    - {subj}: {em_file['filename']}")
        else:
            em = file_manifest.get('event_markers')
            print(f"Event markers: {em['filename'] if em else 'None'}")
        print()
        
        print("Running analysis...")

        analysis_type = request.form.get('analysis_type', 'inter')

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
            external_configs=external_configs,
            respiratory_configs=respiratory_configs,
            cardiac_configs=cardiac_configs,
            analysis_type=analysis_type,
            cleaning_enabled=cleaning_enabled,
            cleaning_stages=cleaning_stages
        )
        
        print("Analysis completed successfully")
        
        for plot in results.get('plots', []):
            plot['url'] = f"/api/plot/{plot['filename']}"
        
        results['file_manifest'] = file_manifest
        
        # Clean NaN values from results before JSON serialization
        def clean_nan(obj):
            """Recursively replace NaN with None for JSON serialization"""
            if isinstance(obj, dict):
                return {k: clean_nan(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_nan(item) for item in obj]
            elif isinstance(obj, float):
                if np.isnan(obj) or np.isinf(obj):
                    return 0.0  
                return obj
            else:
                return obj
        
        results = clean_nan(results)
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
    and handles external data paths (no files uploaded).
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

        external_metadata_json = request.form.get('external_metadata')
        external_files_by_subject = {}

        if external_metadata_json:
            external_files_by_subject = json.loads(external_metadata_json)
            print(f"DEBUG: Received external file metadata for {len(external_files_by_subject)} subject(s)")
            
            for subject, files in external_files_by_subject.items():
                print(f"  Subject {subject}: {len(files)} file(s)")
                for file_data in files:
                    print(f"    - {file_data['filename']}: {len(file_data.get('columns', []))} columns")

        # --- Process respiratory data files ---
        # --- Process respiratory data files ---
        respiratory_filenames_json = request.form.get('respiratory_filenames')
        respiratory_files_by_subject = {}
        
        if respiratory_filenames_json:
            respiratory_filenames = json.loads(respiratory_filenames_json)
            print(f"Processing {len(respiratory_filenames)} respiratory file(s)")
            
            for filepath in respiratory_filenames:
                parts = filepath.split('/')
                # Expected format: root_folder/subject_name/respiratory_data/filename.csv
                if len(parts) >= 3:
                    subject = parts[1]
                    file_name = parts[-1]
                    
                    if subject not in respiratory_files_by_subject:
                        respiratory_files_by_subject[subject] = []
                    
                    respiratory_files_by_subject[subject].append({
                        'filename': file_name,
                        'path': filepath
                    })
            
            if respiratory_files_by_subject:
                print(f"Found respiratory data for {len(respiratory_files_by_subject)} subject(s)")
                for subject, files in respiratory_files_by_subject.items():
                    print(f"  Subject {subject}: {len(files)} respiratory file(s)")

        # --- Process cardiac data files ---
        cardiac_filenames_json = request.form.get('cardiac_filenames')
        cardiac_files_by_subject = {}
        
        if cardiac_filenames_json:
            cardiac_filenames = json.loads(cardiac_filenames_json)
            print(f"Processing {len(cardiac_filenames)} cardiac file(s)")
            
            for filepath in cardiac_filenames:
                parts = filepath.split('/')
                # Expected format: root_folder/subject_name/cardiac_data/filename.csv
                if len(parts) >= 3:
                    subject = parts[1]
                    file_name = parts[-1]
                    
                    if subject not in cardiac_files_by_subject:
                        cardiac_files_by_subject[subject] = []
                    
                    cardiac_files_by_subject[subject].append({
                        'filename': file_name,
                        'path': filepath
                    })
            
            if cardiac_files_by_subject:
                print(f"Found cardiac data for {len(cardiac_files_by_subject)} subject(s)")
                for subject, files in cardiac_files_by_subject.items():
                    print(f"  Subject {subject}: {len(files)} cardiac file(s)")

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
                            match = re.search(r'_([A-Z]{2,4})\.csv$', filename)
                        
                        if match:
                            tag = match.group(1)
                            if tag.lower() not in exclude_tags:
                                subject_availability[subject]['metrics'].add(tag)

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
            'external_data': {
                'has_files': len(external_files_by_subject) > 0,
                'files_by_subject': external_files_by_subject,
                'subjects_with_external': list(external_files_by_subject.keys())
            },
            'respiratory_data': {
                'has_files': len(respiratory_files_by_subject) > 0,
                'files_by_subject': respiratory_files_by_subject,
                'subjects_with_respiratory': list(respiratory_files_by_subject.keys())
            },
            'cardiac_data': {
                'has_files': len(cardiac_files_by_subject) > 0,
                'files_by_subject': cardiac_files_by_subject,
                'subjects_with_cardiac': list(cardiac_files_by_subject.keys())
            }
        }), 200
    
    except Exception as e:
        print(f"Error scanning folder data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

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
            print(f"   Has 'external_data': {'external_data' in path.lower()}")
            print(f"   Ends with .csv: {file.filename.lower().endswith('.csv')}")
            
            filename_lower = file.filename.lower()
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