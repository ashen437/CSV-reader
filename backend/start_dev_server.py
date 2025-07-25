#!/usr/bin/env python3
"""
Development server startup script with health checks
"""

import os
import sys
import time
import subprocess
import requests
from pathlib import Path

def check_env_file():
    """Check if .env file exists and has required variables"""
    env_path = Path(".env")
    if not env_path.exists():
        print("❌ .env file not found!")
        print("📝 Please copy .env.example to .env and fill in your configuration:")
        print("   cp .env.example .env")
        return False
    
    # Check for required environment variables
    required_vars = ["MONGO_URL", "DB_NAME", "OPENAI_API_KEY"]
    missing_vars = []
    
    with open(env_path) as f:
        env_content = f.read()
        for var in required_vars:
            if f"{var}=" not in env_content or f"{var}=your_" in env_content:
                missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing or incomplete environment variables: {', '.join(missing_vars)}")
        print("📝 Please update your .env file with actual values")
        return False
    
    print("✅ Environment file configured")
    return True

def check_dependencies():
    """Check if required packages are installed"""
    print("🔄 Checking dependencies...")
    
    required_packages = [
        ("fastapi", "FastAPI web framework"),
        ("uvicorn", "ASGI server"),
        ("pandas", "Data processing"),
        ("pymongo", "MongoDB driver"),
        ("openai", "OpenAI API client"),
        ("plotly", "Chart generation"),
        ("matplotlib", "Chart generation"),
    ]
    
    missing_packages = []
    
    for package, description in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append((package, description))
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package, desc in missing_packages:
            print(f"   - {package}: {desc}")
        print("\n📦 Install missing packages with:")
        print(f"   pip install {' '.join(pkg for pkg, _ in missing_packages)}")
        return False
    
    print("✅ All required dependencies are installed")
    return True

def check_mongodb():
    """Check if MongoDB is accessible"""
    print("🔄 Checking MongoDB connection...")
    
    try:
        from pymongo import MongoClient
        from dotenv import load_dotenv
        
        load_dotenv()
        mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017/")
        
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=3000)
        client.server_info()  # This will raise an exception if MongoDB is not accessible
        
        print("✅ MongoDB connection successful")
        return True
        
    except Exception as e:
        print(f"❌ MongoDB connection failed: {str(e)}")
        print("💡 Make sure MongoDB is running:")
        print("   - Install MongoDB: https://docs.mongodb.com/manual/installation/")
        print("   - Start MongoDB service")
        print("   - Or use MongoDB Atlas (cloud): https://www.mongodb.com/cloud/atlas")
        return False

def start_server():
    """Start the FastAPI server"""
    print("🚀 Starting CSV Chat Server...")
    
    try:
        # Start the server
        cmd = [sys.executable, "-m", "uvicorn", "server:app", "--reload", "--port", "8000", "--host", "0.0.0.0"]
        print(f"🔧 Command: {' '.join(cmd)}")
        
        process = subprocess.Popen(cmd)
        
        # Wait a moment for server to start
        time.sleep(3)
        
        # Check if server is responding
        try:
            response = requests.get("http://localhost:8000/", timeout=5)
            if response.status_code == 200:
                print("✅ Server started successfully!")
                print("🌐 Server running at: http://localhost:8000")
                print("📚 API docs available at: http://localhost:8000/docs")
                print("\n🎯 You can now:")
                print("   - Test the API endpoints")
                print("   - Run the test script: python test_chat_system.py")
                print("   - Access the frontend (if available)")
                print("\n⏹️  Press Ctrl+C to stop the server")
                
                # Keep the server running
                try:
                    process.wait()
                except KeyboardInterrupt:
                    print("\n🛑 Shutting down server...")
                    process.terminate()
                    process.wait()
                    print("✅ Server stopped")
                    
            else:
                print(f"❌ Server responded with status {response.status_code}")
                process.terminate()
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Server health check failed: {str(e)}")
            process.terminate()
            
    except Exception as e:
        print(f"❌ Failed to start server: {str(e)}")

def main():
    """Main startup routine"""
    print("🔧 CSV Chat System - Development Server")
    print("=" * 50)
    
    # Check prerequisites
    if not check_env_file():
        return
        
    if not check_dependencies():
        return
        
    if not check_mongodb():
        return
    
    # Start server
    start_server()

if __name__ == "__main__":
    main()
