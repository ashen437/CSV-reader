#!/usr/bin/env python3
"""
Test script for Final Results functionality
"""

import requests
import json

API_BASE_URL = "http://localhost:8000"

def test_final_results_endpoints():
    """Test the new final results endpoints"""
    
    # Test file ID (you'll need to replace this with an actual file ID)
    test_file_id = "test-file-id"
    
    print("Testing Final Results Endpoints...")
    print("=" * 50)
    
    # Test 1: Save final results
    print("1. Testing save final results endpoint...")
    try:
        response = requests.post(f"{API_BASE_URL}/api/final-results/save/{test_file_id}")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("✓ Save endpoint working")
            print(f"Response: {response.json()}")
        else:
            print(f"✗ Save endpoint failed: {response.text}")
    except Exception as e:
        print(f"✗ Save endpoint error: {e}")
    
    print()
    
    # Test 2: Get final results
    print("2. Testing get final results endpoint...")
    try:
        response = requests.get(f"{API_BASE_URL}/api/final-results/{test_file_id}")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("✓ Get endpoint working")
            data = response.json()
            print(f"Response keys: {list(data.keys())}")
        else:
            print(f"✗ Get endpoint failed: {response.text}")
    except Exception as e:
        print(f"✗ Get endpoint error: {e}")
    
    print()
    
    # Test 3: Get structured final results
    print("3. Testing get structured final results endpoint...")
    try:
        response = requests.get(f"{API_BASE_URL}/api/final-results/structured/{test_file_id}")
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            print("✓ Structured endpoint working")
            data = response.json()
            print(f"Response keys: {list(data.keys())}")
            if 'structured_results' in data:
                results = data['structured_results']
                print(f"Total items: {results.get('total_items', 0)}")
                print(f"Total groups: {results.get('total_groups', 0)}")
                print(f"Main groups: {len(results.get('main_groups', []))}")
        else:
            print(f"✗ Structured endpoint failed: {response.text}")
    except Exception as e:
        print(f"✗ Structured endpoint error: {e}")

def test_server_health():
    """Test if server is running"""
    print("Testing server health...")
    try:
        response = requests.get(f"{API_BASE_URL}/")
        if response.status_code == 200:
            print("✓ Server is running")
            return True
        else:
            print(f"✗ Server returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Server not reachable: {e}")
        return False

if __name__ == "__main__":
    print("Final Results API Test")
    print("=" * 30)
    
    if test_server_health():
        test_final_results_endpoints()
    else:
        print("\nPlease start the backend server first:")
        print("cd backend && python server.py")
