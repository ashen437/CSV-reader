from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
import pandas as pd
import numpy as np
import pymongo
from pymongo import MongoClient
import gridfs
import io
import os
import json
import uuid
import re
import pathlib
import bson
import traceback
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import openai
from dotenv import load_dotenv
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import base64
from io import BytesIO

# Import our custom grouping logic
from grouping_logic import (
    ProductGroupingEngine, 
    generate_ai_powered_sub_groups_with_config,
    generate_main_groups_from_unique_values
)

# Load environment variables
load_dotenv()

app = FastAPI(title="CSV Processing Dashboard")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler to prevent server crashes
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle any unhandled exceptions to prevent server crashes"""
    print(f"Global exception handler caught: {type(exc).__name__}: {str(exc)}")
    import traceback
    print(f"Traceback: {traceback.format_exc()}")
    
    # Return a proper error response instead of crashing
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

# Database connection
MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client (updated for new API)
from openai import OpenAI
openai_client = OpenAI(api_key=OPENAI_API_KEY)

def ensure_json_serializable(obj):
    """Recursively convert numpy types to Python types for JSON serialization"""
    if isinstance(obj, dict):
        return {key: ensure_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [ensure_json_serializable(item) for item in obj]
    elif hasattr(obj, 'item'):  # numpy types
        return obj.item()
    elif isinstance(obj, (pd.Int64Dtype, pd.Float64Dtype)) or str(type(obj)).startswith('numpy'):
        return obj.item() if hasattr(obj, 'item') else int(obj)
    else:
        return obj

# MongoDB connection
client = MongoClient(MONGO_URL)
db = client[DB_NAME]
fs = gridfs.GridFS(db)

# Collections
files_collection = db.files_metadata
groups_collection = db.analysis_groups
group_management_collection = db.group_management
final_results_collection = db.final_results
saved_groups_collection = db.saved_groups

# Initialize grouping engine
grouping_engine = ProductGroupingEngine(OPENAI_API_KEY)

def create_fallback_groups(df: pd.DataFrame) -> Dict[str, Any]:
    """Create simple fallback groups when main algorithm fails"""
    try:
        # Simple grouping by first column patterns
        items = []
        for index, row in df.head(500).iterrows():  # Limit to first 500 rows for fallback
            item = {
                "id": str(index),
                "name": str(row.iloc[0]) if len(row) > 0 else f"Item_{index}",
                "price": float(row.iloc[1]) if len(row) > 1 and pd.notnull(row.iloc[1]) else 0.0,
                "category": str(row.iloc[2]) if len(row) > 2 else "Unknown",
                "quantity": int(row.iloc[3]) if len(row) > 3 and pd.notnull(row.iloc[3]) else 1,
                "row_data": row.to_dict()
            }
            items.append(item)
        
        # Simple keyword-based grouping
        groups = {
            "electronics": [],
            "furniture": [],
            "food": [],
            "clothing": [],
            "other": []
        }
        
        keywords = {
            "electronics": ["phone", "laptop", "computer", "tablet", "mouse", "keyboard"],
            "furniture": ["chair", "table", "desk", "sofa", "bed"],
            "food": ["rice", "flour", "sugar", "bread", "milk"],
            "clothing": ["shirt", "pants", "shoes", "jacket"]
        }
        
        ungrouped_items = []
        
        for item in items:
            item_name = item["name"].lower()
            assigned = False
            
            for group_name, group_keywords in keywords.items():
                if any(keyword in item_name for keyword in group_keywords):
                    groups[group_name].append(item)
                    assigned = True
                    break
            
            if not assigned:
                ungrouped_items.append(item)
        
        # Convert to main groups format
        main_groups = {}
        for group_name, group_items in groups.items():
            if group_items:  # Only create groups with items
                group_id = str(uuid.uuid4())
                main_groups[group_id] = {
                    "id": group_id,
                    "name": group_name.title(),
                    "enabled": True,
                    "sub_groups": {
                        "default": {
                            "id": str(uuid.uuid4()),
                            "name": "Default",
                            "items": group_items
                        }
                    },
                    "total_items": len(group_items),
                    "estimated_savings": f"{min(20, len(group_items) * 2)}%"
                }
        
        return {
            "main_groups": main_groups,
            "ungrouped_items": ungrouped_items,
            "metadata": {
                "total_items": len(items),
                "total_groups": len(main_groups),
                "grouping_method": "fallback_simple",
                "created_at": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        # Ultimate fallback - return basic structure
        return {
            "main_groups": {
                str(uuid.uuid4()): {
                    "id": str(uuid.uuid4()),
                    "name": "All Items",
                    "enabled": True,
                    "sub_groups": {
                        "default": {
                            "id": str(uuid.uuid4()),
                            "name": "Default",
                            "items": [{"id": "1", "name": "Sample Item", "price": 0.0, "category": "Unknown", "quantity": 1}]
                        }
                    },
                    "total_items": 1,
                    "estimated_savings": "5%"
                }
            },
            "ungrouped_items": [],
            "metadata": {
                "total_items": 1,
                "total_groups": 1,
                "grouping_method": "emergency_fallback",
                "created_at": datetime.now().isoformat()
            }
        }

def convert_groups_to_legacy_format(groups_data):
    """
    Convert new array-based groups structure to legacy dictionary-based structure.
    
    New format: {groups: [...], ungrouped_items: [...]}
    Legacy format: {main_groups: {...}, ungrouped_items: [...]}
    """
    if not groups_data or 'groups' not in groups_data:
        return groups_data
    
    legacy_data = {
        'main_groups': {},
        'ungrouped_items': groups_data.get('ungrouped_items', []),
        'validation': groups_data.get('validation', {}),
        'total_items': groups_data.get('total_items', 0),
        'grouped_items': groups_data.get('grouped_items', 0),
        'ungrouped_count': groups_data.get('ungrouped_count', 0),
        'total_groups': groups_data.get('total_groups', 0),
        'total_sub_groups': groups_data.get('total_sub_groups', 0),
        'estimated_time_saved': groups_data.get('estimated_time_saved', '0 minutes'),
        'is_valid': groups_data.get('is_valid', True)
    }
    
    # Convert each group from array to dictionary
    for group in groups_data.get('groups', []):
        group_id = group.get('id', str(uuid.uuid4()))
        
        # Convert sub_groups from array to dictionary
        sub_groups_dict = {}
        for sub_group in group.get('sub_groups', []):
            sub_group_id = sub_group.get('id', str(uuid.uuid4()))
            sub_groups_dict[sub_group_id] = {
                'id': sub_group_id,
                'name': sub_group.get('name', 'Unnamed Sub Group'),
                'items': sub_group.get('items', []),
                'count': sub_group.get('count', len(sub_group.get('items', []))),
                'is_ungrouped_subgroup': sub_group.get('is_ungrouped_subgroup', False)
            }
        
        # Add group to main_groups dictionary
        legacy_data['main_groups'][group_id] = {
            'id': group_id,
            'name': group.get('name', 'Unnamed Group'),
            'enabled': group.get('enabled', True),
            'type': group.get('type', 'main'),
            'sub_groups': sub_groups_dict,
            'total_items': group.get('count', group.get('item_count', 0)),
            'estimated_savings': group.get('estimated_savings', '0%'),
            'count': group.get('count', group.get('item_count', 0)),
            'item_count': group.get('count', group.get('item_count', 0))
        }
    
    return legacy_data

def convert_legacy_to_groups_format(legacy_data):
    """
    Convert legacy dictionary-based structure back to new array-based structure.
    
    Legacy format: {main_groups: {...}, ungrouped_items: [...]}
    New format: {groups: [...], ungrouped_items: [...]}
    """
    print(f"[DEBUG] convert_legacy_to_groups_format called")
    
    if not legacy_data:
        print(f"[DEBUG] No legacy_data provided")
        return legacy_data
        
    if 'main_groups' not in legacy_data:
        print(f"[DEBUG] No main_groups in legacy_data, returning as-is")
        return legacy_data
    
    print(f"[DEBUG] Legacy data keys: {list(legacy_data.keys())}")
    print(f"[DEBUG] Validation in legacy: {legacy_data.get('validation', 'Missing')}")

    groups_data = {
        'groups': [],
        'ungrouped_items': legacy_data.get('ungrouped_items', []),
        'validation': legacy_data.get('validation', {}),
        'total_items': legacy_data.get('total_items', 0),
        'grouped_items': legacy_data.get('grouped_items', 0),
        'ungrouped_count': legacy_data.get('ungrouped_count', 0),
        'total_groups': legacy_data.get('total_groups', 0),
        'total_sub_groups': legacy_data.get('total_sub_groups', 0),
        'estimated_time_saved': legacy_data.get('estimated_time_saved', '0 minutes'),
        'is_valid': legacy_data.get('is_valid', True)
    }
    
    # If validation is empty, try to recalculate it before conversion
    validation = groups_data['validation']
    if not validation or not validation.get('counts'):
        print(f"[DEBUG] Validation data is empty, recalculating from legacy data first...")
        legacy_data_copy = recalculate_validation_data(legacy_data.copy())
        groups_data['validation'] = legacy_data_copy.get('validation', {})
        groups_data['total_items'] = legacy_data_copy.get('total_items', 0)
        groups_data['grouped_items'] = legacy_data_copy.get('grouped_items', 0)
        groups_data['ungrouped_count'] = legacy_data_copy.get('ungrouped_count', 0)
        groups_data['total_groups'] = legacy_data_copy.get('total_groups', 0)
        groups_data['total_sub_groups'] = legacy_data_copy.get('total_sub_groups', 0)
        print(f"[DEBUG] Recalculated validation: {groups_data['validation']}")
    
    # Convert each group from dictionary to array
    for group_id, group in legacy_data.get('main_groups', {}).items():
        # Convert sub_groups from dictionary to array
        sub_groups_array = []
        for sub_group_id, sub_group in group.get('sub_groups', {}).items():
            sub_groups_array.append({
                'id': sub_group_id,
                'name': sub_group.get('name', 'Unnamed Sub Group'),
                'items': sub_group.get('items', []),
                'count': sub_group.get('count', len(sub_group.get('items', []))),
                'is_ungrouped_subgroup': sub_group.get('is_ungrouped_subgroup', False)
            })
        
        # Add group to groups array
        groups_data['groups'].append({
            'id': group_id,
            'name': group.get('name', 'Unnamed Group'),
            'enabled': group.get('enabled', True),
            'type': group.get('type', 'main'),
            'items': group.get('items', []),  # Add direct items if any
            'sub_groups': sub_groups_array,
            'count': group.get('count', group.get('item_count', 0)),
            'item_count': group.get('count', group.get('item_count', 0)),
            'estimated_savings': group.get('estimated_savings', '0%')
        })
    
    print(f"[DEBUG] Converted {len(groups_data['groups'])} groups")
    print(f"[DEBUG] Final validation data: {groups_data['validation']}")
    
    return groups_data

def recalculate_validation_data(groups_data):
    """Recalculate validation data if it's missing or empty"""
    print(f"[DEBUG] recalculate_validation_data called with data type: {type(groups_data)}")
    
    if not groups_data:
        print(f"[DEBUG] No groups_data provided")
        return groups_data
    
    print(f"[DEBUG] Groups_data keys: {list(groups_data.keys()) if isinstance(groups_data, dict) else 'Not a dict'}")
    
    # If we have the new format (groups array), calculate from that
    if 'groups' in groups_data:
        groups = groups_data.get('groups', [])
        ungrouped_items = groups_data.get('ungrouped_items', [])
        
        print(f"[DEBUG] New format detected - {len(groups)} groups, {len(ungrouped_items)} ungrouped items")
        
        total_grouped = 0
        total_sub_groups = 0
        
        for i, group in enumerate(groups):
            # Count items in this group
            group_items = len(group.get('items', []))
            sub_groups = group.get('sub_groups', [])
            
            print(f"[DEBUG] Group {i}: {group_items} direct items, {len(sub_groups)} sub-groups")
            
            total_sub_groups += len(sub_groups)
            
            # Count items in sub-groups
            for j, sub_group in enumerate(sub_groups):
                sub_group_items = len(sub_group.get('items', []))
                group_items += sub_group_items
                print(f"[DEBUG]   Sub-group {j}: {sub_group_items} items")
            
            total_grouped += group_items
        
        print(f"[DEBUG] Calculated - total_grouped: {total_grouped}, total_sub_groups: {total_sub_groups}")
        
        # Update validation data
        validation_data = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'counts': {
                'total_rows': total_grouped + len(ungrouped_items),
                'grouped_records': total_grouped,
                'ungrouped_records': len(ungrouped_items),
                'main_groups': len(groups),
                'total_sub_groups': total_sub_groups
            }
        }
        
        groups_data['validation'] = validation_data
        groups_data['total_items'] = total_grouped + len(ungrouped_items)
        groups_data['grouped_items'] = total_grouped
        groups_data['ungrouped_count'] = len(ungrouped_items)
        groups_data['total_groups'] = len(groups)
        groups_data['total_sub_groups'] = total_sub_groups
        
        print(f"[DEBUG] New format validation completed: {validation_data['counts']}")
    
    # If we have the legacy format (main_groups dict), calculate from that
    elif 'main_groups' in groups_data:
        main_groups = groups_data.get('main_groups', {})
        ungrouped_items = groups_data.get('ungrouped_items', [])
        
        print(f"[DEBUG] Legacy format detected - {len(main_groups)} main groups, {len(ungrouped_items)} ungrouped items")
        
        total_grouped = 0
        total_sub_groups = 0
        
        for group_id, group in main_groups.items():
            # Count items in this group
            group_items = 0
            sub_groups = group.get('sub_groups', {})
            
            print(f"[DEBUG] Main group {group_id}: {len(sub_groups)} sub-groups")
            
            total_sub_groups += len(sub_groups)
            
            # Count items in sub-groups
            for sub_group_id, sub_group in sub_groups.items():
                sub_group_items = len(sub_group.get('items', []))
                group_items += sub_group_items
                print(f"[DEBUG]   Sub-group {sub_group_id}: {sub_group_items} items")
            
            total_grouped += group_items
        
        print(f"[DEBUG] Calculated - total_grouped: {total_grouped}, total_sub_groups: {total_sub_groups}")
        
        # Update validation data
        validation_data = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'counts': {
                'total_rows': total_grouped + len(ungrouped_items),
                'grouped_records': total_grouped,
                'ungrouped_records': len(ungrouped_items),
                'main_groups': len(main_groups),
                'total_sub_groups': total_sub_groups
            }
        }
        
        groups_data['validation'] = validation_data
        groups_data['total_items'] = total_grouped + len(ungrouped_items)
        groups_data['grouped_items'] = total_grouped
        groups_data['ungrouped_count'] = len(ungrouped_items)
        groups_data['total_groups'] = len(main_groups)
        groups_data['total_sub_groups'] = total_sub_groups
        
        print(f"[DEBUG] Legacy format validation completed: {validation_data['counts']}")
    
    else:
        print(f"[DEBUG] Unknown data format - no 'groups' or 'main_groups' key found")
        # Create minimal validation data
        groups_data['validation'] = {
            'is_valid': False,
            'errors': ['Unknown data format'],
            'warnings': [],
            'counts': {
                'total_rows': 0,
                'grouped_records': 0,
                'ungrouped_records': 0,
                'main_groups': 0,
                'total_sub_groups': 0
            }
        }
    
    return groups_data

