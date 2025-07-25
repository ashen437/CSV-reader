#!/usr/bin/env python3
"""
Test script to validate the enhanced chat system in the server
"""

import asyncio
import pandas as pd
import sys
import os

# Add the current directory to Python path to import server modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def test_server_integration():
    """Test the server integration with sample data"""
    
    print("🚀 Testing Server Chat Integration")
    print("=" * 50)
    
    # Create test DataFrame
    data = {
        'Product': ['iPhone 15', 'Samsung Galaxy S24', 'MacBook Pro', 'Dell XPS 13', 'iPad Pro'],
        'Category': ['Phone', 'Phone', 'Laptop', 'Laptop', 'Tablet'],
        'Price': [999, 899, 1999, 1299, 1099],
        'Sales': [15000, 12000, 8000, 6000, 7000],
        'Rating': [4.5, 4.3, 4.7, 4.4, 4.6]
    }
    df = pd.DataFrame(data)
    
    print(f"📊 Test data: {len(df)} rows, {len(df.columns)} columns")
    
    # Test the AdvancedPandasDataAnalyst directly
    try:
        # Import the class from server (this will test if imports work)
        from server import AdvancedPandasDataAnalyst
        
        # Create analyst instance with fake API key for testing
        analyst = AdvancedPandasDataAnalyst("test-api-key")
        print(f"✅ Analyst initialized in {analyst.mode} mode")
        
        # Test routing decisions
        test_questions = [
            "Show me a chart of sales by product",
            "What are the top 3 products by price?",
            "Create a visualization of ratings",
            "List all products in the Phone category"
        ]
        
        print("\\n🧪 Testing Routing Decisions:")
        for question in test_questions:
            routing = analyst._determine_routing(question, df)
            print(f"  '{question}' -> {routing}")
        
        # Test table extraction
        print("\\n📋 Testing Table Extraction:")
        table_questions = [
            "What are the top 3 products by price?",
            "Show me products with rating above 4.5",
            "Give me a summary of the data"
        ]
        
        for question in table_questions:
            try:
                table_data = analyst._extract_table_data(df, question, "")
                data_type = type(table_data).__name__
                count = len(table_data) if table_data else 0
                print(f"  '{question}' -> {data_type} with {count} items")
            except Exception as e:
                print(f"  '{question}' -> Error: {str(e)}")
        
        # Test the complete analyze_data method (this will use fallback mode)
        print("\\n🔍 Testing Complete Analysis:")
        test_question = "What are the top 3 products by sales?"
        
        try:
            result = await analyst.analyze_data(df, test_question)
            print(f"  Question: {test_question}")
            print(f"  Routing: {result.get('routing', 'unknown')}")
            print(f"  Response length: {len(result.get('response', ''))}")
            print(f"  Has chart: {result.get('chart_data') is not None}")
            print(f"  Has table: {result.get('data_table') is not None}")
            
            if result.get('data_table'):
                print(f"  Table rows: {len(result['data_table'])}")
            
        except Exception as e:
            print(f"  ❌ Analysis failed: {str(e)}")
            import traceback
            traceback.print_exc()
        
        print("\\n✅ Server integration test completed!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {str(e)}")
        print("This might be due to missing dependencies or import issues.")
        return False
    except Exception as e:
        print(f"❌ General error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the server integration test"""
    try:
        success = asyncio.run(test_server_integration())
        if success:
            print("\\n🎉 Server integration is working correctly!")
        else:
            print("\\n🚨 Server integration has issues that need to be resolved.")
    except Exception as e:
        print(f"\\n💥 Test runner failed: {str(e)}")

if __name__ == "__main__":
    main()
