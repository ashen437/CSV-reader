# CSV Reader Backend - Advanced Pandas AI Chat System

## 🎯 Overview

This is a **production-ready FastAPI backend** that provides advanced chat-based data analysis capabilities for CSV files. The system intelligently routes user questions to either generate visualizations (charts) or provide structured data responses, powered by PandasAI and OpenAI.

## ✨ Key Features

### 🤖 **Intelligent Chat Analysis**
- **Smart Routing**: Automatically detects whether user wants visualizations or data tables
- **PandasAI Integration**: Advanced pandas AI for natural language data queries  
- **OpenAI Fallback**: Robust fallback analysis when PandasAI is unavailable
- **Multi-format Support**: Handles various question types and response formats

### 📊 **Advanced Chart Generation**
- **Multiple Chart Types**: Bar charts, pie charts, line charts, scatter plots, histograms
- **Automatic Chart Selection**: Chooses appropriate chart based on question context
- **Professional Styling**: Clean, publication-ready visualizations
- **Cloud Storage**: Cloudinary integration with local fallback

### 💾 **Comprehensive Data Management**
- **MongoDB Integration**: Persistent storage for files, chat history, and charts
- **GridFS Support**: Efficient handling of large CSV files
- **Smart Encoding**: Automatic encoding detection for various CSV formats
- **Performance Optimization**: Sampling for large datasets

### 🔧 **Production-Ready Features**
- **Error Handling**: Comprehensive error recovery and graceful degradation
- **Authentication Ready**: Environment-based configuration
- **CORS Support**: Frontend integration capabilities
- **Health Checks**: Built-in system status monitoring

## 🚀 Quick Start

### 1. **Environment Setup**

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env
```

Required environment variables:
```env
# MongoDB Configuration
MONGO_URL=mongodb://localhost:27017/
DB_NAME=csv_dashboard

# OpenAI API Configuration  
OPENAI_API_KEY=your_openai_api_key_here

# Cloudinary Configuration (optional, for chart hosting)
CLOUDINARY_CLOUD_NAME=your_cloudinary_cloud_name
CLOUDINARY_API_KEY=your_cloudinary_api_key
CLOUDINARY_API_SECRET=your_cloudinary_api_secret
```

### 2. **Install Dependencies**

```bash
# Core dependencies
pip install fastapi uvicorn pandas pymongo openai python-dotenv
pip install plotly matplotlib python-multipart

# Optional dependencies for enhanced features
pip install cloudinary seaborn kaleido chardet
pip install pandasai langchain-openai ai-data-science-team
```

### 3. **Start the Server**

#### Option A: Using the development script (recommended)
```bash
python start_dev_server.py
```

#### Option B: Direct startup
```bash
python server.py
# or
uvicorn server:app --reload --port 8000
```

### 4. **Test the System**

```bash
# Run comprehensive tests
python test_chat_system.py
```

## 📋 API Endpoints

### **File Management**
- `POST /api/upload-csv` - Upload CSV files
- `GET /api/files` - List all uploaded files  
- `DELETE /api/files/{file_id}` - Delete a file
- `GET /api/file-preview/{file_id}` - Preview file data

### **Chat System**
- `POST /api/chat/{file_id}` - Send chat message for analysis
- `GET /api/chat-history/{file_id}` - Get conversation history
- `DELETE /api/chat-history/{file_id}` - Clear chat history

### **Charts & Visualization**
- `GET /api/charts/{file_id}` - Get all charts for a file
- `GET /api/local-charts/{filename}` - Serve local chart images

### **Data Analysis**
- `POST /api/analyze/{file_id}` - Generate intelligent groups
- `GET /api/analysis/{file_id}` - Get analysis results

## 🎯 Usage Examples

### **Chart Generation**
```python
# User question: "Create a bar chart showing sales by category"
# System: → Routes to chart generation
#         → Returns chart image URL  
#         → Provides descriptive analysis
```

### **Data Analysis**
```python
# User question: "What are the top 5 products by revenue?"
# System: → Routes to table extraction
#         → Returns structured data table
#         → Provides insights and summary
```

### **Informational Queries**  
```python
# User question: "Tell me about the sales trends in this data"
# System: → Routes to comprehensive analysis
#         → Returns detailed insights
#         → Includes relevant statistics
```

## 🧠 Smart Routing Logic

The system uses advanced keyword analysis and context detection:

### **Chart Triggers**
- Keywords: `chart`, `graph`, `plot`, `visualization`, `trend`
- Phrases: `"create a visualization"`, `"show me a graph"`
- Context: Time-based queries, comparisons, correlations

### **Table Triggers**  
- Keywords: `list`, `top`, `bottom`, `what are`, `which`
- Phrases: `"tell me"`, `"analyze"`, `"find all"`
- Context: Specific data requests, statistical queries

## 🛠️ Architecture

### **Core Components**

```
┌─────────────────────┐    ┌──────────────────────┐
│   FastAPI Server    │    │   MongoDB Database   │
│   - REST API        │◄──►│   - File Storage     │
│   - Error Handling  │    │   - Chat History     │
│   - CORS Support    │    │   - Chart Metadata   │
└─────────────────────┘    └──────────────────────┘
           │
           ▼
