# CSV Reader Application

A web application for uploading, processing, analyzing, and visualizing CSV data.

## Project Structure

- **frontend/**: React application for the user interface
- **backend/**: FastAPI server for data processing and analysis
- **cache/**: Temporary storage for processing data
- **exports/**: Directory for saving charts and analysis results

## Key Features

- Upload and process CSV files
- AI-powered data analysis
- Interactive data visualization
- Chat interface for asking questions about your data

## Getting Started

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm start
```

The application will be accessible at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

## Using the Cache Directory

The `cache/` directory is used for temporary storage during processing:
- Files here are managed by the application
- Can be safely deleted when the application is not running

## Using the Exports Directory

The `exports/` directory contains saved outputs from your analysis:
- `exports/charts/`: Generated visualizations from data analysis
- Charts are saved with a timestamp and can be accessed through the UI 