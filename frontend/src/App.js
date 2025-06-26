import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import './App.css';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

function App() {
  const navigate = useNavigate();
  const [files, setFiles] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [analysisData, setAnalysisData] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [activeTab, setActiveTab] = useState('analysis'); // 'analysis', 'chat'
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);
  
  const chatEndRef = useRef(null);

  // Fetch files on component mount
  useEffect(() => {
    fetchFiles();
  }, []);

  // Scroll to bottom of chat when new messages are added
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // Load chat history when file is selected
  useEffect(() => {
    if (selectedFile && activeTab === 'chat') {
      loadChatHistory(selectedFile.file_id);
    }
  }, [selectedFile, activeTab]);

  // Function to load chat history
  const loadChatHistory = async (fileId) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat-history/${fileId}`);
      const history = await response.json();
      setChatMessages(history.messages || []);
    } catch (error) {
      console.error('Error loading chat history:', error);
      setChatMessages([]);
    }
  };

  const fetchFiles = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/files`);
      const data = await response.json();
      setFiles(data);
    } catch (error) {
      console.error('Error fetching files:', error);
    }
  };

  const handleSendMessage = async () => {
    if (!chatInput.trim() || !selectedFile) return;

    const userMessage = {
      message: chatInput,
      sender: 'user',
      timestamp: new Date().toISOString()
    };

    setChatMessages(prev => [...prev, userMessage]);
    const currentInput = chatInput;
    setChatInput('');
    setIsChatLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/${selectedFile.file_id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: currentInput, file_id: selectedFile.file_id }),
      });

      if (response.ok) {
        const result = await response.json();
        const aiMessage = {
          message: result.response,
          sender: 'ai',
          timestamp: new Date().toISOString(),
          chart_data: result.chart_data,
          chart_type: result.chart_type
        };
        setChatMessages(prev => [...prev, aiMessage]);
      } else {
        const error = await response.json();
        const errorMessage = {
          message: `Error: ${error.detail}`,
          sender: 'ai',
          timestamp: new Date().toISOString()
        };
        setChatMessages(prev => [...prev, errorMessage]);
      }
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = {
        message: 'Sorry, I encountered an error processing your request.',
        sender: 'ai',
        timestamp: new Date().toISOString()
      };
      setChatMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsChatLoading(false);
    }
  };

  const handleClearChat = async () => {
    if (!selectedFile) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat-history/${selectedFile.file_id}`, {
        method: 'DELETE',
      });
      
      if (response.ok) {
        setChatMessages([]);
      }
    } catch (error) {
      console.error('Error clearing chat:', error);
    }
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileUpload = async (file) => {
    if (!file.name.endsWith('.csv')) {
      alert('Please select a CSV file');
      return;
    }

    setUploadProgress('Uploading...');
    
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE_URL}/api/upload-csv`, {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const result = await response.json();
        setUploadProgress('Upload complete!');
        fetchFiles(); // Refresh file list
        setTimeout(() => setUploadProgress(null), 2000);
      } else {
        const error = await response.json();
        alert(`Upload failed: ${error.detail}`);
        setUploadProgress(null);
      }
    } catch (error) {
      console.error('Upload error:', error);
      alert('Upload failed');
      setUploadProgress(null);
    }
  };

  const handleFileSelect = async (file) => {
    setSelectedFile(file);
    setAnalysisData(null);
    setPreviewData(null);
    setChatMessages([]);
    setActiveTab('analysis'); // Reset to analysis tab

    // Fetch file preview
    try {
      const response = await fetch(`${API_BASE_URL}/api/file-preview/${file.file_id}`);
      const preview = await response.json();
      setPreviewData(preview);
    } catch (error) {
      console.error('Error fetching preview:', error);
    }

    // Check if analysis exists
    if (file.status === 'completed') {
      try {
        const response = await fetch(`${API_BASE_URL}/api/analysis/${file.file_id}`);
        const analysis = await response.json();
        setAnalysisData(analysis);
      } catch (error) {
        console.error('Error fetching analysis:', error);
      }
    }
  };

  const handleAnalyze = async (fileId) => {
    setIsAnalyzing(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/analyze/${fileId}`, {
        method: 'POST',
      });

      if (response.ok) {
        const result = await response.json();
        setAnalysisData(result);
        fetchFiles(); // Refresh to update status
      } else {
        const error = await response.json();
        alert(`Analysis failed: ${error.detail}`);
      }
    } catch (error) {
      console.error('Analysis error:', error);
      alert('Analysis failed');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleDeleteFile = async (fileId) => {
    if (window.confirm('Are you sure you want to delete this file?')) {
      try {
        const response = await fetch(`${API_BASE_URL}/api/files/${fileId}`, {
          method: 'DELETE',
        });

        if (response.ok) {
          fetchFiles();
          if (selectedFile && selectedFile.file_id === fileId) {
            setSelectedFile(null);
            setAnalysisData(null);
            setPreviewData(null);
          }
        }
      } catch (error) {
        console.error('Delete error:', error);
        alert('Delete failed');
      }
    }
  };

  const handleProcessingAIGroups = () => {
    if (!selectedFile) {
      alert('Please select a file first');
      return;
    }
    
    console.log('Navigating to group configuration for file:', selectedFile.file_id);
    
    try {
      // Navigate to the new configuration preview page
      navigate(`/configure-groups/${selectedFile.file_id}`);
    } catch (error) {
      console.error('Navigate error:', error);
      // Fallback to window.location for testing
      window.location.href = `/configure-groups/${selectedFile.file_id}`;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'uploaded': return 'bg-blue-100 text-blue-800';
      case 'processing': return 'bg-yellow-100 text-yellow-800';
      case 'completed': return 'bg-green-100 text-green-800';
      case 'error': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">CSV Processing Dashboard</h1>
              <p className="text-gray-600">Upload and analyze CSV files with AI-powered bulk procurement optimization</p>
            </div>
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 bg-green-400 rounded-full"></div>
              <span className="text-sm text-gray-600">System Online</span>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Left Panel - File Upload & List */}
          <div className="lg:col-span-1 space-y-6">
            
            {/* Upload Area */}
            <div className="bg-white rounded-lg shadow-sm border">
              <div className="p-4 border-b">
                <h2 className="text-lg font-semibold text-gray-900">Upload CSV File</h2>
              </div>
              <div className="p-4">
                <div
                  className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                    dragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
                  }`}
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                >
                  <div className="space-y-2">
                    <svg className="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                      <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    <div className="text-sm text-gray-600">
                      <label className="cursor-pointer">
                        <span className="text-blue-600 hover:text-blue-500">Click to upload</span>
                        <span> or drag and drop</span>
                        <input
                          type="file"
                          className="hidden"
                          accept=".csv"
                          onChange={(e) => e.target.files[0] && handleFileUpload(e.target.files[0])}
                        />
                      </label>
                    </div>
                    <p className="text-xs text-gray-500">CSV files only</p>
                  </div>
                </div>
                {uploadProgress && (
                  <div className="mt-4 text-center">
                    <div className="inline-flex items-center px-4 py-2 bg-blue-100 text-blue-800 rounded-lg">
                      <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      {uploadProgress}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Files List */}
            <div className="bg-white rounded-lg shadow-sm border">
              <div className="p-4 border-b">
                <h2 className="text-lg font-semibold text-gray-900">Uploaded Files</h2>
              </div>
              <div className="divide-y divide-gray-200">
                {files.length === 0 ? (
                  <div className="p-4 text-center text-gray-500">
                    No files uploaded yet
                  </div>
                ) : (
                  files.map((file) => (
                    <div
                      key={file.file_id}
                      className={`p-4 hover:bg-gray-50 cursor-pointer transition-colors ${
                        selectedFile?.file_id === file.file_id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
                      }`}
                      onClick={() => handleFileSelect(file)}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-gray-900 truncate">
                            {file.filename}
                          </p>
                          <p className="text-xs text-gray-500">
                            {file.total_rows} rows • {file.columns?.length} columns
                          </p>
                        </div>
                        <div className="flex items-center space-x-2">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(file.status)}`}>
                            {file.status}
                          </span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteFile(file.file_id);
                            }}
                            className="text-gray-400 hover:text-red-600"
                          >
                            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                          <button
                            onClick={() => navigate(`/configure-groups/${file.file_id}`)}
                            className="p-1 text-gray-400 hover:text-blue-600 focus:outline-none"
                            title="Configure AI Groups"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                              <path d="M5 4a1 1 0 00-2 0v7.268a2 2 0 000 3.464V16a1 1 0 102 0v-1.268a2 2 0 000-3.464V4zM11 4a1 1 0 10-2 0v1.268a2 2 0 000 3.464V16a1 1 0 102 0V8.732a2 2 0 000-3.464V4zM16 3a1 1 0 011 1v7.268a2 2 0 010 3.464V16a1 1 0 11-2 0v-1.268a2 2 0 010-3.464V4a1 1 0 011-1z" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* Right Panel - File Details & Analysis */}
          <div className="lg:col-span-2">
            {!selectedFile ? (
              <div className="bg-white rounded-lg shadow-sm border h-full flex items-center justify-center">
                <div className="text-center text-gray-500">
                  <svg className="mx-auto h-16 w-16 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <h3 className="mt-4 text-lg font-medium">Select a file to view details</h3>
                  <p className="text-sm">Choose a CSV file from the left panel to see its preview and analysis</p>
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                
                {/* File Info & Tabs */}
                <div className="bg-white rounded-lg shadow-sm border">
                  <div className="p-4 border-b">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h2 className="text-lg font-semibold text-gray-900">{selectedFile.filename}</h2>
                        <p className="text-sm text-gray-600">
                          {selectedFile.total_rows} rows • {selectedFile.columns?.length} columns
                        </p>
                      </div>
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(selectedFile.status)}`}>
                        {selectedFile.status}
                      </span>
                      {selectedFile.status === 'completed' && (
                        <button
                          onClick={handleProcessingAIGroups}
                          className="inline-flex items-center px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 transition-colors"
                        >
                          <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          </svg>
                          Configure AI Groups
                        </button>
                      )}
                    </div>
                    
                    {/* Tab Navigation */}
                    <div className="flex space-x-1 bg-gray-100 p-1 rounded-lg">
                      <button
                        onClick={() => setActiveTab('analysis')}
                        className={`flex-1 text-center py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                          activeTab === 'analysis'
                            ? 'bg-white text-blue-600 shadow-sm'
                            : 'text-gray-600 hover:text-gray-900'
                        }`}
                      >
                        <div className="flex items-center justify-center space-x-2">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                          </svg>
                          <span>AI Analysis</span>
                        </div>
                      </button>
                      <button
                        onClick={() => {
                          setActiveTab('chat');
                          if (selectedFile) {
                            loadChatHistory(selectedFile.file_id);
                          }
                        }}
                        className={`flex-1 text-center py-2 px-4 rounded-md text-sm font-medium transition-colors ${
                          activeTab === 'chat'
                            ? 'bg-white text-blue-600 shadow-sm'
                            : 'text-gray-600 hover:text-gray-900'
                        }`}
                      >
                        <div className="flex items-center justify-center space-x-2">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                          </svg>
                          <span>AI Q&A Chat</span>
                        </div>
                      </button>
                    </div>
                  </div>

                  {/* Tab Content */}
                  {activeTab === 'analysis' && (
                    <div>
                      {/* File Preview */}
                      {previewData && (
                        <div className="p-4 border-b">
                          <h3 className="text-sm font-medium text-gray-900 mb-3">Data Preview</h3>
                          <div className="overflow-x-auto">
                            <table className="min-w-full divide-y divide-gray-200">
                              <thead className="bg-gray-50">
                                <tr>
                                  {previewData.columns.map((col, index) => (
                                    <th key={index} className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                      {col}
                                    </th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody className="bg-white divide-y divide-gray-200">
                                {previewData.data.slice(0, 5).map((row, rowIndex) => (
                                  <tr key={rowIndex}>
                                    {previewData.columns.map((col, colIndex) => (
                                      <td key={colIndex} className="px-3 py-2 whitespace-nowrap text-sm text-gray-900">
                                        {String(row[col] || '').substring(0, 50)}
                                        {String(row[col] || '').length > 50 ? '...' : ''}
                                      </td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}

                      {/* Analysis Actions */}
                      <div className="p-4 border-b bg-gray-50">
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="text-sm font-medium text-gray-900">Procurement Analysis</h3>
                            <p className="text-xs text-gray-600">Generate AI-powered bulk procurement groupings</p>
                          </div>
                          {selectedFile.status === 'uploaded' && (
                            <button
                              onClick={() => handleAnalyze(selectedFile.file_id)}
                              disabled={isAnalyzing}
                              className="inline-flex items-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {isAnalyzing ? (
                                <>
                                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                  </svg>
                                  Analyzing...
                                </>
                              ) : (
                                <>
                                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                                  </svg>
                                  Analyze with AI
                                </>
                              )}
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {activeTab === 'chat' && (
                    <div className="h-96 flex flex-col">
                      {/* Chat Header */}
                      <div className="p-4 border-b bg-gray-50">
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="text-sm font-medium text-gray-900">Ask questions about your data</h3>
                            <p className="text-xs text-gray-600">You can ask for statistics, charts, or general questions about the CSV content</p>
                          </div>
                          <button
                            onClick={handleClearChat}
                            className="text-sm text-gray-500 hover:text-red-600 flex items-center space-x-1"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                            <span>Clear</span>
                          </button>
                        </div>
                      </div>

                      {/* Chat Messages */}
                      <div className="flex-1 overflow-y-auto p-4 space-y-4">
                        {chatMessages.length === 0 ? (
                          <div className="text-center text-gray-500 py-8">
                            <svg className="mx-auto h-12 w-12 text-gray-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                            </svg>
                            <p className="text-sm font-medium">Start a conversation</p>
                            <p className="text-xs text-gray-400 mt-1">Ask questions like "What's the average price?" or "Show me a chart of categories"</p>
                          </div>
                        ) : (
                          chatMessages.map((msg, index) => (
                            <div key={index} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                              <div className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                                msg.sender === 'user' 
                                  ? 'bg-blue-600 text-white' 
                                  : 'bg-gray-100 text-gray-900'
                              }`}>
                                <p className="text-sm whitespace-pre-wrap">{msg.message}</p>
                                {msg.chart_data && msg.chart_type === 'image_url' && (
                                  <div className="mt-2">
                                    <img 
                                      src={msg.chart_data} 
                                      alt="Generated chart" 
                                      className="max-w-full h-auto rounded border"
                                      onError={(e) => {
                                        e.target.style.display = 'none';
                                      }}
                                    />
                                  </div>
                                )}
                                <p className="text-xs opacity-75 mt-1">
                                  {new Date(msg.timestamp).toLocaleTimeString()}
                                </p>
                              </div>
                            </div>
                          ))
                        )}
                        {isChatLoading && (
                          <div className="flex justify-start">
                            <div className="bg-gray-100 text-gray-900 px-4 py-2 rounded-lg">
                              <div className="flex items-center space-x-2">
                                <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                                <span className="text-sm">AI is thinking...</span>
                              </div>
                            </div>
                          </div>
                        )}
                        <div ref={chatEndRef} />
                      </div>

                      {/* Chat Input */}
                      <div className="p-4 border-t">
                        <div className="flex space-x-2">
                          <input
                            type="text"
                            value={chatInput}
                            onChange={(e) => setChatInput(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                            placeholder="Ask a question about your data..."
                            className="flex-1 min-w-0 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                            disabled={isChatLoading}
                          />
                          <button
                            onClick={handleSendMessage}
                            disabled={!chatInput.trim() || isChatLoading}
                            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                            </svg>
                          </button>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-2">
                          <button
                            onClick={() => setChatInput("What are the main categories in this data?")}
                            className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-2 py-1 rounded-md"
                          >
                            Categories overview
                          </button>
                          <button
                            onClick={() => setChatInput("Show me a bar chart of the data")}
                            className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-2 py-1 rounded-md"
                          >
                            Create chart
                          </button>
                          <button
                            onClick={() => setChatInput("What's the average price?")}
                            className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-2 py-1 rounded-md"
                          >
                            Average price
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Analysis Results - Only shown in analysis tab */}
                {activeTab === 'analysis' && analysisData && (
                  <div className="bg-white rounded-lg shadow-sm border">
                    <div className="p-4 border-b">
                      <h2 className="text-lg font-semibold text-gray-900">AI Analysis Results</h2>
                      <p className="text-sm text-gray-600">Bulk procurement optimization groupings</p>
                    </div>
                    
                    {/* Summary Stats */}
                    {analysisData.summary && (
                      <div className="p-4 border-b bg-gray-50">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                          <div className="text-center">
                            <div className="text-2xl font-bold text-blue-600">{analysisData.summary.total_groups_created}</div>
                            <div className="text-xs text-gray-600">Groups Created</div>
                          </div>
                          <div className="text-center">
                            <div className="text-2xl font-bold text-green-600">{analysisData.summary.items_grouped}</div>
                            <div className="text-xs text-gray-600">Items Grouped</div>
                          </div>
                          <div className="text-center">
                            <div className="text-2xl font-bold text-purple-600">{analysisData.summary.estimated_total_savings}</div>
                            <div className="text-xs text-gray-600">Est. Savings</div>
                          </div>
                          <div className="text-center">
                            <div className="text-2xl font-bold text-orange-600">{analysisData.summary.items_ungrouped}</div>
                            <div className="text-xs text-gray-600">Ungrouped</div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Groups */}
                    <div className="p-4">
                      <div className="space-y-4">
                        {analysisData.groups?.map((group, index) => (
                          <div key={index} className="border rounded-lg p-4 hover:bg-gray-50">
                            <div className="flex items-start justify-between">
                              <div className="flex-1">
                                <h3 className="text-lg font-medium text-gray-900">{group.group_name}</h3>
                                <p className="text-sm text-gray-600 mt-1">{group.procurement_notes}</p>
                                <div className="flex items-center space-x-4 mt-2">
                                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                    {group.item_ids?.length} items
                                  </span>
                                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                    {group.estimated_savings_potential} savings
                                  </span>
                                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                                    {group.bulk_metric}
                                  </span>
                                </div>
                              </div>
                            </div>
                            
                            {/* Subgroups */}
                            {group.subgroups && Object.keys(group.subgroups).length > 0 && (
                              <div className="mt-3 pl-4 border-l-2 border-gray-200">
                                <p className="text-xs font-medium text-gray-700 mb-2">Subgroups:</p>
                                <div className="flex flex-wrap gap-2">
                                  {Object.entries(group.subgroups).map(([subName, subItems]) => (
                                    <span key={subName} className="inline-flex items-center px-2 py-1 rounded text-xs bg-gray-100 text-gray-700">
                                      {subName} ({subItems?.length})
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;