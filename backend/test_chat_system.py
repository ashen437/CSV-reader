#!/usr/bin/env python3
"""
Test script for CSV Chat System
Tests the chat functionality, chart generation, and file handling
"""

import requests
import json
import io
import pandas as pd
import time

# Configuration
BASE_URL = "http://localhost:8000"

def test_file_upload():
    """Test CSV file upload"""
    print("🔄 Testing file upload...")
    
    # Create a sample CSV file
    sample_data = {
        'Product': ['iPhone 14', 'Samsung Galaxy S23', 'MacBook Pro', 'Dell Laptop', 'iPad Air', 'Surface Pro'],
        'Category': ['Electronics', 'Electronics', 'Computers', 'Computers', 'Tablets', 'Tablets'],
        'Price': [999, 849, 2399, 1299, 599, 1199],
        'Sales': [1500, 1200, 800, 900, 1100, 700],
        'Rating': [4.5, 4.3, 4.8, 4.2, 4.6, 4.1]
    }
    
    df = pd.DataFrame(sample_data)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_content = csv_buffer.getvalue()
    
    # Upload file
    files = {'file': ('test_data.csv', csv_content, 'text/csv')}
    response = requests.post(f"{BASE_URL}/api/upload-csv", files=files)
    
    if response.status_code == 200:
        file_data = response.json()
        print(f"✅ File uploaded successfully: {file_data['file_id']}")
        return file_data['file_id']
    else:
        print(f"❌ File upload failed: {response.status_code} - {response.text}")
        return None

def test_chat_functionality(file_id):
    """Test chat with CSV functionality"""
    print(f"🔄 Testing chat functionality for file: {file_id}")
    
    # Test questions for different chart types
    test_questions = [
        {
            "question": "Create a bar chart showing sales by category",
            "expected_type": "chart",
            "description": "Bar chart request"
        },
        {
            "question": "What are the top 3 products by price?",
            "expected_type": "table", 
            "description": "Table data request"
        },
        {
            "question": "Show me a pie chart of product categories",
            "expected_type": "chart",
            "description": "Pie chart request"
        },
        {
            "question": "Tell me the average rating for each category",
            "expected_type": "table",
            "description": "Analysis request"
        },
        {
            "question": "Create a scatter plot of price vs rating",
            "expected_type": "chart",
            "description": "Scatter plot request"
        }
    ]
    
    results = []
    
    for i, test in enumerate(test_questions):
        print(f"\n📝 Test {i+1}: {test['description']}")
        print(f"   Question: {test['question']}")
        
        # Send chat message
        chat_data = {"message": test["question"], "file_id": file_id}
        response = requests.post(f"{BASE_URL}/api/chat/{file_id}", json=chat_data)
        
        if response.status_code == 200:
            result = response.json()
            
            # Check response
            has_chart = bool(result.get('chart_data'))
            has_response = bool(result.get('response'))
            chart_type = result.get('chart_type')
            
            print(f"   ✅ Response received")
            print(f"   📊 Chart generated: {'Yes' if has_chart else 'No'}")
            print(f"   💬 Text response: {'Yes' if has_response else 'No'}")
            if chart_type:
                print(f"   🎨 Chart type: {chart_type}")
            
            # Validate expected behavior
            if test['expected_type'] == 'chart':
                success = has_chart and chart_type
                print(f"   {'✅' if success else '❌'} Chart expectation: {'Met' if success else 'Not met'}")
            else:
                success = has_response and not (has_chart and 'chart' in test['question'].lower())
                print(f"   {'✅' if success else '❌'} Table/Text expectation: {'Met' if success else 'Not met'}")
            
            results.append({
                "question": test["question"],
                "expected": test["expected_type"],
                "has_chart": has_chart,
                "has_response": has_response,
                "chart_type": chart_type,
                "success": success
            })
            
        else:
            print(f"   ❌ Chat request failed: {response.status_code} - {response.text}")
            results.append({
                "question": test["question"],
                "expected": test["expected_type"],
                "success": False,
                "error": f"HTTP {response.status_code}"
            })
        
        # Wait between requests
        time.sleep(1)
    
    return results

def test_chat_history(file_id):
    """Test chat history retrieval"""
    print(f"\n🔄 Testing chat history for file: {file_id}")
    
    response = requests.get(f"{BASE_URL}/api/chat-history/{file_id}")
    
    if response.status_code == 200:
        history = response.json()
        print(f"✅ Chat history retrieved: {len(history)} messages")
        
        # Check for user and AI messages
        user_messages = [msg for msg in history if msg.get('sender') == 'user']
        ai_messages = [msg for msg in history if msg.get('sender') == 'ai']
        
        print(f"   👤 User messages: {len(user_messages)}")
        print(f"   🤖 AI messages: {len(ai_messages)}")
        
        return True
    else:
        print(f"❌ Chat history retrieval failed: {response.status_code}")
        return False

def test_charts_endpoint(file_id):
    """Test charts endpoint"""
    print(f"\n🔄 Testing charts endpoint for file: {file_id}")
    
    response = requests.get(f"{BASE_URL}/api/charts/{file_id}")
    
    if response.status_code == 200:
        charts_data = response.json()
        charts = charts_data.get('charts', [])
        print(f"✅ Charts endpoint working: {len(charts)} charts found")
        
        for i, chart in enumerate(charts):
            print(f"   📊 Chart {i+1}: {chart.get('chart_type', 'unknown')} - {chart.get('question', 'No question')}")
        
        return True
    else:
        print(f"❌ Charts endpoint failed: {response.status_code}")
        return False

def test_file_list():
    """Test file listing"""
    print(f"\n🔄 Testing file list endpoint...")
    
    response = requests.get(f"{BASE_URL}/api/files")
    
    if response.status_code == 200:
        files = response.json()
        print(f"✅ File list retrieved: {len(files)} files")
        return True
    else:
        print(f"❌ File list failed: {response.status_code}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting CSV Chat System Tests")
    print("=" * 50)
    
    try:
        # Test 1: File upload
        file_id = test_file_upload()
        if not file_id:
            print("❌ Cannot continue tests without file upload")
            return
        
        # Test 2: Chat functionality
        chat_results = test_chat_functionality(file_id)
        
        # Test 3: Chat history
        test_chat_history(file_id)
        
        # Test 4: Charts endpoint
        test_charts_endpoint(file_id)
        
        # Test 5: File list
        test_file_list()
        
        # Summary
        print("\n" + "=" * 50)
        print("📊 Test Summary")
        print("=" * 50)
        
        if chat_results:
            successful_chats = sum(1 for result in chat_results if result.get('success', False))
            total_chats = len(chat_results)
            
            print(f"Chat Tests: {successful_chats}/{total_chats} successful")
            
            for result in chat_results:
                status = "✅" if result.get('success', False) else "❌"
                error = f" ({result.get('error', 'Failed')})" if not result.get('success', False) else ""
                print(f"  {status} {result['question'][:50]}...{error}")
        
        print("\n🎉 Testing complete!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
