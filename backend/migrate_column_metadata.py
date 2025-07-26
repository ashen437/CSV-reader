#!/usr/bin/env python3
"""
Migration script to update existing saved groups with column metadata
This script will:
1. Find all saved groups that don't have column metadata
2. Look up their original file metadata
3. Add the column metadata to the saved group documents
"""

import os
import sys
from pymongo import MongoClient
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# MongoDB connection
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DB_NAME", "csv_reader")

def migrate_column_metadata():
    """Migrate existing saved groups to include column metadata"""
    try:
        # Connect to MongoDB
        client = MongoClient(MONGO_URL)
        db = client[DB_NAME]
        saved_groups_collection = db.saved_groups
        files_collection = db.files
        
        print("Starting column metadata migration...")
        print(f"Connected to database: {DB_NAME}")
        
        # Find saved groups without column metadata
        groups_without_metadata = list(saved_groups_collection.find({
            "$or": [
                {"columns_metadata": {"$exists": False}},
                {"columns_metadata": []},
                {"columns_metadata": None}
            ]
        }))
        
        print(f"Found {len(groups_without_metadata)} saved groups without column metadata")
        
        updated_count = 0
        error_count = 0
        
        for group in groups_without_metadata:
            group_id = group.get('_id')
            group_name = group.get('name', 'Unknown')
            file_id = group.get('file_id')
            
            print(f"Processing group: {group_name} (ID: {group_id})")
            
            if not file_id:
                print(f"  - Skipping: No file_id found")
                error_count += 1
                continue
            
            # Find the original file metadata
            file_metadata = files_collection.find_one({"file_id": file_id})
            
            if not file_metadata:
                print(f"  - Warning: Original file metadata not found for file_id: {file_id}")
                error_count += 1
                continue
            
            # Prepare update data
            update_data = {}
            
            # Add column metadata if available
            if file_metadata.get('columns_metadata'):
                update_data['columns_metadata'] = file_metadata['columns_metadata']
                print(f"  - Added {len(file_metadata['columns_metadata'])} column metadata entries")
            
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
                    {"_id": group_id},
                    {"$set": update_data}
                )
                
                if result.modified_count > 0:
                    print(f"  - Successfully updated")
                    updated_count += 1
                else:
                    print(f"  - Warning: Update operation didn't modify document")
                    error_count += 1
            else:
                print(f"  - Warning: No metadata to update")
                error_count += 1
        
        print(f"\nMigration completed:")
        print(f"  - Updated: {updated_count} saved groups")
        print(f"  - Errors: {error_count} saved groups")
        print(f"  - Total processed: {len(groups_without_metadata)} saved groups")
        
        return updated_count, error_count
        
    except Exception as e:
        print(f"Migration failed: {str(e)}")
        return 0, 1

if __name__ == "__main__":
    print("Column Metadata Migration Script")
    print("=" * 40)
    
    # Confirm before running
    response = input("This will update existing saved groups with column metadata. Continue? (y/N): ")
    if response.lower() != 'y':
        print("Migration cancelled")
        sys.exit(0)
    
    updated, errors = migrate_column_metadata()
    
    if errors == 0:
        print("\n✅ Migration completed successfully!")
    else:
        print(f"\n⚠️  Migration completed with {errors} errors")
    
    sys.exit(0 if errors == 0 else 1)
