#!/usr/bin/env python3
"""
Simple server startup script
"""
import subprocess
import sys
import os

def start_server():
    """Start the FastAPI server"""
    try:
        print("Starting FastAPI server...")
        # Change to the correct directory
        os.chdir(r"e:\Communeo\CSV-reader\backend")
        
        # Start the server
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "server:app", 
            "--host", "0.0.0.0", 
            "--port", "8000", 
            "--reload"
        ], check=True)
        
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"Error starting server: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    start_server()
