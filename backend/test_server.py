#!/usr/bin/env python3
"""
Simple server test - no MongoDB required
"""
import asyncio
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Create a minimal test app
app = FastAPI(title="Test CSV API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    chart_data: str = None
    chart_type: str = None

@app.get("/")
async def root():
    return {"message": "Test API is running"}

@app.post("/api/chat/{file_id}")
async def test_chat(file_id: str, message: ChatMessage):
    """Test chat endpoint without database dependencies"""
    return ChatResponse(
        response=f"Test response for file {file_id}: {message.message}",
        chart_data=None,
        chart_type=None
    )

@app.get("/api/files")
async def test_files():
    """Test files endpoint"""
    return [
        {
            "file_id": "f2ced5ba-ea1e-489e-b28e-b058ee4c672b",
            "filename": "Data.csv",
            "status": "uploaded",
            "total_rows": 100,
            "columns": ["col1", "col2"]
        }
    ]

if __name__ == "__main__":
    print("Starting test server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
