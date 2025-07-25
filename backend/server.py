from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import pandas as pd
import pymongo
from pymongo import MongoClient
import gridfs
import io
import os
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import openai
from dotenv import load_dotenv
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
import base64
from io import BytesIO
import cloudinary
import cloudinary.uploader
import cloudinary.api
import pathlib
import bson

# Import our custom grouping logic
from grouping_logic import (
    ProductGroupingEngine, 
    generate_ai_powered_sub_groups_with_config,
    generate_main_groups_from_unique_values
)

# Load environment variables
load_dotenv()

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

# Import PandasAI components
try:
    from pandasai import SmartDataframe
    from pandasai.llm import OpenAI
    from pandasai.helpers.openai_info import get_openai_callback
    from pandasai.middlewares import StorageMiddleware
    from pandasai.middlewares import ChartMiddleware  # Add chart middleware
    
    # Create enhanced chart middleware for better visualization control
    class EnhancedChartMiddleware(ChartMiddleware):
        """Enhanced chart middleware for PandasAI with better chart support"""
        
        def run(self, df, config, prompt, prompt_id):
            # Run the parent middleware
            return super().run(df, config, prompt, prompt_id)
        
        def save_chart(self, figure, response_parser):
            # Enhanced chart saving with better quality
            import matplotlib.pyplot as plt
            chart_path = super().save_chart(figure, response_parser)
            return chart_path
    
    PANDASAI_AVAILABLE = True
except ImportError:
    PANDASAI_AVAILABLE = False
    print("PandasAI not available, using fallback approach")

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

# Database connection
MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHARTS_EXPORT_PATH = os.getenv("CHARTS_EXPORT_PATH", "exports/charts")

# Ensure export directory exists
os.makedirs(CHARTS_EXPORT_PATH, exist_ok=True)