# Pydantic models
class FileMetadata(BaseModel):
    file_id: str
    filename: str
    upload_date: datetime
    file_size: int
    status: str  # "uploaded", "processing", "completed", "error"
    total_rows: Optional[int] = None
    columns: Optional[List[str]] = None

class GroupData(BaseModel):
    group_name: str
    item_ids: List[str]
    bulk_metric: str
    estimated_savings_potential: str
    procurement_notes: str
    subgroups: Optional[Dict[str, List[str]]] = None

class AnalysisResult(BaseModel):
    file_id: str
    groups: List[GroupData]
    summary: Dict[str, Any]
    created_at: datetime

class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    chart_data: Optional[str] = None
    chart_type: Optional[str] = None

class SubGroupData(BaseModel):
    id: str
    name: str
    items: List[Dict[str, Any]]

class MainGroupData(BaseModel):
    id: str
    name: str
    enabled: bool
    sub_groups: Dict[str, SubGroupData]
    total_items: int
    estimated_savings: str

class GroupManagementData(BaseModel):
    main_groups: Dict[str, MainGroupData]
    ungrouped_items: List[Dict[str, Any]]
    metadata: Dict[str, Any]

class StructuredPlanData(BaseModel):
    id: str
    name: str
    created_at: str
    version: str
    grouping_rules: List[Dict[str, Any]]
    main_groups: Dict[str, Any]
    metadata: Dict[str, Any]

class GroupUpdateRequest(BaseModel):
    action: str  # "add_group", "delete_group", "update_group", "move_item", "toggle_group", "remove_from_sub_group"
    group_id: Optional[str] = None
    sub_group_id: Optional[str] = None
    item_id: Optional[str] = None
    target_group_id: Optional[str] = None  # Can be "ungrouped", "main_group_ungrouped", or group_id
    target_sub_group_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

class FinalResultsData(BaseModel):
    file_id: str
    main_groups: List[Dict[str, Any]]
    total_items: int
    total_groups: int
    created_at: str
    estimated_total_savings: str

class SavedGroupData(BaseModel):
    name: str
    description: str
    structured_results: Dict[str, Any]
    file_id: str
    created_at: str

@app.get("/")
async def root():
    return {"message": "CSV Processing Dashboard API"}

@app.get("/api/health")
async def health_check():
    """Simple health check endpoint for frontend"""
    return {"status": "healthy", "message": "Backend server is running"}