┌─────────────────────┐    ┌──────────────────────┐
│ AdvancedPandasAI    │    │   Chart Generation   │
│ - Smart Routing     │◄──►│   - Plotly/Matplotlib│
│ - PandasAI/OpenAI   │    │   - Multiple Types   │
│ - Table Extraction  │    │   - Cloud Storage    │
└─────────────────────┘    └──────────────────────┘
```

### **Data Flow**

1. **File Upload** → GridFS storage → Metadata creation
2. **Chat Request** → Smart routing → Analysis engine
3. **Chart Generation** → Local creation → Cloud upload → URL return
4. **Data Extraction** → Table parsing → Structured response
5. **History Storage** → MongoDB persistence → Retrieval API

## 🔍 Error Handling & Fallbacks

### **Multi-Level Fallbacks**
1. **PandasAI** → Enhanced OpenAI analysis → Basic pandas operations
2. **Cloudinary** → Local file serving → Base64 encoding
3. **Encoding Detection** → UTF-8 → Latin-1 → Chardet → Error replacement

### **Graceful Degradation**
- Missing packages → Feature-specific warnings
- API failures → Fallback implementations  
- Large datasets → Intelligent sampling
- Network issues → Local alternatives

## 📊 Performance Features

### **Large Dataset Handling**
- **Intelligent Sampling**: 10% sample or 50k rows max for large files
- **Chunked Processing**: Memory-efficient data processing
- **Optimized Storage**: BSON size limit management
- **Preview Limits**: Configurable data preview sizes

### **Caching & Optimization**
- **Chart Caching**: Avoid regenerating identical charts
- **Metadata Storage**: Quick file information access
- **Connection Pooling**: Efficient database connections
- **Response Compression**: Reduced bandwidth usage

## 🔒 Security Considerations

### **Environment Security**
- API keys in environment variables
- Database connection string protection
- File upload validation
- Input sanitization

### **Data Protection**
- GridFS secure file storage
- Temporary file cleanup
- Error message sanitization
- Request rate limiting ready

## 🧪 Testing

### **Automated Testing**
```bash
# Run the comprehensive test suite
python test_chat_system.py
```

**Test Coverage:**
- ✅ File upload and storage
- ✅ Chart generation (all types)  
- ✅ Smart routing accuracy
- ✅ Chat history persistence
- ✅ Error handling and fallbacks
- ✅ API endpoint functionality

### **Manual Testing**
1. Upload sample CSV files
2. Test various question types
3. Verify chart generation
4. Check data table responses
5. Validate error scenarios

## 🚀 Production Deployment

### **Docker Setup** (Coming Soon)
```dockerfile
FROM python:3.9-slim
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### **Environment Variables**
Ensure all production environment variables are properly configured:
- Database connections with authentication
- API keys with appropriate permissions
- Cloud storage with proper access controls
- Error monitoring and logging setup

## 🤝 Contributing

### **Development Setup**
1. Fork the repository
2. Create a feature branch
3. Set up development environment
4. Run tests before committing
5. Submit pull request with description

### **Code Standards**
- Follow PEP 8 style guidelines
- Add docstrings for all functions
- Include error handling for all operations
- Write tests for new features
- Update documentation as needed

## 📞 Support

### **Common Issues**
- **MongoDB Connection**: Ensure MongoDB is running and accessible
- **OpenAI API**: Verify API key and quota availability
- **Package Installation**: Check Python version and pip updates
- **File Upload**: Verify file format and size limits

### **Debug Mode**
Enable detailed logging by setting environment variable:
```bash
export DEBUG=True
python server.py
```

---

## 🎉 **System Status: Production Ready**

The CSV Reader Backend is a **complete, production-ready system** with:
- ✅ Comprehensive error handling
- ✅ Robust fallback mechanisms  
- ✅ Automated test coverage
- ✅ Smart routing and response handling
- ✅ MongoDB persistence
- ✅ RESTful API design
- ✅ Performance optimization
- ✅ Security considerations

**Ready for production deployment and frontend integration!**