# Initialize OpenAI client
openai.api_key = OPENAI_API_KEY

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
chat_collection = db.chat_history
charts_collection = db.charts
structured_plans_collection = db.structured_plans
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
    file_id: str

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
        
        # Store metadata
        metadata = {
            "file_id": file_id,
            "filename": file.filename,
            "upload_date": datetime.now(),
            "file_size": len(content),
            "status": "uploaded",
            "total_rows": len(df),
            "columns": preview_columns
        }
        
        files_collection.insert_one(metadata)
        
        return {
            "file_id": file_id,
            "filename": file.filename,
            "status": "uploaded",
            "total_rows": len(df),
            "columns": preview_columns
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
        
        # Delete chat history
        chat_collection.delete_many({"file_id": file_id})
        
        return {"message": "File deleted successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")

@app.post("/api/chat/{file_id}")
async def chat_with_csv(file_id: str, message: ChatMessage):
    """Chat with CSV data using PandasAI and OpenAI"""
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
        
        # For large datasets, consider sampling for performance
        if len(df) > 50000:
            # Use a representative sample for very large datasets to improve performance
            sample_size = min(50000, int(len(df) * 0.1))  # 10% or 50k max
            df = df.sample(n=sample_size, random_state=42)
        
        # Store user message in chat history
        user_question = message.message
        chat_collection.insert_one({
            "file_id": file_id,
            "message": user_question,
            "sender": "user",
            "timestamp": datetime.now()
        })
        
        # Track if a chart is generated
        chart_data = None
        chart_type = None
        response = None
        
        # Check if we should generate a visualization based on keywords
        should_visualize = any(keyword in user_question.lower() for keyword in 
                               ['chart', 'graph', 'plot', 'visualization', 'visualize',
                                'bar', 'line', 'pie', 'scatter', 'histogram', 'distribution',
                                'trend', 'compare', 'correlation', 'show me', 'display'])
        
        try:
            # Use PandasAI if available
            if PANDASAI_AVAILABLE:
                # Custom path for saving charts
                charts_dir = pathlib.Path(CHARTS_EXPORT_PATH)
                charts_dir.mkdir(parents=True, exist_ok=True)
                
                # Initialize OpenAI LLM for PandasAI
                llm = OpenAI(api_token=OPENAI_API_KEY, model="gpt-4")
                
                # Configure PandasAI with chart saving
                config = {
                    "llm": llm,
                    "verbose": True,
                    "save_charts": True,
                    "save_charts_path": str(charts_dir),
                    "enable_cache": False,
                    "custom_instructions": """
                    When generating charts:
                    1. Use appropriate visualizations for the data type
                    2. Ensure proper titles, labels, and legends
                    3. Choose suitable color schemes for readability
                    4. For time series, use line charts
                    5. For categorical comparisons, use bar charts
                    6. For distributions, use histograms or box plots
                    7. For relationships between variables, use scatter plots
                    8. For proportions, use pie charts or donut charts
                    9. Add insights in the response about what the visualization shows
                    """
                }
                
                # Create SmartDataframe with the configuration
                smart_df = SmartDataframe(df, config=config)
                
                # Run the query
                with get_openai_callback() as cb:
                    # Force generation of charts if requested
                    if should_visualize and not any(viz_command in user_question.lower() for viz_command in ['generate', 'create', 'plot', 'show']):
                        enhanced_question = f"Generate a visualization for: {user_question}"
                        response = smart_df.chat(enhanced_question)
                    else:
                        response = smart_df.chat(user_question)
                    print(f"Tokens used: {cb.total_tokens}, Cost: ${cb.total_cost}")
                
                # Check if PandasAI generated any charts
                chart_files = list(charts_dir.glob("temp_chart_*.png"))
                
                if chart_files:
                    # Use the latest chart (if multiple were generated)
                    latest_chart = max(chart_files, key=lambda x: x.stat().st_mtime)
                    
                    # Upload chart to Cloudinary
                    chart_id = str(uuid.uuid4())
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    chart_filename = f"pandasai_{chart_id}_{timestamp}"
                    
                    cloudinary_response = cloudinary.uploader.upload(
                        str(latest_chart),
                        public_id=chart_filename,
                        folder="csv_charts",
                        overwrite=True
                    )
                    
                    # Set chart data and type for response
                    chart_data = cloudinary_response['secure_url']
                    chart_type = "image_url"
                    
                    # Store chart metadata in database
                    charts_collection.insert_one({
                        "file_id": file_id,
                        "chart_url": chart_data,
                        "chart_type": chart_type,
                        "question": user_question,
                        "created_at": datetime.now()
                    })
                    
                    # Delete the temporary file
                    latest_chart.unlink(missing_ok=True)
                
                # If response is not a string, convert it
                if not isinstance(response, str):
                    if hasattr(response, 'to_string'):
                        response = response.to_string()
                    else:
                        response = str(response)
                
            else:
                # PandasAI not available, use fallback
                raise ImportError("PandasAI not available")
                
        except Exception as pandas_ai_error:
            print(f"PandasAI error or not available: {str(pandas_ai_error)}")
            # Use enhanced fallback approach
            response = await enhanced_csv_analysis(df, user_question)
            
            # Try to generate charts if requested
            if should_visualize:
                chart_data, chart_type = await generate_simple_chart(df, user_question)
        
        # Store AI response in chat history
        chat_collection.insert_one({
            "file_id": file_id,
            "message": response,
            "sender": "ai",
            "timestamp": datetime.now(),
            "chart_data": chart_data,
            "chart_type": chart_type
        })
        
        return ChatResponse(
            response=response,
            chart_data=chart_data,
            chart_type=chart_type
        )
        
    except Exception as e:
        # Ultimate fallback
        error_response = f"I apologize, but I encountered an error processing your question: {str(e)}. Here's what I can tell you about your data: The dataset has {df.shape[0] if 'df' in locals() else 'unknown'} rows and {df.shape[1] if 'df' in locals() else 'unknown'} columns."
        
        chat_collection.insert_one({
            "file_id": file_id,
            "message": error_response,
            "sender": "ai",
            "timestamp": datetime.now()
        })
        
        return ChatResponse(
            response=error_response,
            chart_data=None,
            chart_type=None
        )

async def generate_simple_chart(df: pd.DataFrame, question: str) -> tuple:
    """Generate simple charts based on the question and save to Cloudinary"""
    try:
        chart_data = None
        chart_type = None
        
        # Check if we should generate a visualization based on keywords
        should_visualize = any(keyword in question.lower() for keyword in 
                               ['chart', 'graph', 'plot', 'visualization', 'visualize',
                                'bar', 'line', 'pie', 'scatter', 'histogram', 'distribution',
                                'trend', 'compare', 'correlation', 'show me', 'display'])
        
        # Get numeric and categorical columns
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        date_cols = []
        
        # Check for potential date columns
        for col in df.columns:
            try:
                if df[col].dtype == 'object':
                    # Try to parse as datetime
                    pd.to_datetime(df[col], errors='raise')
                    date_cols.append(col)
            except:
                pass
        
        # Generate filename for chart
        chart_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        chart_filename = f"chart_{chart_id}_{timestamp}"
        local_path = os.path.join(CHARTS_EXPORT_PATH, f"{chart_filename}.png")
        
        # Parse the question for better chart selection
        question_lower = question.lower()
        
        # Try to identify relevant columns from question
        mentioned_cols = []
        for col in df.columns:
            if col.lower() in question_lower:
                mentioned_cols.append(col)
        
        # Select appropriate columns based on question and column mentions
        target_cat_col = None
        target_num_col = None
        
        # Prioritize mentioned columns first
        if mentioned_cols:
            for col in mentioned_cols:
                if col in categorical_cols:
                    target_cat_col = col
                elif col in numeric_cols:
                    target_num_col = col
        
        # Fall back to first columns if no mentions found
        if not target_cat_col and categorical_cols:
            target_cat_col = categorical_cols[0]
        if not target_num_col and numeric_cols:
            target_num_col = numeric_cols[0]
        
        # Create appropriate chart based on the request
        if ('bar' in question_lower or 'compare' in question_lower) and target_cat_col and target_num_col:
            # Create bar chart
            # Group by category and aggregate
            if 'average' in question_lower or 'mean' in question_lower:
                grouped = df.groupby(target_cat_col)[target_num_col].mean().nlargest(10)
                agg_type = 'Average'
            elif 'count' in question_lower:
                grouped = df.groupby(target_cat_col).size().nlargest(10)
                agg_type = 'Count'
            else:
                grouped = df.groupby(target_cat_col)[target_num_col].sum().nlargest(10)
                agg_type = 'Sum'
            
            fig = px.bar(
                x=grouped.index, 
                y=grouped.values,
                labels={'x': target_cat_col, 'y': f'{agg_type} of {target_num_col}'},
                title=f'{target_cat_col} vs {agg_type} of {target_num_col}'
            )
            
            # Enhance aesthetics
            fig.update_layout(
                xaxis_title=target_cat_col,
                yaxis_title=f'{agg_type} of {target_num_col}',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(
                    showgrid=False,
                    showline=True,
                    linewidth=1,
                    linecolor='lightgray'
                ),
                yaxis=dict(
                    showgrid=True,
                    gridwidth=1,
                    gridcolor='lightgray'
                ),
                margin=dict(l=40, r=40, t=50, b=40),
            )
            
            # Save locally first
            fig.write_image(local_path)
            
        elif ('pie' in question_lower or 'distribution' in question_lower or 'breakdown' in question_lower) and target_cat_col:
            # Create pie chart
            value_counts = df[target_cat_col].value_counts().head(10)
            
            fig = px.pie(
                values=value_counts.values,
                names=value_counts.index,
                title=f'Distribution of {target_cat_col}'
            )
            
            # Enhance aesthetics
            fig.update_layout(
                legend_title=target_cat_col,
                margin=dict(l=40, r=40, t=50, b=40)
            )
            
            # Save locally first
            fig.write_image(local_path)
            
        elif ('line' in question_lower or 'trend' in question_lower or 'time' in question_lower or 'over time' in question_lower):
            # Try to create line chart - prioritize date columns if available
            x_col = None
            
            # Find appropriate x-axis (prefer date columns)
            if date_cols:
                x_col = date_cols[0]
                # Convert to datetime
                df[x_col] = pd.to_datetime(df[x_col], errors='coerce')
                # Sort by date
                df = df.sort_values(by=x_col)
            elif target_num_col and len(numeric_cols) > 1:
                # Use another numeric column
                others = [col for col in numeric_cols if col != target_num_col]
                x_col = others[0]
            elif numeric_cols:
                # Fall back to index
                x_col = df.index.name or 'Index'
                df['Index'] = df.index
            
            if x_col and target_num_col:
                # Create line chart
                fig = px.line(
                    df.head(100), 
                    x=x_col, 
                    y=target_num_col, 
                    title=f'{target_num_col} Trend',
                    markers=True
                )
                
                # Enhance aesthetics
                fig.update_layout(
                    xaxis_title=x_col,
                    yaxis_title=target_num_col,
                    plot_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(
                        showgrid=False,
                        showline=True,
                        linewidth=1,
                        linecolor='lightgray'
                    ),
                    yaxis=dict(
                        showgrid=True,
                        gridwidth=1,
                        gridcolor='lightgray'
                    ),
                    margin=dict(l=40, r=40, t=50, b=40),
                )
                
                # Save locally first
                fig.write_image(local_path)
            
        elif ('scatter' in question_lower or 'correlation' in question_lower or 'relationship' in question_lower) and len(numeric_cols) >= 2:
            # For scatter plots, we need two numeric columns
            if target_num_col:
                # Find another numeric column different from target_num_col
                secondary_num_col = next((col for col in numeric_cols if col != target_num_col), None)
                if secondary_num_col:
                    # Create scatter plot with color by category if available
                    if target_cat_col:
                        fig = px.scatter(
                            df, 
                            x=target_num_col, 
                            y=secondary_num_col, 
                            color=target_cat_col,
                            title=f'Correlation: {target_num_col} vs {secondary_num_col}',
                            opacity=0.7
                        )
                    else:
                        fig = px.scatter(
                            df, 
                            x=target_num_col, 
                            y=secondary_num_col, 
                            title=f'Correlation: {target_num_col} vs {secondary_num_col}',
                            opacity=0.7
                        )
                    
                    # Enhance aesthetics
                    fig.update_layout(
                        xaxis_title=target_num_col,
                        yaxis_title=secondary_num_col,
                        plot_bgcolor='rgba(0,0,0,0)',
                        xaxis=dict(
                            showgrid=True,
                            gridwidth=1,
                            gridcolor='lightgray'
                        ),
                        yaxis=dict(
                            showgrid=True,
                            gridwidth=1,
                            gridcolor='lightgray'
                        ),
                        margin=dict(l=40, r=40, t=50, b=40),
                    )
                    
                    # Save locally first
                    fig.write_image(local_path)
            
        elif ('histogram' in question_lower or 'distribution' in question_lower) and target_num_col:
            # Create histogram for numeric column
            fig = px.histogram(
                df, 
                x=target_num_col,
                nbins=20,
                title=f'Distribution of {target_num_col}'
            )
            
            # Enhance aesthetics
            fig.update_layout(
                xaxis_title=target_num_col,
                yaxis_title="Count",
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(
                    showgrid=False,
                    showline=True,
                    linewidth=1,
                    linecolor='lightgray'
                ),
                yaxis=dict(
                    showgrid=True,
                    gridwidth=1,
                    gridcolor='lightgray'
                ),
                margin=dict(l=40, r=40, t=50, b=40),
            )
            
            # Save locally first
            fig.write_image(local_path)
            
        # Default chart if no specific chart type was identified but visualization is requested
        elif should_visualize and numeric_cols and categorical_cols:
            # Default to a bar chart with the first categorical and numeric columns
            cat_col = categorical_cols[0]
            num_col = numeric_cols[0]
            
            grouped = df.groupby(cat_col)[num_col].sum().nlargest(10)
            
            fig = px.bar(
                x=grouped.index, 
                y=grouped.values,
                labels={'x': cat_col, 'y': f'Sum of {num_col}'},
                title=f'{cat_col} vs {num_col}'
            )
            
            # Enhance aesthetics
            fig.update_layout(
                xaxis_title=cat_col,
                yaxis_title=f'Sum of {num_col}',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=40, r=40, t=50, b=40),
            )
            
            # Save locally first
            fig.write_image(local_path)
        
        # Upload to Cloudinary if a chart was created
        if os.path.exists(local_path):
            cloudinary_response = cloudinary.uploader.upload(
                local_path,
                public_id=chart_filename,
                folder="csv_charts",
                overwrite=True
            )
            
            chart_data = cloudinary_response['secure_url']
            chart_type = "image_url"
            
            # Clean up local file after upload
            os.remove(local_path)
            
        return chart_data, chart_type
        
    except Exception as e:
        print(f"Chart generation error: {e}")
        return None, None

