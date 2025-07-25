#!/usr/bin/env python3
"""
Test script for the chat endpoint to debug 422 errors
"""

import requests
import json
import sys

def test_chat_endpoint():
    """Test the chat endpoint with proper payload"""
    
    # API endpoint
    base_url = "http://localhost:8000"
    file_id = "f2ced5ba-ea1e-489e-b28e-b058ee4c672b"  # From the error logs
    chat_url = f"{base_url}/api/chat/{file_id}"
    
    # Test payload matching the ChatMessage model
    test_payload = {
        "message": "Show me a summary of the data"
    }
    
    print(f"Testing chat endpoint: {chat_url}")
    print(f"Payload: {json.dumps(test_payload, indent=2)}")
    
    try:
        # Send POST request
        response = requests.post(chat_url, json=test_payload, timeout=30)
        
        print(f"\nResponse Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 422:
            print("\n❌ 422 Unprocessable Entity Error!")
            try:
                error_detail = response.json()
                print(f"Error Detail: {json.dumps(error_detail, indent=2)}")
            except:
                print(f"Raw Response: {response.text}")
        elif response.status_code == 200:
            print("\n✅ Success!")
            try:
                response_data = response.json()
                print(f"Response: {json.dumps(response_data, indent=2)}")
            except:
                print(f"Raw Response: {response.text}")
        else:
            print(f"\n⚠️ Unexpected status code: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.ConnectionError:
        print("\n❌ Connection Error - Is the server running on port 8000?")
    except requests.Timeout:
        print("\n❌ Timeout Error - Server took too long to respond")
    except Exception as e:
        print(f"\n❌ Unexpected Error: {str(e)}")

def test_server_health():
    """Test if the server is running"""
    try:
        response = requests.get("http://localhost:8000/", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running and responding")
            data = response.json()
            print(f"Server response: {data}")
            return True
        else:
            print(f"⚠️ Server responded with status {response.status_code}")
            return False
    except requests.ConnectionError:
        print("❌ Server is not running or not accessible on port 8000")
        return False
    except Exception as e:
        print(f"❌ Error checking server: {str(e)}")
        return False

def test_files_endpoint():
    """Test the files endpoint to check if the file exists"""
    try:
        response = requests.get("http://localhost:8000/api/files", timeout=10)
        if response.status_code == 200:
            files = response.json()
            print(f"✅ Files endpoint working. Found {len(files)} files:")
            for file in files:
                print(f"  - {file.get('filename', 'Unknown')} (ID: {file.get('file_id', 'Unknown')})")
            return files
        else:
            print(f"⚠️ Files endpoint returned status {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error checking files: {str(e)}")
        return []

if __name__ == "__main__":
    print("🧪 Testing Chat Endpoint\n")
    
    # Test server health first
    print("1. Testing server health...")
    if not test_server_health():
        print("\nServer is not running. Please start the server first.")
        sys.exit(1)
    
    print("\n2. Testing files endpoint...")
    files = test_files_endpoint()
    
    print("\n3. Testing chat endpoint...")
    test_chat_endpoint()
    
    print("\n🧪 Test completed!")
