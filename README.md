# Data Analysis Platform Quickstart

A web-based platform for analyzing EmotiBit biometric data with interactive visualizations. Upload CSV files, execute server-side analyses with python libraries, and view results with matplotlib plots directly in your browser.

## Features

- **File Upload Interface** - Browse and upload CSV files for ground truth data and event markers
- **Real-Time Analysis** - View statistics, data tables, and matplotlib plots instantly
- **Interactive React UI** - Responsive interface with no page refreshes
- **Data Visualization** - Automatically generated time-series plots, histograms, and moving averages
- **RESTful API** - Modular Flask endpoints for easy extension

## Prerequisites

- Python 3.8+
- Node.js 14+
- npm or yarn

## Expected File Names and Paths
- Event marker file names should be appended with "_event_markers.csv" and placed in the root of the subject's data folder.
- EmotiBit ground truth files are expected to be parsed and all resulting csv files should be appended "_TAGNAME.csv" (e.g. "_HR.csv") and be found in subject_data/emotibit_data
- Respiration csv file names should be appended "respiratory_data_FILE#.csv" (e.g. "respiratory_data_0.csv) and be found in subject_data/respiratory_data
- External data files (e.g. those collected in PsychoPy) should be placed in the subject's "external_data" folder, found at the same level as emotibit_data and respiratory_data folders.

### Paths
- Emotibit data: subject_data/<experiment_name>/<trial_name>/<subject_id>/emotibit_data/
- Respiratory data (vernier belt): subject_data/<experiment_name>/<trial_name>/<subject_id>/respiratory_data/
- Respiratory/Cardiac data (Polar H10): subject_data/<experiment_name>/<trial_name>/<subject_id>/cardiac_data/
- External Data (e.g. PsychoPy): subject_data/<experiment_name>/<trial_name>/<subject_id>/external_data/

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/analysis_platform.git
cd analysis_platform
```

### 2. Install the requirements in requirements.txt
```bash
pip install -r requirements.txt
```

### 3. Install requirements for React
```bash
cd frontend
npm install
cd ..
```

### 4. Run the backend server
```bash
python app.py
```

### 5. Run the frontend server
```bash
cd frontend
npm start
```