async def enhanced_csv_analysis(df: pd.DataFrame, question: str) -> str:
    """Enhanced fallback analysis using OpenAI with detailed data context"""
    try:
        # Prepare comprehensive data summary
        # Handle NaN values in sample data
        sample_df = df.head(3).fillna("")
        
        data_summary = {
            "shape": f"{df.shape[0]} rows, {df.shape[1]} columns",
            "columns": df.columns.tolist(),
            "data_types": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "missing_values": df.isnull().sum().to_dict(),
            "sample_data": sample_df.to_dict('records')
        }
        
        # Add statistical summary for numeric columns
        numeric_cols = df.select_dtypes(include=['number']).columns
        if len(numeric_cols) > 0:
            data_summary["statistics"] = df[numeric_cols].describe().to_dict()
        
        # Add value counts for categorical columns
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns
        categorical_info = {}
        for col in categorical_cols[:3]:  # Limit to first 3 categorical columns
            value_counts = df[col].value_counts().head(5).to_dict()
            categorical_info[col] = value_counts
        data_summary["categorical_summary"] = categorical_info
        
        # Detect visualization intent
        should_visualize = any(keyword in question.lower() for keyword in 
                          ['chart', 'graph', 'plot', 'visualization', 'visualize',
                           'bar', 'line', 'pie', 'scatter', 'histogram', 'distribution',
                           'trend', 'compare', 'correlation', 'show me', 'display'])
        
        # Create comprehensive prompt
        prompt = f"""
        You are a data analyst assistant. Analyze this CSV dataset and answer the user's question comprehensively.

        Dataset Information:
        - Size: {data_summary['shape']}
        - Columns: {', '.join(data_summary['columns'])}
        - Data Types: {data_summary['data_types']}
        - Missing Values: {data_summary['missing_values']}
        
        Sample Data (first 3 rows):
        {json.dumps(data_summary['sample_data'], indent=2)}
        
        Statistical Summary (numeric columns):
        {json.dumps(data_summary.get('statistics', {}), indent=2)}
        
        Categorical Data Summary:
        {json.dumps(data_summary['categorical_summary'], indent=2)}

        User Question: "{question}"

        {'In addition to answering the question, I will generate a visualization to help illustrate the answer.' if should_visualize else ''}
        
        Provide a helpful, detailed answer based on the data. If the question asks for specific calculations, provide estimates based on the sample data and statistics. If asking for visualizations, mention that a chart will be generated separately.
        """
        
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful data analyst assistant. Provide clear, actionable insights about the dataset."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.3
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"I can see your dataset has {df.shape[0]} rows and {df.shape[1]} columns with these columns: {', '.join(df.columns.tolist())}. However, I encountered an error analyzing it in detail: {str(e)}"

