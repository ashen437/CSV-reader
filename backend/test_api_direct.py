#!/usr/bin/env python3
"""
Test the API endpoint with the test server
"""
import requests
import json
import time

def test_api():
    """Test the API endpoints"""
    base_url = "http://localhost:8000"
    
    # Wait a moment for server to start
    print("Waiting for server to start...")
    time.sleep(3)
    
    # Test root endpoint
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ Server returned {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return
    
    # Test chat endpoint
    file_id = "f2ced5ba-ea1e-489e-b28e-b058ee4c672b"
    chat_url = f"{base_url}/api/chat/{file_id}"
    
    test_payloads = [
        {"message": "Show me a summary"},
        {"message": "Create a chart"},
        {"message": "What data do you have?"}
    ]
    
    for i, payload in enumerate(test_payloads, 1):
        print(f"\n{i}. Testing chat with: {payload}")
        try:
            response = requests.post(chat_url, json=payload, timeout=10)
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ Success!")
                data = response.json()
                print(f"Response: {data['response']}")
            elif response.status_code == 422:
                print("❌ 422 Error!")
                error = response.json()
                print(f"Error detail: {error}")
            else:
                print(f"❌ Unexpected status: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")
    
    # Test files endpoint
    print(f"\n4. Testing files endpoint...")
    try:
        response = requests.get(f"{base_url}/api/files", timeout=5)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Files endpoint works!")
            files = response.json()
            print(f"Files: {files}")
        else:
            print(f"❌ Files endpoint failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Files request failed: {e}")

if __name__ == "__main__":
    test_api()
