#!/usr/bin/env python3
"""
Quick API validation test without MongoDB
"""

def test_pydantic_models():
    """Test if our Pydantic models work correctly"""
    try:
        from pydantic import BaseModel, ValidationError
        
        # Test the ChatMessage model
        class ChatMessage(BaseModel):
            message: str
        
        # Test valid input
        try:
            valid_message = ChatMessage(message="Hello, how are you?")
            print(f"✅ Valid ChatMessage: {valid_message}")
        except ValidationError as e:
            print(f"❌ Valid ChatMessage failed: {e}")
        
        # Test invalid input (missing message)
        try:
            invalid_message = ChatMessage()
            print(f"❌ Invalid ChatMessage should have failed: {invalid_message}")
        except ValidationError as e:
            print(f"✅ Invalid ChatMessage correctly failed: {e}")
        
        # Test what the frontend might be sending
        frontend_data = {"message": "Show me a summary"}
        try:
            frontend_message = ChatMessage(**frontend_data)
            print(f"✅ Frontend data works: {frontend_message}")
        except ValidationError as e:
            print(f"❌ Frontend data failed: {e}")
        
        # Test with extra fields (what might be causing 422)
        extra_fields_data = {
            "message": "Show me a summary",
            "file_id": "f2ced5ba-ea1e-489e-b28e-b058ee4c672b",
            "extra_field": "should be ignored"
        }
        try:
            extra_message = ChatMessage(**extra_fields_data)
            print(f"✅ Extra fields data works: {extra_message}")
        except ValidationError as e:
            print(f"❌ Extra fields data failed: {e}")
            
    except Exception as e:
        print(f"❌ Model test failed: {e}")

def test_endpoint_signature():
    """Test the endpoint signature"""
    print("\nTesting endpoint signature...")
    print("Expected endpoint: POST /api/chat/{file_id}")
    print("Expected body: { 'message': 'some text' }")
    print("Should return: { 'response': '...', 'chart_data': null, 'chart_type': null }")

if __name__ == "__main__":
    print("🧪 Testing API Validation\n")
    test_pydantic_models()
    test_endpoint_signature()
    print("\n✅ Validation test completed!")