@app.get("/api/chat-history/{file_id}")
async def get_chat_history(file_id: str):
    """Get chat history for a specific file"""
    try:
        messages = list(chat_collection.find(
            {"file_id": file_id},
            {"_id": 0}
        ).sort("timestamp", 1))
        
        # Convert datetime to ISO string
        for message in messages:
            if 'timestamp' in message:
                message['timestamp'] = message['timestamp'].isoformat()
        
        return {"messages": messages}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching chat history: {str(e)}")

@app.delete("/api/chat-history/{file_id}")
async def clear_chat_history(file_id: str):
    """Clear chat history for a specific file"""
    try:
        chat_collection.delete_many({"file_id": file_id})
        return {"message": "Chat history cleared successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing chat history: {str(e)}")

# Add a new endpoint for retrieving charts by file_id
@app.get("/api/charts/{file_id}")
async def get_charts(file_id: str):
    """Get all charts generated for a specific file"""
    try:
        charts = list(charts_collection.find(
            {"file_id": file_id},
            {"_id": 0}
        ).sort("created_at", -1))
        
        # Convert datetime to ISO string
        for chart in charts:
            if 'created_at' in chart:
                chart['created_at'] = chart['created_at'].isoformat()
        
        return {"charts": charts}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching charts: {str(e)}")

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