@app.get("/api/debug/test-grouping")
async def test_grouping():
    """Test endpoint to debug grouping issues"""
    try:
        # Create a small test dataframe
        test_data = {
            'Name': ['Apple iPhone', 'Samsung Phone', 'Office Chair', 'Desk Lamp', 'Rice 1kg'],
            'Price': [999, 899, 299, 49, 5],
            'Category': ['Electronics', 'Electronics', 'Furniture', 'Furniture', 'Food']
        }
        test_df = pd.DataFrame(test_data)
        
        print("Testing grouping with sample data...")
        groups_data = grouping_engine.generate_intelligent_groups(test_df)
        
        return {
            "status": "success",
            "test_data_rows": len(test_df),
            "groups_created": len(groups_data.get("main_groups", {})),
            "ungrouped_items": len(groups_data.get("ungrouped_items", [])),
            "sample_data": test_data
        }
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@app.post("/api/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    """Upload a CSV file and store it in GridFS"""
    try:
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are allowed")
        
        # Read file content
        content = await file.read()
        
        # Create unique file ID
        file_id = str(uuid.uuid4())
        
        # Store file in GridFS
        fs.put(content, filename=file.filename, _id=file_id)
        
        # Try to detect the encoding and parse CSV with error handling
        try:
            # First attempt: Try using pandas with default UTF-8
            df = pd.read_csv(io.BytesIO(content))
        except UnicodeDecodeError:
            try:
                # Second attempt: Try with latin-1 (very permissive encoding)
                df = pd.read_csv(io.BytesIO(content), encoding='latin-1')
            except Exception:
                try:
                    # Third attempt: Use chardet to detect encoding
                    import chardet
                    detected = chardet.detect(content)
                    encoding = detected['encoding']
                    df = pd.read_csv(io.BytesIO(content), encoding=encoding)
                except Exception as e:
                    # Last resort: Try with errors='replace'
                    df = pd.read_csv(io.BytesIO(content), encoding='utf-8', errors='replace')
        
        # For large files, limit preview data stored in metadata
        max_preview_rows = min(1000, len(df))
        preview_columns = df.columns.tolist()
        
        # Analyze column data types with robust detection
        def detect_column_type(series):
            """Detect the data type of a pandas Series"""
            # Remove null values for analysis
            non_null_series = series.dropna()
            if len(non_null_series) == 0:
                return 'text'
            
            # Sample a subset for performance on large datasets
            sample_size = min(1000, len(non_null_series))
            sample = non_null_series.head(sample_size)
            
            # Convert sample to string first to handle mixed types
            sample_strings = [str(x).strip() for x in sample if pd.notna(x)]
            
            # Count how many values match each type
            integer_count = 0
            float_count = 0
            
            for val_str in sample_strings:
                if val_str == '':
                    continue
                    
                # Check for integer first
                try:
                    # Try to parse as integer directly
                    int(val_str)
                    integer_count += 1
                    continue
                except ValueError:
                    pass
                
                # Check for float (including integers that can be expressed as floats)
                try:
                    float_val = float(val_str)
                    # Check if it's actually an integer value in float form (like "42.0")
                    if float_val.is_integer() and ('.' in val_str or 'e' in val_str.lower()):
                        integer_count += 1
                    else:
                        float_count += 1
                except ValueError:
                    pass
            
            total_values = len(sample_strings)
            if total_values == 0:
                return 'text'
            
            # If more than 70% are integers, classify as integer
            if integer_count / total_values > 0.7:
                return 'integer'
            
            # If more than 60% are numeric (int or float), classify as decimal
            if (integer_count + float_count) / total_values > 0.6:
                return 'decimal'
            
            # Check for dates (only if not numeric)
            try:
                pd.to_datetime(sample, errors='raise')
                return 'date'
            except (ValueError, TypeError):
                pass
            
            # Check for booleans
            unique_values = set(val_str.lower() for val_str in sample_strings)
            boolean_values = {'true', 'false', '1', '0', 'yes', 'no', 'y', 'n'}
            if unique_values.issubset(boolean_values) and len(unique_values) <= 4:
                return 'boolean'
            
            # Default to text
            return 'text'
        
        # Create column metadata with types
        columns_metadata = []
        for col in df.columns:
            col_type = detect_column_type(df[col])
            
            # Get some sample values for reference (first 3 non-null values)
            sample_values = df[col].dropna().head(3).tolist()
            
            # Convert numpy types to Python native types for MongoDB compatibility
            sample_values_clean = []
            for val in sample_values:
                if pd.isna(val):
                    continue
                # Convert numpy types to Python native types
                if hasattr(val, 'item'):  # numpy scalar
                    sample_values_clean.append(val.item())
                elif isinstance(val, (np.integer, np.floating)):
                    sample_values_clean.append(val.item())
                elif isinstance(val, np.bool_):
                    sample_values_clean.append(bool(val))
                else:
                    sample_values_clean.append(str(val))
            
            # Get null count and total count as Python int (not numpy.int64)
            null_count = int(df[col].isnull().sum())
            total_count = int(len(df[col]))
            
            columns_metadata.append({
                'name': str(col),  # Ensure column name is string
                'type': col_type,
                'sample_values': sample_values_clean,
                'null_count': null_count,
                'total_count': total_count
            })
        
        # Store metadata with enhanced column information
        metadata = {
            "file_id": file_id,
            "filename": file.filename,
            "upload_date": datetime.now(),
            "file_size": len(content),
            "status": "uploaded",
            "total_rows": int(len(df)),  # Convert to Python int
            "columns": preview_columns,  # Keep for backward compatibility
            "columns_metadata": columns_metadata  # New detailed column information
        }
        
        files_collection.insert_one(metadata)
        
        return {
            "file_id": file_id,
            "filename": file.filename,
            "status": "uploaded",
            "total_rows": int(len(df)),  # Convert to Python int
            "columns": preview_columns,
            "columns_metadata": columns_metadata
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")

@app.get("/api/files")
async def get_files():
    """Get list of all uploaded files"""
    try:
        files = list(files_collection.find({}, {"_id": 0}))
        # Convert datetime to ISO string for JSON serialization
        for file in files:
            if 'upload_date' in file:
                file['upload_date'] = file['upload_date'].isoformat()
        return files
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching files: {str(e)}")

@app.post("/api/analyze/{file_id}")
async def analyze_csv(file_id: str):
    """Analyze CSV file using OpenAI for bulk procurement grouping"""
    try:
        # Update status to processing
        files_collection.update_one(
            {"file_id": file_id},
            {"$set": {"status": "processing"}}
        )
        
        # Retrieve file from GridFS
        file_data = fs.get(file_id)
        content = file_data.read()
        
        # Try to detect the encoding and parse CSV with error handling
        try:
            # First attempt: Try using pandas with default UTF-8
            df = pd.read_csv(io.BytesIO(content))
        except UnicodeDecodeError:
            try:
                # Second attempt: Try with latin-1 (very permissive encoding)
                df = pd.read_csv(io.BytesIO(content), encoding='latin-1')
            except Exception:
                try:
                    # Third attempt: Use chardet to detect encoding
                    import chardet
                    detected = chardet.detect(content)
                    encoding = detected['encoding']
                    df = pd.read_csv(io.BytesIO(content), encoding=encoding)
                except Exception as e:
                    # Last resort: Try with errors='replace'
                    df = pd.read_csv(io.BytesIO(content), encoding='utf-8', errors='replace')
        
        # For large datasets, consider using a sample
        if len(df) > 50000:
            sample_size = min(50000, int(len(df) * 0.1))  # 10% or 50k max
            df_sample = df.sample(n=sample_size, random_state=42)
        else:
            df_sample = df
        
        # Prepare data for OpenAI
        items_data = []
        for index, row in df_sample.iterrows():
            try:
                item = {
                    "id": str(index),
                    "name": str(row.iloc[0]) if len(row) > 0 else "",
                    "price": str(row.iloc[1]) if len(row) > 1 else "0",
                    "category": str(row.iloc[2]) if len(row) > 2 else "Unknown",
                    "quantity": str(row.iloc[3]) if len(row) > 3 else "1"
                }
                items_data.append(item)
            except Exception:
                # Skip problematic rows
                continue
        
        # Limit items to first 50 for the API call
        api_items = items_data[:50]
        
        # Prepare OpenAI prompt
        prompt = f"""
As a procurement optimization expert, analyze the following inventory items and create intelligent bulk purchasing groups.

RULES:
1. Group items by core product type, ignoring brands and minor variations
2. Focus on products that can realistically be purchased together from similar suppliers
3. Consider storage and handling requirements
4. Aim for 20-60% cost savings through bulk purchasing
5. Create meaningful subgroups for large categories

ITEMS TO ANALYZE:
{json.dumps(api_items)}

REQUIRED OUTPUT FORMAT (JSON only):
{{
  "groups": [
    {{
      "group_name": "Product Type Name",
      "item_ids": ["0", "1", "2"],
      "bulk_metric": "kg|units|liters|boxes",
      "estimated_savings_potential": "15-25%",
      "procurement_notes": "Notes about procurement considerations",
      "subgroups": {{
        "variant_1": ["0", "1"],
        "variant_2": ["2"]
      }}
    }}
  ],
  "summary": {{
    "total_items_processed": {len(api_items)},
    "total_groups_created": 1,
    "items_grouped": {len(api_items) - 1},
    "items_ungrouped": 1,
    "estimated_total_savings": "$5,000"
  }}
}}

Focus on practical bulk purchasing opportunities that procurement teams can actually implement.
"""
        
        # Call OpenAI API
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a procurement optimization expert. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.3
        )
        
        # Parse OpenAI response
        analysis_text = response.choices[0].message.content
        
        # Clean and parse JSON response
        try:
            # Remove any markdown formatting
            if "```json" in analysis_text:
                analysis_text = analysis_text.split("```json")[1].split("```")[0]
            elif "```" in analysis_text:
                analysis_text = analysis_text.split("```")[1].split("```")[0]
            
            analysis_result = json.loads(analysis_text.strip())
        except json.JSONDecodeError:
            # Fallback: create basic grouping
            analysis_result = {
                "groups": [{
                    "group_name": "General Items",
                    "item_ids": [str(i) for i in range(min(len(api_items), 10))],
                    "bulk_metric": "units",
                    "estimated_savings_potential": "15-20%",
                    "procurement_notes": "Basic grouping applied due to analysis complexity"
                }],
                "summary": {
                    "total_items_processed": len(api_items),
                    "total_groups_created": 1,
                    "items_grouped": min(len(api_items), 10),
                    "items_ungrouped": max(0, len(api_items) - 10),
                    "estimated_total_savings": "$1,000"
                }
            }
        
        # Store analysis results
        analysis_doc = {
            "file_id": file_id,
            "groups": analysis_result.get("groups", []),
            "summary": analysis_result.get("summary", {}),
            "created_at": datetime.now(),
            "original_data": items_data
        }
        
        groups_collection.insert_one(analysis_doc)
        
        # Update file status
        files_collection.update_one(
            {"file_id": file_id},
            {"$set": {"status": "completed"}}
        )
        
        return {
            "file_id": file_id,
            "status": "completed",
            "groups": analysis_result.get("groups", []),
            "summary": analysis_result.get("summary", {})
        }
        
    except Exception as e:
        # Update status to error
        files_collection.update_one(
            {"file_id": file_id},
            {"$set": {"status": "error"}}
        )
        raise HTTPException(status_code=500, detail=f"Error analyzing file: {str(e)}")

@app.get("/api/analysis/{file_id}")
async def get_analysis(file_id: str):
    """Get analysis results for a specific file"""
    try:
        analysis = groups_collection.find_one({"file_id": file_id}, {"_id": 0})
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        # Convert datetime to ISO string
        if 'created_at' in analysis:
            analysis['created_at'] = analysis['created_at'].isoformat()
            
        return analysis
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching analysis: {str(e)}")

@app.get("/api/file-preview/{file_id}")
async def get_file_preview(file_id: str, rows: int = 10):
    """Get preview of CSV file data"""
    try:
        # Retrieve file from GridFS
        file_data = fs.get(file_id)
        content = file_data.read()
        
        # Try to detect the encoding and parse CSV with error handling
        try:
            # First attempt: Try using pandas with default UTF-8
            df = pd.read_csv(io.BytesIO(content))
        except UnicodeDecodeError:
            try:
                # Second attempt: Try with latin-1 (very permissive encoding)
                df = pd.read_csv(io.BytesIO(content), encoding='latin-1')
            except Exception:
                try:
                    # Third attempt: Use chardet to detect encoding
                    import chardet
                    detected = chardet.detect(content)
                    encoding = detected['encoding']
                    df = pd.read_csv(io.BytesIO(content), encoding=encoding)
                except Exception as e:
                    # Last resort: Try with errors='replace'
                    df = pd.read_csv(io.BytesIO(content), encoding='utf-8', errors='replace')
        
        # Cap preview to requested rows
        preview_rows = min(rows, len(df))
        
        # Handle NaN values for JSON compatibility
        preview_df = df.head(preview_rows)
        preview_df = preview_df.fillna("")  # Replace NaN with empty string
        preview_data = preview_df.to_dict('records')
        
        return {
            "columns": df.columns.tolist(),
            "data": preview_data,
            "total_rows": len(df)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting file preview: {str(e)}")

@app.delete("/api/files/{file_id}")
async def delete_file(file_id: str):
    """Delete a file and its analysis"""
    try:
        # Delete from GridFS
        fs.delete(file_id)
        
        # Delete metadata
        files_collection.delete_one({"file_id": file_id})
        
        # Delete analysis
        groups_collection.delete_one({"file_id": file_id})
        
        return {"message": "File deleted successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")

@app.get("/api/file-columns/{file_id}")
async def get_file_columns(file_id: str):
    """Get available columns for a specific file"""
    try:
        # Retrieve file from GridFS
        file_data = fs.get(file_id)
        content = file_data.read()
        
        # Try to detect the encoding and parse CSV with error handling
        try:
            # First attempt: Try using pandas with default UTF-8
            df = pd.read_csv(BytesIO(content), encoding='utf-8')
        except UnicodeDecodeError:
            # Second attempt: Try with 'latin-1' encoding
            try:
                df = pd.read_csv(BytesIO(content), encoding='latin-1')
            except Exception:
                # Third attempt: Try with 'cp1252' encoding
                df = pd.read_csv(BytesIO(content), encoding='cp1252')
        
        columns = df.columns.tolist()
        sample_data = {}
        
        # Get sample values for each column (first non-null value)
        for col in columns:
            non_null_values = df[col].dropna()
            if len(non_null_values) > 0:
                sample_data[col] = str(non_null_values.iloc[0])
            else:
                sample_data[col] = "N/A"
        
        return {
            "columns": columns,
            "sample_data": sample_data,
            "total_columns": len(columns)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting file columns: {str(e)}")

# ================== GROUP MANAGEMENT ENDPOINTS ==================

@app.post("/api/group-management/generate/{file_id}")
async def generate_intelligent_groups(file_id: str):
    """Generate intelligent groups using default AI settings"""
    """Generate intelligent groups for a CSV file using AI and similarity analysis"""
    try:
        # Retrieve file from GridFS
        file_data = fs.get(file_id)
        content = file_data.read()
        
        # Parse CSV
        try:
            df = pd.read_csv(io.BytesIO(content))
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(io.BytesIO(content), encoding='latin-1')
            except Exception:
                try:
                    import chardet
                    detected = chardet.detect(content)
                    encoding = detected['encoding']
                    df = pd.read_csv(io.BytesIO(content), encoding=encoding)
                except Exception as e:
                    df = pd.read_csv(io.BytesIO(content), encoding='utf-8', errors='replace')
        
        # Generate intelligent groups with chunked processing for large datasets
        print(f"Starting group generation for {len(df)} rows...")
        try:
            groups_data = grouping_engine.generate_intelligent_groups(df)
            print(f"Group generation completed successfully")
        except Exception as e:
            print(f"Error in group generation: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Fallback to simple grouping
            print("Attempting fallback grouping...")
            try:
                groups_data = create_fallback_groups(df)
                print("Fallback grouping successful")
            except Exception as fallback_error:
                print(f"Fallback grouping also failed: {str(fallback_error)}")
                raise HTTPException(status_code=500, detail=f"Group generation failed: {str(e)}")
        
        # Note: generate_intelligent_groups already returns legacy format (main_groups)
        # So we store it as is, but convert to new format for frontend response
        
        # Store in database (groups_data is already in legacy format)
        group_doc = {
            "file_id": file_id,
            "groups_data": groups_data,
            "created_at": datetime.now(),
            "type": "intelligent_groups"
        }
        
        result = group_management_collection.insert_one(group_doc)
        
        # Auto-save final results when intelligent grouping is complete
        try:
            structured_results = generate_structured_final_results(groups_data)
            final_results_doc = {
                "file_id": file_id,
                "structured_results": structured_results,
                "original_groups_data": groups_data,
                "created_at": datetime.now(),
                "version": "1.0",
                "auto_generated": True
            }
            
            # Save or update final results
            existing_results = final_results_collection.find_one({"file_id": file_id})
            if existing_results:
                final_results_collection.replace_one(
                    {"file_id": file_id},
                    final_results_doc
                )
            else:
                final_results_collection.insert_one(final_results_doc)
            
            print(f"Auto-saved final results for file {file_id}")
        except Exception as auto_save_error:
            print(f"Failed to auto-save final results: {str(auto_save_error)}")
            # Don't fail the main operation if auto-save fails
        
        # Convert to new format for frontend response
        new_format_data = convert_legacy_to_groups_format(groups_data)
        new_format_data["management_id"] = str(result.inserted_id)
        return new_format_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating intelligent groups: {str(e)}")

def optimize_group_data_for_storage(groups_data, max_items_per_group=100):
    """
    Optimize group data for MongoDB storage by limiting the amount of data stored per group.
    For large datasets, store only summary data and essential items to avoid BSON size limits.
    """
    optimized_data = {
        'main_groups': {},
        'ungrouped_items': [],
        'validation': groups_data.get('validation', {}),
        'storage_optimized': True,  # Flag to indicate this is optimized storage
        'full_data_available': False  # Flag to indicate if full data can be reconstructed
    }
    
    # Process main groups
    for group_id, group_info in groups_data.get('main_groups', {}).items():
        optimized_group = {
            'id': group_info.get('id'),
            'name': group_info.get('name'),
            'enabled': group_info.get('enabled', True),
            'sub_groups': {},
            'total_items': group_info.get('total_items', 0),
            'estimated_savings': group_info.get('estimated_savings', '0%')
        }
        
        # Process sub-groups
        for sg_id, sg_info in group_info.get('sub_groups', {}).items():
            items = sg_info.get('items', [])
            total_items = len(items)
            
            # Store only essential data and limit items to prevent BSON size issues
            optimized_items = []
            if total_items > 0:
                # For small datasets, store first few items for preview
                # For large datasets, store only summary statistics
                if total_items <= max_items_per_group:
                    optimized_items = items[:max_items_per_group]
                else:
                    # Store only a sample for preview, include summary stats
                    sample_items = items[:10]  # First 10 items for preview
                    for item in sample_items:
                        # Keep only essential fields, remove large row_data
                        optimized_item = {
                            'id': item.get('id'),
                            'name': item.get('name', ''),
                            'price': item.get('price', 0),
                            'category': item.get('category', ''),
                            'quantity': item.get('quantity', 1)
                            # Note: removing 'row_data' to save space
                        }
                        optimized_items.append(optimized_item)
            
            optimized_group['sub_groups'][sg_id] = {
                'id': sg_info.get('id'),
                'name': sg_info.get('name'),
                'items': optimized_items,
                'total_items_count': total_items,  # Store actual count
                'is_truncated': total_items > max_items_per_group,
                'is_ungrouped_subgroup': sg_info.get('is_ungrouped_subgroup', False)
            }
        
        optimized_data['main_groups'][group_id] = optimized_group
    
    # Optimize ungrouped items similarly
    ungrouped = groups_data.get('ungrouped_items', [])
    if len(ungrouped) <= max_items_per_group:
        optimized_data['ungrouped_items'] = ungrouped
    else:
        # Store only a sample of ungrouped items
        optimized_data['ungrouped_items'] = ungrouped[:10]
        optimized_data['ungrouped_items_count'] = len(ungrouped)
        optimized_data['ungrouped_items_truncated'] = True
    
    return optimized_data

def get_document_size_estimate(data):
    """
    Estimate the BSON document size to prevent MongoDB size limit errors.
    Returns size estimate in bytes.
    """
    try:
        return len(bson.encode(data))
    except Exception:
        # Fallback: rough estimation based on string representation
        import sys
        return sys.getsizeof(str(data))

@app.post("/api/group-management/generate-configured/{file_id}")
async def generate_configured_groups(file_id: str, config: dict):
    """Generate groups based on user configuration - uses unique values approach for main groups"""
    try:
        print(f"\n=== Generate Configured Groups for file: {file_id} ===")
        print(f"Configuration: {config}")
        
        # Retrieve file from GridFS
        file_data = fs.get(file_id)
        content = file_data.read()
        
        # Parse CSV with encoding handling
        try:
            df = pd.read_csv(io.BytesIO(content))
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(io.BytesIO(content), encoding='latin-1')
            except Exception:
                try:
                    import chardet
                    detected = chardet.detect(content)
                    encoding = detected['encoding']
                    df = pd.read_csv(io.BytesIO(content), encoding=encoding)
                except Exception as e:
                    df = pd.read_csv(io.BytesIO(content), encoding='utf-8', errors='replace')
        
        if df is None or df.empty:
            raise HTTPException(status_code=400, detail="Could not load data from file")
        
        print(f"Loaded {len(df)} records from file")
        print(f"Available columns: {list(df.columns)}")
        
        # Extract configuration
        use_main_groups = config.get('use_main_groups', True)
        main_group_column = config.get('main_group_column')
        sub_group_column = config.get('sub_group_column')
        
        print(f"Configuration: use_main_groups={use_main_groups}, main_column={main_group_column}, sub_column={sub_group_column}")
        
        # Validate columns exist
        if use_main_groups and main_group_column:
            if main_group_column not in df.columns:
                raise HTTPException(status_code=400, detail=f"Main group column '{main_group_column}' not found in dataset")
        
        if sub_group_column and sub_group_column not in df.columns:
            raise HTTPException(status_code=400, detail=f"Sub group column '{sub_group_column}' not found in dataset")
        
        # FIXED: Use unique values approach for main groups + AI sub-grouping
        if use_main_groups and main_group_column:
            if sub_group_column:
                # Use AI-powered sub-grouping when both main and sub columns are specified
                print(f"🧠 Using AI-POWERED SUB-GROUPING approach")
                print(f"   Main group column: {main_group_column}")
                print(f"   Sub group column: {sub_group_column}")
                
                try:
                    result = generate_ai_powered_sub_groups_with_config(df, main_group_column, sub_group_column)
                    
                    if result:
                        print(f"✅ Generated {len(result.get('groups', []))} main groups with AI-powered sub-groups")
                        print(f"📊 Total sub-groups: {result.get('total_sub_groups', 0)}")
                    else:
                        raise Exception("AI sub-grouping returned None")
                        
                except Exception as ai_error:
                    print(f"⚠️ AI-powered sub-grouping failed: {str(ai_error)}")
                    print(f"🔄 Falling back to unique values main groups only...")
                    
                    # Fallback to simple unique values approach for main groups
                    result = generate_main_groups_from_unique_values(df, main_group_column)
                    
                    if not result:
                        raise HTTPException(status_code=500, detail="Both AI sub-grouping and fallback methods failed")
                    
                    print(f"✅ Fallback successful: Generated {len(result.get('groups', []))} main groups")
                
            else:
                # Use simple unique values method for main groups only
                print(f"🎯 Using UNIQUE VALUES approach for main group column: {main_group_column}")
                
                result = generate_main_groups_from_unique_values(df, main_group_column)
                
                if not result:
                    raise HTTPException(status_code=500, detail="Failed to generate groups from unique values")
                
                print(f"✅ Generated {len(result.get('groups', []))} main groups from unique values")
            
            print(f"📊 Total records processed: {len(df)}")
            print(f"📊 Grouped records: {result.get('grouped_items', 0)}")
            print(f"📊 Ungrouped records: {result.get('ungrouped_count', 0)}")
            
        elif sub_group_column:
            # Use AI sub-grouping without main groups
            print(f"🤖 Using AI-POWERED SUB-GROUPING without main groups")
            print(f"   Sub group column: {sub_group_column}")
            
            try:
                result = generate_ai_powered_sub_groups_with_config(df, None, sub_group_column)
                
                if result:
                    print(f"✅ Generated AI-powered sub-groups without main groups")
                    print(f"📊 Total sub-groups: {result.get('total_sub_groups', 0)}")
                else:
                    raise Exception("AI sub-grouping returned None")
                    
            except Exception as ai_error:
                print(f"⚠️ AI-powered sub-grouping failed: {str(ai_error)}")
                print(f"🔄 Cannot fallback for sub-grouping without main groups")
                raise HTTPException(status_code=500, detail=f"AI sub-grouping failed and no fallback available for sub-grouping only mode. Error: {str(ai_error)}")
            
        else:
            # Fallback to AI method for other cases
            print(f"🤖 Using AI-powered grouping method")
            group_generator = ProductGroupingEngine(OPENAI_API_KEY)
            result = group_generator.generate_ai_powered_groups_from_columns(
                df, 
                main_group_column=main_group_column if use_main_groups else None, 
                sub_group_column=sub_group_column
            )
            
            if not result:
                # Fallback to the old method if AI fails
                print("AI-powered grouping failed, falling back to standard method...")
                result = group_generator.generate_groups_with_config(
                    df, 
                    use_main_groups=use_main_groups,
                    main_group_column=main_group_column, 
                    sub_group_column=sub_group_column
                )
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to generate groups")
        
        # Ensure validation data is properly calculated
        validation_data = result.get('validation', {})
        if not validation_data or not validation_data.get('counts'):
            print("⚠️ Validation data missing, recalculating...")
            # Use the grouping engine's recalculation method
            group_generator = ProductGroupingEngine(OPENAI_API_KEY)
            result = group_generator.recalculate_validation_data(result)
            validation_data = result.get('validation', {})
        
        print(f"📈 Final validation counts: {validation_data.get('counts', {})}")
        
        # Convert to legacy format for storage
        groups_legacy_data = convert_groups_to_legacy_format(result)
        groups_legacy = groups_legacy_data.get('main_groups', {})
        ungrouped_legacy = result.get('ungrouped_items', [])
        
        # Double-check validation data one more time
        combined_data = {
            'main_groups': groups_legacy,
            'ungrouped_items': ungrouped_legacy,
            'validation': validation_data
        }
        combined_data = recalculate_validation_data(combined_data)
        final_validation = combined_data.get('validation', {})
        
        print(f"🔍 Final validation after storage conversion: {final_validation.get('counts', {})}")
        
        # Check document size before storing
        storage_data = {
            'main_groups': groups_legacy,
            'ungrouped_items': ungrouped_legacy,
            'validation': final_validation,
            'total_items': len(df),
            'grouped_items': final_validation['counts']['grouped_records'],
            'ungrouped_count': final_validation['counts']['ungrouped_records'],
            'total_groups': final_validation['counts']['main_groups'],
            'total_sub_groups': final_validation['counts']['total_sub_groups'],
            'is_valid': final_validation['is_valid']
        }
        
        estimated_size = get_document_size_estimate(storage_data)
        max_bson_size = 16 * 1024 * 1024 - 1024  # 16MB minus 1KB buffer
        
        print(f"💾 Estimated document size: {estimated_size:,} bytes ({estimated_size/1024/1024:.2f} MB)")
        
        # If document is too large, optimize for storage
        if estimated_size > max_bson_size:
            print(f"⚠️  Document too large ({estimated_size:,} bytes), optimizing for storage...")
            storage_data = optimize_group_data_for_storage(storage_data, max_items_per_group=50)
            optimized_size = get_document_size_estimate(storage_data)
            print(f"✅ Optimized document size: {optimized_size:,} bytes ({optimized_size/1024/1024:.2f} MB)")
        
        # Store in database
        group_doc = {
            "file_id": file_id,
            "groups_data": storage_data,
            "created_at": datetime.now(),
            "type": "configured_groups_unique_values" if (use_main_groups and main_group_column) else "ai_powered_configured_groups",
            "configuration": {
                "use_main_groups": use_main_groups,
                "main_group_column": main_group_column,
                "sub_group_column": sub_group_column
            },
            "processing_config": {
                'use_main_groups': use_main_groups,
                'main_group_column': main_group_column,
                'sub_group_column': sub_group_column,
                'total_records_processed': len(df),
                'processing_method': 'unique_values_main_groups' if (use_main_groups and main_group_column) else 'ai_powered_column_analysis'
            }
        }
        
        # Replace existing document
        group_management_collection.replace_one(
            {"file_id": file_id},
            group_doc,
            upsert=True
        )
        
        # Convert back to new format for response to frontend
        converted_groups_data = convert_legacy_to_groups_format(storage_data)
        
        response_data = {
            'groups': converted_groups_data.get('groups', []),
            'ungrouped_items': ungrouped_legacy,
            'validation': final_validation,
            'total_items': len(df),
            'grouped_items': final_validation['counts']['grouped_records'],
            'ungrouped_count': final_validation['counts']['ungrouped_records'],
            'total_groups': final_validation['counts']['main_groups'],
            'total_sub_groups': final_validation['counts']['total_sub_groups'],
            'is_valid': final_validation['is_valid'],
            'management_id': file_id,
            'processing_config': {
                'use_main_groups': use_main_groups,
                'main_group_column': main_group_column,
                'sub_group_column': sub_group_column,
                'total_records_processed': len(df),
                'processing_method': 'unique_values_main_groups' if (use_main_groups and main_group_column) else 'ai_powered_column_analysis'
            },
            'storage_optimized': storage_data.get('storage_optimized', False)
        }
        
        print(f"🎉 SUCCESS: Generated {final_validation['counts']['main_groups']} main groups")
        print(f"📊 Total records: {len(df)} | Grouped: {final_validation['counts']['grouped_records']} | Ungrouped: {final_validation['counts']['ungrouped_records']}")
        
        # Ensure all data is JSON serializable
        response_data = ensure_json_serializable(response_data)
        
        return response_data
        
    except Exception as e:
        print(f"❌ ERROR in generate_configured_groups: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating configured groups: {str(e)}")

@app.get("/api/group-management/{file_id}")
async def get_group_management_data(file_id: str):
    """Get group management data for a file"""
    try:
        group_doc = group_management_collection.find_one(
            {"file_id": file_id},
            {"_id": 0}
        )
        
        if not group_doc:
            raise HTTPException(status_code=404, detail="Group management data not found")
        
        print(f"[DEBUG] Raw group_doc keys: {list(group_doc.keys())}")
        print(f"[DEBUG] Groups_data type: {type(group_doc.get('groups_data'))}")
        
        # Convert datetime to ISO string
        if 'created_at' in group_doc:
            group_doc['created_at'] = group_doc['created_at'].isoformat()
        
        # Process groups_data
        if 'groups_data' in group_doc:
            original_data = group_doc['groups_data']
            print(f"[DEBUG] Original groups_data keys: {list(original_data.keys()) if isinstance(original_data, dict) else 'Not a dict'}")
            
            # Check validation data status
            validation = original_data.get('validation', {})
            counts = validation.get('counts', {})
            print(f"[DEBUG] Validation data: {validation}")
            print(f"[DEBUG] Counts data: {counts}")
            
            # Check if validation data is missing, empty, or has zero values
            needs_recalculation = (
                not validation or 
                not counts or 
                counts.get('total_rows', 0) == 0 or
                counts.get('main_groups', 0) == 0
            )
            
            if needs_recalculation:
                print(f"[DEBUG] Validation data needs recalculation...")
                
                # Use the grouping engine's recalculation method
                try:
                    updated_data = grouping_engine.recalculate_validation_data(original_data)
                    print(f"[DEBUG] Recalculation successful using grouping engine")
                    original_data = updated_data
                except Exception as recalc_error:
                    print(f"[DEBUG] Grouping engine recalculation failed: {recalc_error}, trying server recalculation...")
                    # Fallback to server's recalculation method
                    original_data = recalculate_validation_data(original_data)
                
                print(f"[DEBUG] After recalculation - validation: {original_data.get('validation', {})}")
                
                # Update the database with the corrected data
                try:
                    # Convert to legacy format for storage
                    legacy_data = convert_groups_to_legacy_format(original_data)
                    
                    group_management_collection.update_one(
                        {"file_id": file_id},
                        {"$set": {"groups_data": legacy_data}}
                    )
                    print(f"[DEBUG] Updated database with corrected validation data")
                except Exception as update_error:
                    print(f"[DEBUG] Failed to update database: {update_error}")
            
            # Convert legacy format back to new format for frontend
            converted_data = convert_legacy_to_groups_format(original_data)
            print(f"[DEBUG] After conversion - groups count: {len(converted_data.get('groups', []))}")
            print(f"[DEBUG] Final validation counts: {converted_data.get('validation', {}).get('counts', {})}")
            group_doc['groups_data'] = converted_data
            
        return group_doc
        
    except Exception as e:
        print(f"[ERROR] get_group_management_data: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error fetching group management data: {str(e)}")

@app.post("/api/group-management/update/{file_id}")
async def update_group_management(file_id: str, update_request: GroupUpdateRequest):
    """Update group management data based on user actions"""
    try:
        # Get current group data
        group_doc = group_management_collection.find_one({"file_id": file_id})
        if not group_doc:
            raise HTTPException(status_code=404, detail="Group management data not found")
        
        groups_data = group_doc["groups_data"]
        action = update_request.action
        
        if action == "add_main_group":
            # Add new main group
            group_id = str(uuid.uuid4())
            group_name = update_request.data.get("name", f"New Group {len(groups_data['main_groups']) + 1}")
            groups_data["main_groups"][group_id] = {
                "id": group_id,
                "name": group_name,
                "enabled": True,
                "sub_groups": {
                    "default": {
                        "id": str(uuid.uuid4()),
                        "name": "Default",
                        "items": []
                    }
                },
                "total_items": 0,
                "estimated_savings": "0%"
            }
        
        elif action == "delete_main_group":
            # Delete main group and move items to ungrouped
            if update_request.group_id in groups_data["main_groups"]:
                group_data = groups_data["main_groups"][update_request.group_id]
                # Move all items to ungrouped
                for sub_group in group_data["sub_groups"].values():
                    groups_data["ungrouped_items"].extend(sub_group["items"])
                # Delete the group
                del groups_data["main_groups"][update_request.group_id]
        
        elif action == "add_sub_group":
            # Add new sub group
            if update_request.group_id in groups_data["main_groups"]:
                sub_group_id = str(uuid.uuid4())
                sub_group_name = update_request.data.get("name", f"Sub Group {len(groups_data['main_groups'][update_request.group_id]['sub_groups']) + 1}")
                groups_data["main_groups"][update_request.group_id]["sub_groups"][sub_group_id] = {
                    "id": sub_group_id,
                    "name": sub_group_name,
                    "items": []
                }
        
        elif action == "delete_sub_group":
            # Delete sub group and move items based on type
            if (update_request.group_id in groups_data["main_groups"] and 
                update_request.sub_group_id in groups_data["main_groups"][update_request.group_id]["sub_groups"]):
                
                sub_group_data = groups_data["main_groups"][update_request.group_id]["sub_groups"][update_request.sub_group_id]
                sub_group_items = sub_group_data["items"]
                
                # If it's the special "Ungrouped Items" sub-group, move items to main ungrouped
                if sub_group_data.get("is_ungrouped_subgroup", False):
                    groups_data["ungrouped_items"].extend(sub_group_items)
                else:
                    # For regular sub-groups, move items to main group's ungrouped sub-group
                    # First, find or create the "Ungrouped Items" sub-group for this main group
                    main_group = groups_data["main_groups"][update_request.group_id]
                    ungrouped_sub_group = None
                    
                    # Find existing ungrouped sub-group
                    for sg_id, sg_data in main_group["sub_groups"].items():
                        if sg_data.get("is_ungrouped_subgroup", False):
                            ungrouped_sub_group = sg_data
                            break
                    
                    # Create ungrouped sub-group if it doesn't exist
                    if not ungrouped_sub_group:
                        ungrouped_sg_id = str(uuid.uuid4())
                        ungrouped_sub_group = {
                            "id": ungrouped_sg_id,
                            "name": "Ungrouped Items",
                            "items": [],
                            "is_ungrouped_subgroup": True
                        }
                        main_group["sub_groups"][ungrouped_sg_id] = ungrouped_sub_group
                    
                    # Move items to ungrouped sub-group
                    ungrouped_sub_group["items"].extend(sub_group_items)
                
                # Delete the sub-group
                del groups_data["main_groups"][update_request.group_id]["sub_groups"][update_request.sub_group_id]
        
        elif action == "move_item":
            # Move item between groups/ungrouped
            item_to_move = None
            source_group_id = None
            
            # Find and remove item from source
            if update_request.group_id == "ungrouped":
                for i, item in enumerate(groups_data["ungrouped_items"]):
                    if item["id"] == update_request.item_id:
                        item_to_move = groups_data["ungrouped_items"].pop(i)
                        break
            else:
                # Find in main groups
                for group_id, group_data in groups_data["main_groups"].items():
                    for sub_group_id, sub_group_data in group_data["sub_groups"].items():
                        for i, item in enumerate(sub_group_data["items"]):
                            if item["id"] == update_request.item_id:
                                item_to_move = sub_group_data["items"].pop(i)
                                source_group_id = group_id
                                break
                        if item_to_move:
                            break
                    if item_to_move:
                        break
            
            # Add item to target
            if item_to_move:
                if update_request.target_group_id == "ungrouped":
                    groups_data["ungrouped_items"].append(item_to_move)
                elif update_request.target_group_id == "main_group_ungrouped":
                    # Special case: move to main group's ungrouped items (not a sub-group)
                    # This means adding to the "Ungrouped Items" sub-group of the specified main group
                    target_main_group_id = update_request.data.get("main_group_id") or source_group_id
                    if target_main_group_id and target_main_group_id in groups_data["main_groups"]:
                        main_group = groups_data["main_groups"][target_main_group_id]
                        
                        # Find or create ungrouped sub-group
                        ungrouped_sub_group = None
                        for sg_id, sg_data in main_group["sub_groups"].items():
                            if sg_data.get("is_ungrouped_subgroup", False):
                                ungrouped_sub_group = sg_data
                                break
                        
                        # Create ungrouped sub-group if it doesn't exist
                        if not ungrouped_sub_group:
                            ungrouped_sg_id = str(uuid.uuid4())
                            ungrouped_sub_group = {
                                "id": ungrouped_sg_id,
                                "name": "Ungrouped Items",
                                "items": [],
                                "is_ungrouped_subgroup": True
                            }
                            main_group["sub_groups"][ungrouped_sg_id] = ungrouped_sub_group
                        
                        ungrouped_sub_group["items"].append(item_to_move)
                else:
                    target_group = groups_data["main_groups"].get(update_request.target_group_id)
                    target_sub_group = update_request.target_sub_group_id or "default"
                    if target_group and target_sub_group in target_group["sub_groups"]:
                        target_group["sub_groups"][target_sub_group]["items"].append(item_to_move)
        
        elif action == "remove_from_sub_group":
            # Remove item from sub-group and add to main group's ungrouped items
            if (update_request.group_id in groups_data["main_groups"] and 
                update_request.sub_group_id in groups_data["main_groups"][update_request.group_id]["sub_groups"]):
                
                sub_group = groups_data["main_groups"][update_request.group_id]["sub_groups"][update_request.sub_group_id]
                item_to_move = None
                
                # Find and remove item from sub-group
                for i, item in enumerate(sub_group["items"]):
                    if item["id"] == update_request.item_id:
                        item_to_move = sub_group["items"].pop(i)
                        break
                
                if item_to_move:
                    main_group = groups_data["main_groups"][update_request.group_id]
                    
                    # Find or create ungrouped sub-group
                    ungrouped_sub_group = None
                    for sg_id, sg_data in main_group["sub_groups"].items():
                        if sg_data.get("is_ungrouped_subgroup", False):
                            ungrouped_sub_group = sg_data
                            break
                    
                    # Create ungrouped sub-group if it doesn't exist
                    if not ungrouped_sub_group:
                        ungrouped_sg_id = str(uuid.uuid4())
                        ungrouped_sub_group = {
                            "id": ungrouped_sg_id,
                            "name": "Ungrouped Items",
                            "items": [],
                            "is_ungrouped_subgroup": True
                        }
                        main_group["sub_groups"][ungrouped_sg_id] = ungrouped_sub_group
                    
                    # Add item to ungrouped sub-group
                    ungrouped_sub_group["items"].append(item_to_move)
        
        elif action == "move_multiple_items":
            # Move multiple items from ungrouped to a specific group/sub-group
            item_ids = update_request.data.get("item_ids", [])
            target_group_id = update_request.target_group_id
            target_sub_group_id = update_request.target_sub_group_id or "default"
            
            if target_group_id and target_group_id in groups_data["main_groups"]:
                target_group = groups_data["main_groups"][target_group_id]
                if target_sub_group_id in target_group["sub_groups"]:
                    items_to_move = []
                    
                    # Find items in ungrouped
                    for item_id in item_ids:
                        for i, item in enumerate(groups_data["ungrouped_items"]):
                            if item["id"] == item_id:
                                items_to_move.append(groups_data["ungrouped_items"].pop(i))
                                break
                    
                    # Add to target sub-group
                    target_group["sub_groups"][target_sub_group_id]["items"].extend(items_to_move)
        
        elif action == "toggle_group":
            # Enable/disable main group
            if update_request.group_id in groups_data["main_groups"]:
                current_state = groups_data["main_groups"][update_request.group_id]["enabled"]
                groups_data["main_groups"][update_request.group_id]["enabled"] = not current_state
        
        elif action == "update_group_name":
            # Update group name
            if update_request.group_id in groups_data["main_groups"]:
                new_name = update_request.data.get("name", "")
                if new_name:
                    groups_data["main_groups"][update_request.group_id]["name"] = new_name
        
        elif action == "update_sub_group_name":
            # Update sub group name
            if (update_request.group_id in groups_data["main_groups"] and 
                update_request.sub_group_id in groups_data["main_groups"][update_request.group_id]["sub_groups"]):
                new_name = update_request.data.get("name", "")
                if new_name:
                    groups_data["main_groups"][update_request.group_id]["sub_groups"][update_request.sub_group_id]["name"] = new_name
        
        # Recalculate statistics
        for group_id, group_data in groups_data["main_groups"].items():
            total_items = sum(len(sg["items"]) for sg in group_data["sub_groups"].values())
            group_data["total_items"] = total_items
            
            # Calculate estimated savings
            all_items = []
            for sg in group_data["sub_groups"].values():
                all_items.extend(sg["items"])
            group_data["estimated_savings"] = grouping_engine.calculate_estimated_savings(all_items)
        
        # Update metadata
        groups_data["metadata"]["last_updated"] = datetime.now().isoformat()
        groups_data["metadata"]["total_groups"] = len(groups_data["main_groups"])
        groups_data["metadata"]["total_ungrouped"] = len(groups_data["ungrouped_items"])
        
        # Save updated data (in legacy format)
        group_management_collection.update_one(
            {"file_id": file_id},
            {"$set": {"groups_data": groups_data, "updated_at": datetime.now()}}
        )
        
        # Convert back to new format for frontend response
        return convert_legacy_to_groups_format(groups_data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating group management: {str(e)}")

# ================== FILE MANAGEMENT ENDPOINTS ==================
        raise HTTPException(status_code=500, detail=f"Error deleting structured plan: {str(e)}")

@app.post("/api/group-management/generate-from-unique-values/{file_id}")
async def generate_groups_from_unique_values(file_id: str, config: dict):
    """Generate main groups for each unique value in the specified column"""
    try:
        print(f"[DEBUG] Generating groups from unique values for file: {file_id}")
        print(f"[DEBUG] Config: {config}")
        
        # Get column name from config
        column_name = config.get('column_name')
        if not column_name:
            raise HTTPException(status_code=400, detail="column_name is required in config")
        
        # Load CSV file from GridFS
        file_doc = files_collection.find_one({"file_id": file_id})
        if not file_doc:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Get file from GridFS
        grid_file = fs.get(file_doc["gridfs_id"])
        csv_content = grid_file.read()
        
        # Create DataFrame
        df = pd.read_csv(io.StringIO(csv_content.decode('utf-8')))
        print(f"[DEBUG] Loaded DataFrame with {len(df)} rows and columns: {list(df.columns)}")
        
        # Validate column exists
        if column_name not in df.columns:
            raise HTTPException(status_code=400, detail=f"Column '{column_name}' not found in dataset")
        
        # Generate groups using the new method
        from grouping_logic import generate_main_groups_from_unique_values
        groups_data = generate_main_groups_from_unique_values(df, column_name)
        
        if not groups_data:
            raise HTTPException(status_code=500, detail="Failed to generate groups from unique values")
        
        print(f"[DEBUG] Generated {len(groups_data.get('groups', []))} main groups")
        print(f"[DEBUG] Validation data: {groups_data.get('validation', {})}")
        
        # Convert to legacy format for storage
        storage_data = convert_groups_to_legacy_format(groups_data)
        
        # Optimize for storage if needed
        if get_document_size_estimate(storage_data) > 15 * 1024 * 1024:  # 15MB threshold
            print(f"[DEBUG] Data size exceeds threshold, optimizing for storage...")
            storage_data = optimize_group_data_for_storage(storage_data)
        
        # Save to database
        group_doc = {
            "file_id": file_id,
            "groups_data": storage_data,
            "created_at": datetime.now(),
            "generation_method": "unique_values_main_groups",
            "source_column": column_name,
            "total_groups": len(groups_data.get('groups', [])),
            "total_items": groups_data.get('total_items', 0)
        }
        
        # Upsert the document
        group_management_collection.replace_one(
            {"file_id": file_id},
            group_doc,
            upsert=True
        )
        
        print(f"[DEBUG] Saved group data to database")
        
        # Return the new format for frontend
        return {
            "success": True,
            "message": f"Successfully created {len(groups_data.get('groups', []))} main groups from column '{column_name}'",
            "groups_data": groups_data,
            "stats": {
                "total_groups": len(groups_data.get('groups', [])),
                "total_items": groups_data.get('total_items', 0),
                "grouped_items": groups_data.get('grouped_items', 0),
                "ungrouped_items": groups_data.get('ungrouped_count', 0)
            }
        }
        
    except Exception as e:
        print(f"[ERROR] generate_groups_from_unique_values: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating groups: {str(e)}")

@app.post("/api/group-management/generate-ai-sub-groups/{file_id}")
async def generate_ai_sub_groups(file_id: str, config: dict):
    """Generate AI-powered sub-groups based on core product types"""
    try:
        print(f"[DEBUG] Generating AI-powered sub-groups for file: {file_id}")
        print(f"[DEBUG] Config: {config}")
        
        # Get required columns from config
        main_group_column = config.get('main_group_column')
        sub_group_column = config.get('sub_group_column')
        use_main_groups = config.get('use_main_groups', True)
        
        if not sub_group_column:
            raise HTTPException(status_code=400, detail="sub_group_column is required for AI sub-grouping")
        
        # Load CSV file from GridFS
        file_doc = files_collection.find_one({"file_id": file_id})
        if not file_doc:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Get file from GridFS
        grid_file = fs.get(file_doc["gridfs_id"])
        csv_content = grid_file.read()
        
        # Create DataFrame
        df = pd.read_csv(io.StringIO(csv_content.decode('utf-8')))
        print(f"[DEBUG] Loaded DataFrame with {len(df)} rows and columns: {list(df.columns)}")
        
        # Validate columns exist
        if sub_group_column not in df.columns:
            raise HTTPException(status_code=400, detail=f"Sub group column '{sub_group_column}' not found in dataset")
        
        if use_main_groups and main_group_column and main_group_column not in df.columns:
            raise HTTPException(status_code=400, detail=f"Main group column '{main_group_column}' not found in dataset")
        
        # Generate AI-powered sub-groups        
        main_col = main_group_column if use_main_groups else None
        
        try:
            groups_data = generate_ai_powered_sub_groups_with_config(df, main_col, sub_group_column)
            
            if not groups_data:
                raise Exception("AI sub-grouping returned None")
                
        except Exception as ai_error:
            print(f"⚠️ AI-powered sub-grouping failed: {str(ai_error)}")
            
            # Try fallback if we have main groups
            if use_main_groups and main_group_column:
                print(f"🔄 Falling back to unique values main groups only...")
                groups_data = generate_main_groups_from_unique_values(df, main_group_column)
                
                if not groups_data:
                    raise HTTPException(status_code=500, detail=f"Both AI sub-grouping and fallback methods failed. Original error: {str(ai_error)}")
                    
                print(f"✅ Fallback successful: Generated {len(groups_data.get('groups', []))} main groups")
            else:
                raise HTTPException(status_code=500, detail=f"AI-powered sub-grouping failed and no fallback available for sub-grouping only mode. Error: {str(ai_error)}")
        
        print(f"[DEBUG] Generated {len(groups_data.get('groups', []))} groups with AI sub-grouping")
        print(f"[DEBUG] Total sub-groups: {groups_data.get('total_sub_groups', 0)}")
        print(f"[DEBUG] Validation data: {groups_data.get('validation', {})}")
        
        # Convert to legacy format for storage
        storage_data = convert_groups_to_legacy_format(groups_data)
        
        # Optimize for storage if needed
        if get_document_size_estimate(storage_data) > 15 * 1024 * 1024:  # 15MB threshold
            print(f"[DEBUG] Data size exceeds threshold, optimizing for storage...")
            storage_data = optimize_group_data_for_storage(storage_data)
        
        # Save to database
        group_doc = {
            "file_id": file_id,
            "groups_data": storage_data,
            "created_at": datetime.now(),
            "generation_method": "ai_powered_sub_grouping",
            "main_column": main_group_column,
            "sub_column": sub_group_column,
            "use_main_groups": use_main_groups,
            "total_groups": len(groups_data.get('groups', [])),
            "total_sub_groups": groups_data.get('total_sub_groups', 0),
            "total_items": groups_data.get('total_items', 0)
        }
        
        # Upsert the document
        group_management_collection.replace_one(
            {"file_id": file_id},
            group_doc,
            upsert=True
        )
        
        print(f"[DEBUG] Saved AI sub-group data to database")
        
        # Return the new format for frontend
        return {
            "success": True,
            "message": f"Successfully created {groups_data.get('total_sub_groups', 0)} AI-powered sub-groups across {len(groups_data.get('groups', []))} main groups",
            "groups_data": groups_data,
            "stats": {
                "total_groups": len(groups_data.get('groups', [])),
                "total_sub_groups": groups_data.get('total_sub_groups', 0),
                "total_items": groups_data.get('total_items', 0),
                "grouped_items": groups_data.get('grouped_items', 0),
                "ungrouped_items": groups_data.get('ungrouped_count', 0),
                "processing_method": "ai_powered_sub_grouping"
            }
        }
        
    except Exception as e:
        print(f"[ERROR] generate_ai_sub_groups: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating AI sub-groups: {str(e)}")

@app.get("/api/debug/test-openai")
async def test_openai_connection():
    """Test OpenAI API connection for debugging"""
    try:
        print("[DEBUG] Testing OpenAI API connection...")
        
        # Check if API key exists
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {
                "status": "error",
                "message": "OpenAI API key not found in environment variables",
                "suggestions": [
                    "Check if OPENAI_API_KEY is set in .env file",
                    "Restart the server after adding the API key"
                ]
            }
        
        if api_key == "test-key-for-demo":
            return {
                "status": "error", 
                "message": "OpenAI API key is set to test value",
                "suggestions": [
                    "Replace 'test-key-for-demo' with actual OpenAI API key",
                    "Get API key from https://platform.openai.com/api-keys"
                ]
            }
        
        # Test a simple API call
        import openai
        openai.api_key = api_key
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",  # Use cheaper model for testing
                messages=[
                    {"role": "user", "content": "Say 'Hello' if this API test is working."}
                ],
                max_tokens=10,
                temperature=0
            )
            
            response_text = response.choices[0].message.content.strip()
            
            return {
                "status": "success",
                "message": "OpenAI API connection successful",
                "api_key_prefix": f"{api_key[:8]}...{api_key[-4:]}",
                "test_response": response_text,
                "model_used": "gpt-3.5-turbo"
            }
            
        except openai.error.AuthenticationError as e:
            return {
                "status": "error",
                "message": "OpenAI API authentication failed",
                "error": str(e),
                "suggestions": [
                    "Check if your OpenAI API key is valid",
                    "Verify you have credits in your OpenAI account",
                    "Get a new API key from https://platform.openai.com/api-keys"
                ]
            }
            
        except openai.error.RateLimitError as e:
            return {
                "status": "error",
                "message": "OpenAI API rate limit exceeded",
                "error": str(e),
                "suggestions": [
                    "Wait a few minutes and try again",
                    "Check your OpenAI usage limits",
                    "Upgrade your OpenAI plan if needed"
                ]
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": "Unexpected OpenAI API error",
                "error": str(e),
                "error_type": str(type(e))
            }
        
    except Exception as e:
        return {
            "status": "error",
            "message": "Failed to test OpenAI connection",
            "error": str(e)
        }

def generate_structured_final_results(groups_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a structured final results list with unique groups and record counts"""
    try:
        final_results = {
            "main_groups": [],
            "total_items": 0,
            "total_groups": 0,
            "total_sub_groups": 0,
            "ungrouped_items_count": 0,
            "estimated_total_savings": "0%"
        }
        
        # Handle both legacy and new format
        main_groups = groups_data.get('main_groups', {})
        ungrouped_items = groups_data.get('ungrouped_items', [])
        
        # Convert to legacy format if needed
        if not main_groups and 'groups' in groups_data:
            converted_data = convert_groups_to_legacy_format(groups_data)
            main_groups = converted_data.get('main_groups', {})
            ungrouped_items = converted_data.get('ungrouped_items', [])
        
        total_items = 0
        total_sub_groups = 0
        
        # Process each main group
        for group_id, group_info in main_groups.items():
            main_group_data = {
                "name": group_info.get('name', 'Unnamed Group'),
                "sub_groups": [],
                "total_items": 0,
                "estimated_savings": group_info.get('estimated_savings', '0%')
            }
            
            # Process sub groups
            sub_groups = group_info.get('sub_groups', {})
            for sub_group_id, sub_group_info in sub_groups.items():
                items = sub_group_info.get('items', [])
                
                # Count unique items with their quantities
                unique_items = {}
                for item in items:
                    item_name = item.get('name', 'Unknown Item')
                    # Use the original name as key to maintain case and formatting
                    item_key = item_name.strip()
                    
                    if item_key in unique_items:
                        # If item has a count field, use it; otherwise add quantity
                        item_count = item.get('count', item.get('quantity', 1))
                        unique_items[item_key]['count'] += item_count
                    else:
                        unique_items[item_key] = {
                            'name': item_name,
                            'count': item.get('count', item.get('quantity', 1)),
                            'price': item.get('price', 0),
                            'category': item.get('category', 'Unknown')
                        }
                
                # Convert to list format for final results - sorted by count descending
                sub_group_items = []
                sub_group_total_items = 0
                for unique_item in sorted(unique_items.values(), key=lambda x: (-x['count'], x['name'])):
                    sub_group_items.append({
                        "name": unique_item['name'],
                        "count": unique_item['count']
                    })
                    sub_group_total_items += unique_item['count']
                
                if sub_group_items:  # Only add sub-groups with items
                    sub_group_data = {
                        "name": sub_group_info.get('name', 'Unnamed Sub Group'),
                        "items": sub_group_items,
                        "total_items": sub_group_total_items
                    }
                    main_group_data["sub_groups"].append(sub_group_data)
                    main_group_data["total_items"] += sub_group_total_items
                    total_sub_groups += 1
            
            if main_group_data["sub_groups"]:  # Only add main groups with sub-groups
                final_results["main_groups"].append(main_group_data)
                total_items += main_group_data["total_items"]
        
        # Calculate totals
        final_results["total_items"] = total_items + len(ungrouped_items)
        final_results["total_groups"] = len(final_results["main_groups"])
        final_results["total_sub_groups"] = total_sub_groups
        final_results["ungrouped_items_count"] = len(ungrouped_items)
        
        # Calculate estimated total savings (average of all group savings)
        if final_results["main_groups"]:
            total_savings = 0
            savings_count = 0
            for group in final_results["main_groups"]:
                savings_str = group.get("estimated_savings", "0%")
                try:
                    savings_num = float(savings_str.replace('%', ''))
                    total_savings += savings_num
                    savings_count += 1
                except:
                    pass
            
            if savings_count > 0:
                avg_savings = total_savings / savings_count
                final_results["estimated_total_savings"] = f"{avg_savings:.0f}%"
        
        return final_results
        
    except Exception as e:
        print(f"Error generating structured final results: {str(e)}")
        return {
            "main_groups": [],
            "total_items": 0,
            "total_groups": 0,
            "total_sub_groups": 0,
            "ungrouped_items_count": 0,
            "estimated_total_savings": "0%",
            "error": str(e)
        }

@app.post("/api/final-results/save/{file_id}")
async def save_final_results(file_id: str):
    """Save the current grouping results as final results"""
    try:
        # Get the current group management data
        group_doc = group_management_collection.find_one({"file_id": file_id})
        if not group_doc:
            raise HTTPException(status_code=404, detail="No group data found for this file")
        
        groups_data = group_doc.get('groups_data', {})
        
        # Generate structured final results
        structured_results = generate_structured_final_results(groups_data)
        
        # Prepare final results document
        final_results_doc = {
            "file_id": file_id,
            "structured_results": structured_results,
            "original_groups_data": groups_data,
            "created_at": datetime.now(),
            "version": "1.0"
        }
        
        # Save or update final results
        existing_results = final_results_collection.find_one({"file_id": file_id})
        if existing_results:
            final_results_collection.replace_one(
                {"file_id": file_id},
                final_results_doc
            )
            result_id = existing_results["_id"]
        else:
            result = final_results_collection.insert_one(final_results_doc)
            result_id = result.inserted_id
        
        return {
            "status": "success",
            "message": "Final results saved successfully",
            "result_id": str(result_id),
            "structured_results": structured_results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving final results: {str(e)}")

@app.get("/api/final-results/{file_id}")
async def get_final_results(file_id: str):
    """Get the saved final results for a file"""
    try:
        # Get saved final results
        final_results_doc = final_results_collection.find_one({"file_id": file_id})
        if not final_results_doc:
            raise HTTPException(status_code=404, detail="No final results found for this file")
        
        # Convert ObjectId to string for JSON serialization
        final_results_doc["_id"] = str(final_results_doc["_id"])
        
        return {
            "status": "success",
            "final_results": final_results_doc
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving final results: {str(e)}")

@app.get("/api/final-results/structured/{file_id}")
async def get_structured_final_results(file_id: str):
    """Get a structured list of final results suitable for display"""
    try:
        # Get saved final results
        final_results_doc = final_results_collection.find_one({"file_id": file_id})
        if not final_results_doc:
            # Try to generate from current group data if no saved results
            group_doc = group_management_collection.find_one({"file_id": file_id})
            if not group_doc:
                raise HTTPException(status_code=404, detail="No group data or final results found for this file")
            
            groups_data = group_doc.get('groups_data', {})
            structured_results = generate_structured_final_results(groups_data)
        else:
            structured_results = final_results_doc.get('structured_results', {})
        
        return {
            "status": "success",
            "file_id": file_id,
            "structured_results": structured_results,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving structured final results: {str(e)}")

@app.delete("/api/final-results/{file_id}")
async def delete_final_results(file_id: str):
    """Delete the saved final results for a file"""
    try:
        result = final_results_collection.delete_one({"file_id": file_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="No final results found for this file")
        
        return {
            "status": "success",
            "message": "Final results deleted successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting final results: {str(e)}")

# Saved Groups Endpoints
@app.post("/api/saved-groups")
async def save_group_with_name(data: SavedGroupData):
    """Save a group with user-provided name and description"""
    try:
        print(f"Received save request for group: {data.name}")
        print(f"File ID: {data.file_id}")
        print(f"Structured results keys: {list(data.structured_results.keys()) if data.structured_results else 'None'}")
        
        # Get the original file metadata to include column information
        file_metadata = None
        if data.file_id:
            file_metadata = files_collection.find_one({"file_id": data.file_id})
            print(f"Found file metadata: {bool(file_metadata)}")
        
        # Create the saved group document
        saved_group_doc = {
            "name": data.name,
            "description": data.description,
            "structured_results": data.structured_results,
            "file_id": data.file_id,
            "created_at": data.created_at,
            "saved_at": datetime.now().isoformat()
        }
        
        # Add column metadata if available
        if file_metadata:
            saved_group_doc["file_name"] = file_metadata.get("filename", "Unknown")
            saved_group_doc["total_rows"] = file_metadata.get("total_rows", 0)
            saved_group_doc["columns_metadata"] = file_metadata.get("columns_metadata", [])
            # Keep original columns list for backward compatibility
            saved_group_doc["available_columns"] = file_metadata.get("columns", [])
            print(f"Added {len(saved_group_doc.get('columns_metadata', []))} column metadata entries")
        else:
            print("No file metadata found - saved group will not have column information")
        
        print(f"About to save document with keys: {list(saved_group_doc.keys())}")
        
        # Save to database
        result = saved_groups_collection.insert_one(saved_group_doc)
        
        print(f"Successfully saved with ID: {result.inserted_id}")
        
        return {
            "status": "success",
            "message": "Group saved successfully",
            "group_id": str(result.inserted_id)
        }
        
    except Exception as e:
        print(f"Error saving group: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        raise HTTPException(status_code=500, detail=f"Error saving group: {str(e)}")

@app.get("/api/saved-groups")
async def get_saved_groups():
    """Get all saved groups with summary information"""
    try:
        saved_groups = list(saved_groups_collection.find(
            {},
            {
                "_id": 1,
                "name": 1,
                "description": 1,
                "file_id": 1,
                "created_at": 1,
                "saved_at": 1,
                "structured_results": 1
            }
        ).sort("saved_at", -1))
        
        # Enhance each group with file name and summary info
        for group in saved_groups:
            group["_id"] = str(group["_id"])
            
            # Try to get file name
            file_meta = files_collection.find_one({"file_id": group.get("file_id")})
            if file_meta:
                group["file_name"] = file_meta.get("filename", "Unknown File")
            else:
                group["file_name"] = "Unknown File"
            
            # Add structured results summary if available
            if "structured_results" not in group:
                group["structured_results"] = {
                    "total_items": 0,
                    "total_groups": 0,
                    "total_sub_groups": 0,
                    "estimated_total_savings": "0%"
                }
        
        return {
            "status": "success",
            "saved_groups": saved_groups
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving saved groups: {str(e)}")

@app.get("/api/saved-groups/{group_id}")
async def get_saved_group_details(group_id: str):
    """Get detailed information for a specific saved group"""
    try:
        from bson import ObjectId
        
        # Validate ObjectId format
        if not ObjectId.is_valid(group_id):
            raise HTTPException(status_code=400, detail="Invalid group ID format")
        
        saved_group = saved_groups_collection.find_one({"_id": ObjectId(group_id)})
        
        if not saved_group:
            raise HTTPException(status_code=404, detail="Saved group not found")
        
        # Convert ObjectId to string for JSON serialization
        saved_group["_id"] = str(saved_group["_id"])
        
        return {
            "status": "success",
            "saved_group": saved_group
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving saved group: {str(e)}")

@app.delete("/api/saved-groups/{group_id}")
async def delete_saved_group(group_id: str):
    """Delete a saved group"""
    try:
        from bson import ObjectId
        
        # Validate ObjectId format
        if not ObjectId.is_valid(group_id):
            raise HTTPException(status_code=400, detail="Invalid group ID format")
        
        result = saved_groups_collection.delete_one({"_id": ObjectId(group_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Saved group not found")
        
        return {
            "status": "success",
            "message": "Saved group deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting saved group: {str(e)}")

@app.get("/api/saved-groups/{group_id}/columns")
async def get_saved_group_columns(group_id: str):
    """Get column metadata for a specific saved group"""
    try:
        from bson import ObjectId
        
        # Validate ObjectId format
        if not ObjectId.is_valid(group_id):
            raise HTTPException(status_code=400, detail="Invalid group ID format")
        
        saved_group = saved_groups_collection.find_one({"_id": ObjectId(group_id)})
        
        if not saved_group:
            raise HTTPException(status_code=404, detail="Saved group not found")
        
        # Get column metadata - should be stored with the saved group
        columns_metadata = saved_group.get('columns_metadata', [])
        available_columns = saved_group.get('available_columns', [])
        file_name = saved_group.get('file_name', 'Unknown')
        total_rows = saved_group.get('total_rows', 0)
        
        # If no metadata in saved group, try to get from original file
        if not columns_metadata and saved_group.get('file_id'):
            file_metadata = files_collection.find_one({"file_id": saved_group['file_id']})
            if file_metadata:
                columns_metadata = file_metadata.get('columns_metadata', [])
                available_columns = file_metadata.get('columns', [])
                file_name = file_metadata.get('filename', 'Unknown')
                total_rows = file_metadata.get('total_rows', 0)
        
        return {
            "status": "success",
            "group_id": group_id,
            "group_name": saved_group.get('name', 'Unknown Group'),
            "file_name": file_name,
            "total_rows": total_rows,
            "columns_metadata": columns_metadata,
            "available_columns": available_columns  # For backward compatibility
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving column metadata: {str(e)}")

@app.post("/api/saved-groups/{group_id}/migrate-metadata")
async def migrate_group_metadata(group_id: str):
    """Migrate a specific saved group to include column metadata from its original file"""
    try:
        from bson import ObjectId
        
        # Validate ObjectId format
        if not ObjectId.is_valid(group_id):
            raise HTTPException(status_code=400, detail="Invalid group ID format")
        
        saved_group = saved_groups_collection.find_one({"_id": ObjectId(group_id)})
        
        if not saved_group:
            raise HTTPException(status_code=404, detail="Saved group not found")
        
        # Check if already has metadata
        if saved_group.get('columns_metadata'):
            return {
                "status": "success",
                "message": "Group already has column metadata",
                "columns_count": len(saved_group.get('columns_metadata', []))
            }
        
        # Get the original file metadata
        file_id = saved_group.get('file_id')
        if not file_id:
            raise HTTPException(status_code=400, detail="No file ID found for this group")
        
        file_metadata = files_collection.find_one({"file_id": file_id})
        if not file_metadata:
            raise HTTPException(status_code=404, detail="Original file metadata not found")
        
        # Prepare update data
        update_data = {}
        
        # Add column metadata if available
        if file_metadata.get('columns_metadata'):
            update_data['columns_metadata'] = file_metadata['columns_metadata']
        
        # Add other useful file information
        if file_metadata.get('filename'):
            update_data['file_name'] = file_metadata['filename']
        
        if file_metadata.get('total_rows'):
            update_data['total_rows'] = file_metadata['total_rows']
        
        if file_metadata.get('columns'):
            update_data['available_columns'] = file_metadata['columns']
        
        # Add migration timestamp
        update_data['metadata_migrated_at'] = datetime.now().isoformat()
        
        if update_data:
            # Update the saved group
            result = saved_groups_collection.update_one(
                {"_id": ObjectId(group_id)},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                return {
                    "status": "success",
                    "message": "Column metadata added successfully",
                    "columns_count": len(update_data.get('columns_metadata', []))
                }
            else:
                raise HTTPException(status_code=500, detail="Failed to update group metadata")
        else:
            raise HTTPException(status_code=404, detail="No metadata available to migrate")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error migrating metadata: {str(e)}")

@app.get("/api/saved-groups/{group_id}/export-excel")
async def export_saved_group_to_excel(group_id: str):
    """Export a saved group to Excel format with main groups, sub groups, and items"""
    try:
        from bson import ObjectId
        
        # Validate ObjectId format
        if not ObjectId.is_valid(group_id):
            raise HTTPException(status_code=400, detail="Invalid group ID format")
        
        # Get the saved group
        saved_group = saved_groups_collection.find_one({"_id": ObjectId(group_id)})
        
        if not saved_group:
            raise HTTPException(status_code=404, detail="Saved group not found")
        
        # Create Excel workbook
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Main data sheet with groups, sub groups, and items
            export_data = []
            structured_results = saved_group.get('structured_results', {})
            main_groups = structured_results.get('main_groups', [])
            
            # Handle both list and dict structures for main_groups
            if isinstance(main_groups, dict):
                main_groups = list(main_groups.values())
            elif not isinstance(main_groups, list):
                main_groups = []
            
            for main_group in main_groups:
                if not isinstance(main_group, dict):
                    continue
                    
                main_group_name = main_group.get('name', 'Unknown Main Group')
                sub_groups = main_group.get('sub_groups', [])
                
                # Handle both list and dict structures for sub_groups
                if isinstance(sub_groups, dict):
                    sub_groups = list(sub_groups.values())
                elif not isinstance(sub_groups, list):
                    sub_groups = []
                
                for sub_group in sub_groups:
                    if not isinstance(sub_group, dict):
                        continue
                        
                    sub_group_name = sub_group.get('name', 'Unknown Sub Group')
                    items = sub_group.get('items', [])
                    
                    if not isinstance(items, list):
                        items = []
                    
                    if items:
                        for item in items:
                            if isinstance(item, dict):
                                export_data.append({
                                    'Main Group': main_group_name,
                                    'Sub Group': sub_group_name,
                                    'Item Name': item.get('name', 'Unknown Item'),
                                    'Record Count': item.get('count', 1)
                                })
                    else:
                        # Add a row even if no items to show the group structure
                        export_data.append({
                            'Main Group': main_group_name,
                            'Sub Group': sub_group_name,
                            'Item Name': 'No items',
                            'Record Count': 0
                        })
            
            # Create the main export sheet
            if export_data:
                export_df = pd.DataFrame(export_data)
                export_df.to_excel(writer, sheet_name='Groups and Items', index=False)
            else:
                # Create empty sheet if no data
                empty_df = pd.DataFrame({
                    'Main Group': ['No data available'],
                    'Sub Group': ['No data available'],
                    'Item Name': ['No items found'],
                    'Record Count': [0]
                })
                empty_df.to_excel(writer, sheet_name='Groups and Items', index=False)
        
        output.seek(0)
        
        # Create the filename - ensure it's safe for filesystem
        safe_name = saved_group.get('name', 'group')
        safe_name = ''.join(c for c in safe_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        if not safe_name:
            safe_name = 'export'
        filename = f"{safe_name}_groups_export.xlsx"
        
        # Return as streaming response
        return StreamingResponse(
            io.BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error exporting to Excel: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error exporting to Excel: {str(e)}")

@app.get("/api/files/{file_id}/data")
async def get_file_data(file_id: str):
    """Get the original CSV data for a file"""
    try:
        print(f"Getting file data for file_id: {file_id}")
        
        # Get the file from GridFS - files are stored with UUID strings as _id
        fs = gridfs.GridFS(db)
        file_data = None
        
        try:
            # Try direct UUID string lookup first
            print(f"Trying direct UUID lookup for: {file_id}")
            file_data = fs.get(file_id)
            print(f"Found file with UUID: {file_data.filename}")
        except gridfs.NoFile:
            # If not found with UUID, try ObjectId format (for backward compatibility)
            try:
                from bson import ObjectId
                print(f"UUID lookup failed, trying ObjectId for: {file_id}")
                if ObjectId.is_valid(file_id):
                    file_data = fs.get(ObjectId(file_id))
                    print(f"Found file with ObjectId: {file_data.filename}")
                else:
                    print(f"Invalid ObjectId format: {file_id}")
                    raise HTTPException(status_code=404, detail="File not found - invalid ID format")
            except gridfs.NoFile:
                print(f"File not found with either UUID or ObjectId: {file_id}")
                raise HTTPException(status_code=404, detail="File not found")
        except Exception as gridfs_error:
            print(f"GridFS error: {gridfs_error}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(gridfs_error)}")
        
        if not file_data:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Read the file content as bytes with proper error handling
        try:
            raw_bytes = file_data.read()
            print(f"Read {len(raw_bytes)} bytes from file")
            
            if not raw_bytes:
                raise HTTPException(status_code=500, detail="File is empty or could not be read")
                
        except Exception as read_error:
            print(f"Error reading file data: {read_error}")
            raise HTTPException(status_code=500, detail=f"Error reading file: {str(read_error)}")
        
        # Try different encodings on the bytes with comprehensive error handling
        csv_content = None
        encodings_to_try = ['utf-8', 'windows-1252', 'iso-8859-1', 'cp1252', 'latin1', 'ascii']
        encoding_used = None
        
        for encoding in encodings_to_try:
            try:
                csv_content = raw_bytes.decode(encoding)
                encoding_used = encoding
                print(f"Successfully decoded with {encoding}, length: {len(csv_content)} characters")
                break
            except UnicodeDecodeError as decode_error:
                print(f"{encoding} decoding failed: {decode_error}")
                continue
            except Exception as unexpected_error:
                print(f"Unexpected error with {encoding}: {unexpected_error}")
                continue
        
        # If all encodings fail, use UTF-8 with error replacement as last resort
        if csv_content is None:
            try:
                csv_content = raw_bytes.decode('utf-8', errors='replace')
                encoding_used = 'utf-8-replace'
                print(f"Decoded with UTF-8 and error replacement, length: {len(csv_content)} characters")
            except Exception as final_error:
                print(f"Even UTF-8 with error replacement failed: {final_error}")
                raise HTTPException(status_code=500, detail="File encoding is not supported")
        
        if not csv_content or len(csv_content.strip()) == 0:
            raise HTTPException(status_code=500, detail="File appears to be empty after decoding")
        
        # Parse CSV with comprehensive error handling
        from io import StringIO
        
        try:
            csv_buffer = StringIO(csv_content)
            df = pd.read_csv(csv_buffer)
            print(f"Parsed CSV successfully: {len(df)} rows, {len(df.columns)} columns")
            print(f"Columns: {list(df.columns)}")
            
        except pd.errors.EmptyDataError:
            print("CSV file is empty")
            raise HTTPException(status_code=500, detail="CSV file is empty")
            
        except pd.errors.ParserError as parser_error:
            print(f"CSV parsing error: {parser_error}")
            # Try with different parameters
            try:
                csv_buffer = StringIO(csv_content)
                df = pd.read_csv(csv_buffer, sep=None, engine='python')  # Auto-detect separator
                print(f"Parsed CSV with auto-detection: {len(df)} rows, {len(df.columns)} columns")
            except Exception as fallback_error:
                print(f"CSV parsing with auto-detection also failed: {fallback_error}")
                raise HTTPException(status_code=500, detail=f"Cannot parse CSV file: {str(fallback_error)}")
                
        except Exception as csv_error:
            print(f"Unexpected CSV parsing error: {csv_error}")
            # Try with most permissive parameters
            try:
                csv_buffer = StringIO(csv_content)
                df = pd.read_csv(csv_buffer, 
                               on_bad_lines='skip',  # Skip bad lines
                               encoding_errors='replace',  # Replace encoding errors
                               sep=None,  # Auto-detect separator
                               engine='python')
                print(f"Parsed CSV with permissive settings: {len(df)} rows, {len(df.columns)} columns")
            except Exception as final_csv_error:
                print(f"All CSV parsing attempts failed: {final_csv_error}")
                raise HTTPException(status_code=500, detail=f"Cannot parse CSV file: {str(final_csv_error)}")
        
        # Validate the parsed data
        if df.empty:
            raise HTTPException(status_code=500, detail="CSV file contains no data")
            
        if len(df.columns) == 0:
            raise HTTPException(status_code=500, detail="CSV file contains no columns")
        
        # Convert to list of dictionaries with error handling
        try:
            # Handle NaN and infinite values before converting to dict - replace with None for JSON serialization
            df_clean = df.copy()
            
            # Replace NaN values with None (which becomes null in JSON)
            df_clean = df_clean.where(pd.notnull(df_clean), None)
            
            # Replace infinite values with None (inf and -inf are not JSON compliant)
            import numpy as np
            numeric_columns = df_clean.select_dtypes(include=[np.number]).columns
            for col in numeric_columns:
                df_clean[col] = df_clean[col].replace([np.inf, -np.inf], None)
            
            data = df_clean.to_dict('records')
            print(f"Converted DataFrame to dict with {len(data)} records, NaN and infinite values replaced with None")
        except Exception as dict_error:
            print(f"Error converting DataFrame to dict: {dict_error}")
            raise HTTPException(status_code=500, detail=f"Error processing CSV data: {str(dict_error)}")
        
        result = {
            "file_id": file_id,
            "filename": file_data.filename,
            "data": data,
            "columns": list(df.columns),
            "row_count": len(data),
            "encoding_used": encoding_used
        }
        
        print(f"Successfully returning result with {len(result['data'])} rows and {len(result['columns'])} columns")
        print(f"Encoding used: {encoding_used}")
        return result
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"Unexpected error in get_file_data: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Custom Export Data Model
class CustomExportColumn(BaseModel):
    column_name: str
    aggregation_type: str  # 'majority' or 'sum'

class CustomExportRequest(BaseModel):
    group_id: str
    custom_columns: List[CustomExportColumn]

@app.post("/api/export-custom-excel")
async def export_custom_excel(request: CustomExportRequest):
    """Export a saved group to Excel with custom columns and aggregations"""
    try:
        from bson import ObjectId
        from collections import Counter
        import numpy as np
        
        # Validate ObjectId format for group_id
        if not ObjectId.is_valid(request.group_id):
            raise HTTPException(status_code=400, detail="Invalid group ID format")
        
        # Get the saved group
        saved_group = saved_groups_collection.find_one({"_id": ObjectId(request.group_id)})
        if not saved_group:
            raise HTTPException(status_code=404, detail="Saved group not found")
        
        # Get the original file data
        file_id = saved_group.get('file_id')
        if not file_id:
            raise HTTPException(status_code=400, detail="No original file associated with this group")
        
        # Get original CSV data with robust error handling
        fs = gridfs.GridFS(db)
        file_data = None
        
        try:
            # Try direct UUID string lookup first (most common case)
            file_data = fs.get(file_id)
            print(f"Found export file with UUID: {file_data.filename}")
        except gridfs.NoFile:
            # If not found with UUID, try ObjectId format (for backward compatibility)
            try:
                if ObjectId.is_valid(file_id):
                    file_data = fs.get(ObjectId(file_id))
                    print(f"Found export file with ObjectId: {file_data.filename}")
                else:
                    raise HTTPException(status_code=404, detail="Original file not found - invalid file ID format")
            except gridfs.NoFile:
                raise HTTPException(status_code=404, detail="Original file not found")
        except Exception as gridfs_error:
            print(f"GridFS error during export: {gridfs_error}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(gridfs_error)}")
        
        if not file_data:
            raise HTTPException(status_code=404, detail="Original file not found")
        
        # Read the file content as bytes with proper error handling
        try:
            raw_bytes = file_data.read()
            print(f"Read {len(raw_bytes)} bytes from original file for export")
            
            if not raw_bytes:
                raise HTTPException(status_code=500, detail="Original file is empty or could not be read")
                
        except Exception as read_error:
            print(f"Error reading export file data: {read_error}")
            raise HTTPException(status_code=500, detail=f"Error reading original file: {str(read_error)}")
        
        # Try different encodings on the bytes with comprehensive error handling
        csv_content = None
        encodings_to_try = ['utf-8', 'windows-1252', 'iso-8859-1', 'cp1252', 'latin1', 'ascii']
        
        for encoding in encodings_to_try:
            try:
                csv_content = raw_bytes.decode(encoding)
                print(f"Successfully decoded export file with {encoding}")
                break
            except UnicodeDecodeError as decode_error:
                print(f"Export file {encoding} decoding failed: {decode_error}")
                continue
            except Exception as unexpected_error:
                print(f"Unexpected error with {encoding} during export: {unexpected_error}")
                continue
        
        # If all encodings fail, use UTF-8 with error replacement as last resort
        if csv_content is None:
            try:
                csv_content = raw_bytes.decode('utf-8', errors='replace')
                print(f"Decoded export file with UTF-8 and error replacement")
            except Exception as final_error:
                print(f"Even UTF-8 with error replacement failed during export: {final_error}")
                raise HTTPException(status_code=500, detail="Original file encoding is not supported")
        
        if not csv_content or len(csv_content.strip()) == 0:
            raise HTTPException(status_code=500, detail="Original file appears to be empty after decoding")
        
        # Parse CSV with comprehensive error handling
        from io import StringIO
        
        try:
            csv_buffer = StringIO(csv_content)
            original_df = pd.read_csv(csv_buffer)
            print(f"Parsed export CSV successfully: {len(original_df)} rows, {len(original_df.columns)} columns")
            
        except pd.errors.EmptyDataError:
            print("Export CSV file is empty")
            raise HTTPException(status_code=500, detail="Original CSV file is empty")
            
        except pd.errors.ParserError as parser_error:
            print(f"Export CSV parsing error: {parser_error}")
            # Try with different parameters
            try:
                csv_buffer = StringIO(csv_content)
                original_df = pd.read_csv(csv_buffer, sep=None, engine='python')  # Auto-detect separator
                print(f"Parsed export CSV with auto-detection: {len(original_df)} rows, {len(original_df.columns)} columns")
            except Exception as fallback_error:
                print(f"Export CSV parsing with auto-detection also failed: {fallback_error}")
                raise HTTPException(status_code=500, detail=f"Cannot parse original CSV file: {str(fallback_error)}")
                
        except Exception as csv_error:
            print(f"Unexpected export CSV parsing error: {csv_error}")
            # Try with most permissive parameters
            try:
                csv_buffer = StringIO(csv_content)
                original_df = pd.read_csv(csv_buffer, 
                                        on_bad_lines='skip',  # Skip bad lines
                                        encoding_errors='replace',  # Replace encoding errors
                                        sep=None,  # Auto-detect separator
                                        engine='python')
                print(f"Parsed export CSV with permissive settings: {len(original_df)} rows, {len(original_df.columns)} columns")
            except Exception as final_csv_error:
                print(f"All export CSV parsing attempts failed: {final_csv_error}")
                raise HTTPException(status_code=500, detail=f"Cannot parse original CSV file: {str(final_csv_error)}")
        
        # Validate the parsed data
        if original_df.empty:
            raise HTTPException(status_code=500, detail="Original CSV file contains no data")
            
        if len(original_df.columns) == 0:
            raise HTTPException(status_code=500, detail="Original CSV file contains no columns")
        
        # Create aggregation mapping - this is a simplified approach
        # In a full implementation, you'd need to track which original rows map to each item
        def aggregate_column_values(values, aggregation_type, column_name):
            """Aggregate column values based on type"""
            if not values:
                return None
            
            # Remove null/empty values
            clean_values = [v for v in values if pd.notna(v) and str(v).strip() != '']
            if not clean_values:
                return None
            
            if aggregation_type == 'majority':
                # Return the most common value
                if clean_values:
                    counter = Counter(clean_values)
                    return counter.most_common(1)[0][0]
                return None
            elif aggregation_type == 'sum':
                # Sum numeric values only
                numeric_values = []
                for v in clean_values:
                    try:
                        numeric_values.append(float(v))
                    except (ValueError, TypeError):
                        continue
                return sum(numeric_values) if numeric_values else 0
            
            return None
        
        # Build export data
        export_data = []
        structured_results = saved_group.get('structured_results', {})
        
        print(f"Processing structured results for export...")
        print(f"Structured results keys: {list(structured_results.keys()) if structured_results else 'None'}")
        
        # Handle different data structures
        main_groups = []
        if 'main_groups' in structured_results:
            main_groups_raw = structured_results['main_groups']
            if isinstance(main_groups_raw, dict):
                main_groups = list(main_groups_raw.values())
            elif isinstance(main_groups_raw, list):
                main_groups = main_groups_raw
            else:
                print(f"Unexpected main_groups type: {type(main_groups_raw)}")
        elif 'groups' in structured_results:
            # Handle newer format
            main_groups = structured_results['groups']
            
        print(f"Found {len(main_groups)} main groups for export")
        
        for i, main_group in enumerate(main_groups):
            if not isinstance(main_group, dict):
                print(f"Skipping non-dict main group at index {i}: {type(main_group)}")
                continue
                
            main_group_name = main_group.get('name', f'Main Group {i+1}')
            print(f"Processing main group: {main_group_name}")
            
            # Handle sub_groups with different structures
            sub_groups = []
            if 'sub_groups' in main_group:
                sub_groups_raw = main_group['sub_groups']
                if isinstance(sub_groups_raw, dict):
                    sub_groups = list(sub_groups_raw.values())
                elif isinstance(sub_groups_raw, list):
                    sub_groups = sub_groups_raw
            
            print(f"Found {len(sub_groups)} sub groups in {main_group_name}")
            
            if not sub_groups:
                # If no sub_groups, create a default one
                sub_groups = [{'name': main_group_name, 'items': main_group.get('items', [])}]
        
        for main_group in main_groups:
            if not isinstance(main_group, dict):
                continue
                
            main_group_name = main_group.get('name', 'Unknown Main Group')
            sub_groups = main_group.get('sub_groups', [])
            
            if isinstance(sub_groups, dict):
                sub_groups = list(sub_groups.values())
            elif not isinstance(sub_groups, list):
                sub_groups = []
            
            for j, sub_group in enumerate(sub_groups):
                if not isinstance(sub_group, dict):
                    print(f"Skipping non-dict sub group at index {j} in {main_group_name}")
                    continue
                    
                sub_group_name = sub_group.get('name', f'Sub Group {j+1}')
                items = sub_group.get('items', [])
                
                if not isinstance(items, list):
                    print(f"Items is not a list in {sub_group_name}, converting from {type(items)}")
                    items = []
                
                print(f"Processing {len(items)} items in sub group: {sub_group_name}")
                
                for k, item in enumerate(items):
                    if not isinstance(item, dict):
                        print(f"Skipping non-dict item at index {k} in {sub_group_name}")
                        continue
                    
                    item_name = item.get('name', f'Item {k+1}')
                    item_count = item.get('count', 1)
                    
                    # Base row data
                    row = {
                        'Main Group': main_group_name,
                        'Sub Group': sub_group_name,
                        'Item Name': item_name,
                        'Record Count': item_count
                    }
                    
                    print(f"Processing item: {item_name} (count: {item_count})")
                    
                    # Add custom columns with aggregated values
                    for custom_col in request.custom_columns:
                        column_name = custom_col.column_name
                        aggregation_type = custom_col.aggregation_type
                        
                        print(f"Processing custom column: {column_name} ({aggregation_type})")
                        
                        if column_name in original_df.columns:
                            # Enhanced matching: try multiple strategies to find related records
                            matching_rows = pd.DataFrame()
                            
                            # Strategy 1: Exact name match (case-insensitive)
                            if 'name' in original_df.columns:
                                exact_matches = original_df[original_df['name'].str.lower() == item_name.lower()]
                                if not exact_matches.empty:
                                    matching_rows = exact_matches
                                    print(f"Found {len(matching_rows)} exact matches for {item_name}")
                            
                            # Strategy 2: Partial name match in any column
                            if matching_rows.empty:
                                matching_rows = original_df[original_df.apply(
                                    lambda row: any(
                                        str(item_name).lower() in str(cell).lower() 
                                        for cell in row.values 
                                        if pd.notna(cell) and str(cell).strip() != ''
                                    ), axis=1
                                )]
                                if not matching_rows.empty:
                                    print(f"Found {len(matching_rows)} partial matches for {item_name}")
                            
                            # Strategy 3: If still no matches, try keyword matching
                            if matching_rows.empty:
                                item_words = set(item_name.lower().split())
                                matching_rows = original_df[original_df.apply(
                                    lambda row: any(
                                        len(item_words.intersection(set(str(cell).lower().split()))) >= min(2, len(item_words))
                                        for cell in row.values 
                                        if pd.notna(cell) and str(cell).strip() != ''
                                    ), axis=1
                                )]
                                if not matching_rows.empty:
                                    print(f"Found {len(matching_rows)} keyword matches for {item_name}")
                            
                            # Apply aggregation
                            if not matching_rows.empty:
                                values = matching_rows[column_name].tolist()
                                aggregated_value = aggregate_column_values(values, aggregation_type, column_name)
                                row[f"{column_name} ({aggregation_type})"] = aggregated_value
                                print(f"Aggregated value for {column_name}: {aggregated_value}")
                            else:
                                # If no matches found, use a sample of data for demonstration
                                # In production, this should be handled based on business logic
                                sample_values = original_df[column_name].dropna().head(item_count).tolist()
                                if sample_values:
                                    aggregated_value = aggregate_column_values(sample_values, aggregation_type, column_name)
                                    row[f"{column_name} ({aggregation_type})"] = f"Sample: {aggregated_value}"
                                    print(f"Using sample value for {column_name}: {aggregated_value}")
                                else:
                                    row[f"{column_name} ({aggregation_type})"] = "No data"
                                    print(f"No data available for {column_name}")
                        else:
                            row[f"{column_name} ({aggregation_type})"] = "Column not found"
                            print(f"Column {column_name} not found in original data")
                    
                    export_data.append(row)
        
        print(f"Generated {len(export_data)} rows for export")
        
        print(f"Generated {len(export_data)} rows for export")
        
        # Create Excel workbook
        output = BytesIO()
        
        try:
            if export_data:
                export_df = pd.DataFrame(export_data)
                print(f"Created DataFrame with shape: {export_df.shape}")
                print(f"DataFrame columns: {list(export_df.columns)}")
            else:
                # Create empty sheet if no data
                print("No export data generated, creating empty template")
                base_columns = ['Main Group', 'Sub Group', 'Item Name', 'Record Count']
                custom_columns = [f"{col.column_name} ({col.aggregation_type})" for col in request.custom_columns]
                all_columns = base_columns + custom_columns
                
                export_df = pd.DataFrame({col: ['No data available'] for col in all_columns})
                print(f"Created empty DataFrame with columns: {all_columns}")
            
            # Create Excel file with error handling
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                export_df.to_excel(writer, sheet_name='Custom Export', index=False)
                print("Successfully wrote Excel file to buffer")
            
            output.seek(0)
            print(f"Excel file size: {len(output.getvalue())} bytes")
            
        except Exception as excel_error:
            print(f"Error creating Excel file: {excel_error}")
            raise HTTPException(status_code=500, detail=f"Error creating Excel file: {str(excel_error)}")
        
        # Create filename
        safe_name = saved_group.get('name', 'group')
        safe_name = ''.join(c for c in safe_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        if not safe_name:
            safe_name = 'export'
        filename = f"{safe_name}_custom_export.xlsx"
        
        return StreamingResponse(
            BytesIO(output.getvalue()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"Error in custom export: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error in custom export: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    
    # Check environment variables and display status
    env_vars = {
        "MONGO_URL": MONGO_URL,
        "DB_NAME": DB_NAME,
        "OPENAI_API_KEY": "✓ Set" if OPENAI_API_KEY else "❌ Missing"
    }
    
    print("\n=== CSV Processing Dashboard Backend ===")
    print(f"MongoDB connection: {'✓ Connected' if client else '❌ Not connected'}")
    print(f"Database: {DB_NAME}")
    print(f"OpenAI API Key: {env_vars['OPENAI_API_KEY']}")
    print("=====================================\n")
    print("Grouping-only mode enabled")
    print("Chat and chart features removed")
    print("=====================================\n")
    print("To run the server, use:")
    print("uvicorn server:app --reload --port 8000")
    print("or")
    print("python server.py")
    print("=====================================\n")
    
    # Run the server
    uvicorn.run(app, host="0.0.0.0", port=8000)