# CSV Processing Dashboard Backend

This is the backend API for the CSV Processing Dashboard with intelligent group management and optimized storage for large datasets.

## Features

- **Large Dataset Support**: Handles datasets of any size with automatic storage optimization to prevent MongoDB BSON size limits
- **Chunked Processing**: Processes data efficiently in manageable chunks for memory optimization
- **Intelligent Grouping**: AI-powered product grouping based on core product types
- **Interactive Group Management**: Full CRUD operations for groups and sub-groups
- **Structured Plans**: Save and reuse grouping strategies across datasets
- **Storage Optimization**: Automatic document size optimization for MongoDB's 16MB BSON limit

## Quick Start

### Method 1: Using the startup script (Recommended)
```bash
cd backend
python start_server.py
```

### Method 2: Using uvicorn directly
```bash
cd backend
python -m venv venv
.\venv\Scripts\Activate 
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```

### Method 3: Using Python directly
```bash
cd backend
python server.py
```

## Common Issues and Solutions

### "Error loading ASGI app. Could not import module 'main'"
- **Problem**: Running `uvicorn main:app` instead of `uvicorn server:app`
- **Solution**: Use `uvicorn server:app` (the file is named `server.py`, not `main.py`)

### "BSON document too large" Error
- **Problem**: Large datasets (30,000+ rows) exceed MongoDB's 16MB BSON document limit
- **Solution**: The system automatically optimizes storage by:
  - Removing redundant `row_data` fields from items
  - Storing only essential item fields (id, name, price, category, quantity)
  - Limiting items per sub-group for preview (10-50 items)
  - Maintaining full count statistics for accurate reporting
  - This optimization is transparent to the frontend

### Large Dataset Processing
- The system automatically uses chunked processing for datasets with any number of rows
- Each chunk processes 1000 rows with 100-row samples for analysis
- Progress is logged in the console
- Storage is automatically optimized for large datasets to prevent BSON size limits

### Environment Variables
Make sure to set these environment variables:
```bash
MONGO_URL=your_mongodb_connection_string
DB_NAME=your_database_name
OPENAI_API_KEY=your_openai_api_key
CLOUDINARY_CLOUD_NAME=your_cloudinary_cloud_name
CLOUDINARY_API_KEY=your_cloudinary_api_key
CLOUDINARY_API_SECRET=your_cloudinary_api_secret
```

## API Endpoints

- `GET /` - Health check
- `POST /api/upload-csv` - Upload CSV file
- `POST /api/group-management/generate/{file_id}` - Generate intelligent groups
- `POST /api/group-management/update/{file_id}` - Update group management
- `GET /api/structured-plans` - Get all structured plans
- `POST /api/structured-plans/apply/{file_id}/{plan_id}` - Apply structured plan

## Documentation

Once the server is running, visit:
- API Documentation: http://localhost:8000/docs
- Interactive API: http://localhost:8000/redoc

## Dependencies

Install required packages:
```bash
pip install -r requirements.txt
```

## Storage Optimization for Large Datasets

For large datasets (like 30,000+ row files), the system automatically:

### 1. **Document Size Monitoring**
- Estimates BSON document size before MongoDB storage
- Compares against MongoDB's 16MB limit
- Triggers optimization when approaching limits

### 2. **Automatic Storage Optimization**
- Removes large `row_data` fields that can contain entire CSV row information
- Keeps only essential fields: `id`, `name`, `price`, `category`, `quantity`
- Limits items stored per sub-group (50 items initially, 10 if still too large)
- Stores full count statistics separately for accurate reporting

### 3. **Frontend Compatibility**
- Optimization is transparent to the frontend
- All group counts and statistics remain accurate
- UI shows correct total numbers even with optimized storage
- Group management operations work normally

### 4. **Processing Details**
1. **Processes in chunks**: 1000 rows at a time
2. **Samples from each chunk**: 100 representative items for analysis
3. **Analyzes patterns**: Extracts product types and common patterns
4. **Merges results**: Combines all chunk analyses intelligently
5. **Creates final groups**: Forms main groups and sub-groups based on global patterns
6. **Optimizes storage**: Reduces document size if needed before MongoDB storage

This approach ensures:
- Memory efficiency during processing
- MongoDB compatibility for any dataset size
- Processing stability and scalability
- Accurate grouping and statistics across the entire dataset
- Full frontend functionality regardless of dataset size

## Performance Characteristics

- **Small datasets** (< 1,000 rows): Full data storage, no optimization needed
- **Medium datasets** (1,000 - 10,000 rows): Selective optimization if approaching limits
- **Large datasets** (10,000+ rows): Automatic optimization with preview data
- **Very large datasets** (30,000+ rows): Aggressive optimization with statistical summaries 