@app.post("/api/structured-plans/save/{file_id}")
async def save_structured_plan(file_id: str, plan_data: Dict[str, Any]):
    """Save a structured plan from group management data"""
    try:
        # Get current group data
        group_doc = group_management_collection.find_one({"file_id": file_id})
        if not group_doc:
            raise HTTPException(status_code=404, detail="Group management data not found")
        
        groups_data = group_doc["groups_data"]
        
        # Create structured plan
        structured_plan = grouping_engine.create_structured_plan(groups_data)
        structured_plan["name"] = plan_data.get("name", structured_plan["name"])
        structured_plan["description"] = plan_data.get("description", "")
        
        # Save to database
        plan_doc = {
            "plan_id": structured_plan["id"],
            "file_id": file_id,
            "plan_data": structured_plan,
            "created_at": datetime.now()
        }
        
        structured_plans_collection.insert_one(plan_doc)
        
        return {"message": "Structured plan saved successfully", "plan_id": structured_plan["id"]}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving structured plan: {str(e)}")

@app.get("/api/structured-plans")
async def get_structured_plans():
    """Get all available structured plans"""
    try:
        plans = list(structured_plans_collection.find({}, {"_id": 0, "plan_data": 1, "created_at": 1}))
        
        # Convert datetime to ISO string and extract basic info
        plan_list = []
        for plan_doc in plans:
            plan_data = plan_doc["plan_data"]
            plan_list.append({
                "id": plan_data["id"],
                "name": plan_data["name"],
                "description": plan_data.get("description", ""),
                "created_at": plan_doc["created_at"].isoformat(),
                "version": plan_data.get("version", "1.0"),
                "total_groups": len(plan_data.get("main_groups", {}))
            })
        
        return {"plans": plan_list}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching structured plans: {str(e)}")

