#!/usr/bin/env python3

"""
Test script to verify Excel export dependencies and functionality
"""

def test_dependencies():
    """Test if all required dependencies are available"""
    try:
        import pandas as pd
        print("✓ pandas imported successfully")
        
        import openpyxl
        print("✓ openpyxl imported successfully")
        
        from io import BytesIO
        print("✓ BytesIO imported successfully")
        
        # Test basic Excel creation
        df = pd.DataFrame({
            'Column1': ['A', 'B', 'C'],
            'Column2': [1, 2, 3]
        })
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Test', index=False)
        
        output.seek(0)
        size = len(output.getvalue())
        print(f"✓ Created test Excel file: {size} bytes")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_data_structures():
    """Test data structure handling like in the export function"""
    try:
        import pandas as pd
        from io import BytesIO
        
        # Test similar to the export function structure
        test_data = [
            {
                'Main Group': 'Group A',
                'Sub Group': 'Sub A1',
                'Item Name': 'Item 1',
                'Count': 5,
                'Price (sum)': 100.50,
                'Category (majority)': 'Electronics'
            },
            {
                'Main Group': 'Group A', 
                'Sub Group': 'Sub A2',
                'Item Name': 'Item 2',
                'Count': 3,
                'Price (sum)': 75.25,
                'Category (majority)': 'Electronics'
            }
        ]
        
        df = pd.DataFrame(test_data)
        print(f"✓ Created test DataFrame with {len(df)} rows and {len(df.columns)} columns")
        print(f"  Columns: {list(df.columns)}")
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Export Test', index=False)
        
        output.seek(0)
        size = len(output.getvalue())
        print(f"✓ Created export-style Excel file: {size} bytes")
        
        return True
        
    except Exception as e:
        print(f"❌ Data structure test error: {e}")
        return False

if __name__ == "__main__":
    print("Testing Excel export dependencies and functionality...")
    print("=" * 50)
    
    deps_ok = test_dependencies()
    print()
    
    data_ok = test_data_structures()
    print()
    
    if deps_ok and data_ok:
        print("✅ All tests passed! Excel export should work.")
    else:
        print("❌ Some tests failed. Check the errors above.")
