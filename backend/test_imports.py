#!/usr/bin/env python3
"""
Test server imports and configuration
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test if server imports work correctly"""
    try:
        print("Testing server imports...")
        
        # Test basic imports
        from fastapi import FastAPI
        print("✅ FastAPI import successful")
        
        import pandas as pd
        print("✅ Pandas import successful")
        
        from pymongo import MongoClient
        print("✅ PyMongo import successful")
        
        from dotenv import load_dotenv
        print("✅ dotenv import successful")
        
        # Load environment variables
        load_dotenv()
        
        # Check environment variables
        mongo_url = os.getenv("MONGO_URL")
        db_name = os.getenv("DB_NAME")
        openai_key = os.getenv("OPENAI_API_KEY")
        
        if mongo_url:
            print(f"✅ MONGO_URL configured: {mongo_url[:20]}...")
        else:
            print("❌ MONGO_URL not configured")
            
        if db_name:
            print(f"✅ DB_NAME configured: {db_name}")
        else:
            print("❌ DB_NAME not configured")
            
        if openai_key:
            print(f"✅ OPENAI_API_KEY configured: {openai_key[:10]}...")
        else:
            print("❌ OPENAI_API_KEY not configured")
        
        # Test MongoDB connection
        try:
            client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
            client.admin.command('ping')
            print("✅ MongoDB connection successful")
        except Exception as e:
            print(f"❌ MongoDB connection failed: {str(e)}")
        
        # Try to import the server module
        try:
            print("\nTesting server module import...")
            import server
            print("✅ Server module imported successfully")
            
            # Check if the app is created
            if hasattr(server, 'app'):
                print("✅ FastAPI app instance found")
                
                # Get the list of routes
                routes = [route.path for route in server.app.routes]
                print(f"✅ Found {len(routes)} routes:")
                for route in routes[:10]:  # Show first 10 routes
                    print(f"  - {route}")
                if len(routes) > 10:
                    print(f"  ... and {len(routes) - 10} more")
            else:
                print("❌ FastAPI app instance not found")
                
        except Exception as e:
            print(f"❌ Server module import failed: {str(e)}")
            import traceback
            traceback.print_exc()
        
    except Exception as e:
        print(f"❌ Import test failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_imports()