@app.get("/api/structured-plans/{plan_id}")
async def get_structured_plan(plan_id: str):
    """Get a specific structured plan"""
    try:
        plan_doc = structured_plans_collection.find_one({"plan_data.id": plan_id}, {"_id": 0})
        
        if not plan_doc:
            raise HTTPException(status_code=404, detail="Structured plan not found")
        
        # Convert datetime to ISO string
        if 'created_at' in plan_doc:
            plan_doc['created_at'] = plan_doc['created_at'].isoformat()
        
        return plan_doc["plan_data"]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching structured plan: {str(e)}")

@app.post("/api/structured-plans/apply/{file_id}/{plan_id}")
async def apply_structured_plan(file_id: str, plan_id: str):
    """Apply a structured plan to a CSV file"""
    try:
        # Get the structured plan
        plan_doc = structured_plans_collection.find_one({"plan_data.id": plan_id})
        if not plan_doc:
            raise HTTPException(status_code=404, detail="Structured plan not found")
        
        plan_data = plan_doc["plan_data"]
        
        # Get the CSV file
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
        
        # Apply structured plan
        groups_data = grouping_engine.apply_structured_plan(df, plan_data)
        
        # Store in database
        group_doc = {
            "file_id": file_id,
            "groups_data": groups_data,
            "created_at": datetime.now(),
            "type": "structured_plan_applied",
            "plan_id": plan_id
        }
        
        # Remove existing group management data for this file
        group_management_collection.delete_many({"file_id": file_id})
        
        # Insert new data
        result = group_management_collection.insert_one(group_doc)
        groups_data["management_id"] = str(result.inserted_id)
        
        return groups_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error applying structured plan: {str(e)}")

@app.delete("/api/structured-plans/{plan_id}")
async def delete_structured_plan(plan_id: str):
    """Delete a structured plan"""
    try:
        result = structured_plans_collection.delete_one({"plan_data.id": plan_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Structured plan not found")
        
        return {"message": "Structured plan deleted successfully"}
        
    except Exception as e:
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
        # Create the saved group document
        saved_group_doc = {
            "name": data.name,
            "description": data.description,
            "structured_results": data.structured_results,
            "file_id": data.file_id,
            "created_at": data.created_at,
            "saved_at": datetime.now().isoformat()
        }
        
        # Save to database
        result = saved_groups_collection.insert_one(saved_group_doc)
        
        return {
            "status": "success",
            "message": "Group saved successfully",
            "group_id": str(result.inserted_id)
        }
        
    except Exception as e:
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

if __name__ == "__main__":
    import uvicorn
    
    # Check environment variables and display status
    env_vars = {
        "MONGO_URL": MONGO_URL,
        "DB_NAME": DB_NAME,
        "OPENAI_API_KEY": "✓ Set" if OPENAI_API_KEY else "❌ Missing",
        "CLOUDINARY_CONFIG": "✓ Set" if cloudinary.config().cloud_name else "❌ Missing",
        "PANDASAI_AVAILABLE": "✓ Available" if PANDASAI_AVAILABLE else "❌ Not available"
    }
    
    print("\n=== CSV Processing Dashboard Backend ===")
    print(f"MongoDB connection: {'✓ Connected' if client else '❌ Not connected'}")
    print(f"Database: {DB_NAME}")
    print(f"PandasAI: {env_vars['PANDASAI_AVAILABLE']}")
    print(f"OpenAI API Key: {env_vars['OPENAI_API_KEY']}")
    print(f"Cloudinary: {env_vars['CLOUDINARY_CONFIG']}")
    print(f"Charts export path: {CHARTS_EXPORT_PATH}")
    print("=====================================\n")
    print("To run the server, use:")
    print("uvicorn server:app --reload --port 8000")
    print("or")
    print("python server.py")
    print("=====================================\n")
    
    # Run the server
    uvicorn.run(app, host="0.0.0.0", port=8000)