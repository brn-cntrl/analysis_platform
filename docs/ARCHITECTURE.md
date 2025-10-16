# EmotiBit Data Analysis System - Architecture

## Overview

A full-stack web application for analyzing biometric data collected from EmotiBit devices. The system enables researchers to compare physiological responses across multiple experimental conditions using event markers and condition markers, with dynamic multi-group comparisons and time series visualizations.

## System Architecture
User Action → Frontend
↓
Select Folder → Parse File Structure
↓
Scan Folder Data → Extract Metrics/Markers/Conditions
↓
Configure Analysis:
- Select Biometric Metrics
- Add Comparison Groups:
- Label (user-defined name)
- Event Marker (e.g., "sart_1")
- Condition Marker (e.g., "physical_plants") [optional]
- Time Window (full duration or custom offset)
↓
Validate Configuration
↓
Send to Backend