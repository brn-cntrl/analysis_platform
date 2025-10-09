from flask import Flask, jsonify, request, send_from_directory, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import subprocess
import json

app = Flask(__name__, static_folder='frontend/build', static_url_path='')
CORS(app)

# Configure paths
UPLOAD_FOLDER = 'data'
OUTPUT_FOLDER = 'data/outputs'
NOTEBOOK_PATH = 'data_analysis.ipynb'
ALLOWED_EXTENSIONS = {'csv'}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/api/hello', methods=['GET'])
def hello():
    return jsonify({'message': 'Hello from Flask!'})

@app.route('/api/upload-and-analyze', methods=['POST'])
def upload_and_analyze():
    """Upload files and execute notebook analysis"""
    
    # Check if files are present
    if 'ground_truth' not in request.files or 'markers' not in request.files:
        return jsonify({'error': 'Both ground_truth and markers files are required'}), 400
    
    ground_truth_file = request.files['ground_truth']
    markers_file = request.files['markers']
    
    # Validate files
    if ground_truth_file.filename == '' or markers_file.filename == '':
        return jsonify({'error': 'No files selected'}), 400
    
    if not (allowed_file(ground_truth_file.filename) and allowed_file(markers_file.filename)):
        return jsonify({'error': 'Only CSV files are allowed'}), 400
    
    try:
        ground_truth_path = os.path.join(app.config['UPLOAD_FOLDER'], 'ground_truth.csv')
        markers_path = os.path.join(app.config['UPLOAD_FOLDER'], 'markers.csv')
        
        ground_truth_file.save(ground_truth_path)
        markers_file.save(markers_path)
        
        print(f"Files saved: {ground_truth_path}, {markers_path}")
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
            timeout=60  # 60 second timeout
        )
        
        if result.returncode != 0:
            error_msg = f"Notebook execution failed: {result.stderr}"
            print(error_msg)
            return jsonify({'error': error_msg}), 500
        
        print("Notebook executed successfully")
        
        # Read results from JSON file created by notebook
        results_path = os.path.join(OUTPUT_FOLDER, 'results.json')
        if os.path.exists(results_path):
            with open(results_path, 'r') as f:
                results = json.load(f)
            
            # Add image URLs
            for plot in results.get('plots', []):
                plot['url'] = f"/api/plot/{plot['filename']}"
            
            return jsonify({
                'message': 'Analysis completed successfully',
                'results': results
            }), 200
        else:
            return jsonify({'error': 'Results file not found'}), 500
        
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Notebook execution timed out'}), 500
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(error_msg)
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
            
            # Add image URLs
            for plot in results.get('plots', []):
                plot['url'] = f"/api/plot/{plot['filename']}"
            
            return jsonify(results), 200
        else:
            return jsonify({'error': 'No results available'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('api/save_images', methods=['POST'])
def save_images():
    """
    Saves all PNG images from the OUTPUT_FOLDER to a specified target folder.
    This route expects a JSON payload with an optional 'folder_name' key. It creates a target folder
    inside the 'data' directory using the provided folder name (or 'default_folder' if not specified).
    All PNG files in the OUTPUT_FOLDER are copied to the target folder.
    Returns:
        JSON response with a success message and HTTP 200 status code if images are saved successfully.
        If an error occurs, returns a JSON response with the error message and HTTP 500 status code.
    """
    global OUTPUT_FOLDER

    try:
        data = request.get_json()
        folder_name = data.get('folder_name', 'default_folder')
        target_folder = os.path.join('data', secure_filename(folder_name))
        os.makedirs(target_folder, exist_ok=True)
        
        for filename in os.listdir(OUTPUT_FOLDER):
            if filename.endswith('.png'):
                src_path = os.path.join(OUTPUT_FOLDER, filename)
                dst_path = os.path.join(target_folder, filename)
                with open(src_path, 'rb') as src_file:
                    with open(dst_path, 'wb') as dst_file:
                        dst_file.write(src_file.read())
        
        return jsonify({'message': f'Images saved to {target_folder}'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
# Serve React App
@app.route('/')
def serve():
    return send_from_directory(app.static_folder, 'index.html')

@app.errorhandler(404)
def not_found(e):
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(debug=True, port=5001)