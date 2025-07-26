import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDocumentContext } from './contexts/DocumentContext';
import './App.css';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

function App() {
  const navigate = useNavigate();
  const { selectDocument, selectedDocument } = useDocumentContext();
  const [files, setFiles] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [analysisData, setAnalysisData] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [activeTab, setActiveTab] = useState('analysis'); // Only 'analysis' tab now
  
  // Short-term memory for analysis results (cleared when app closes)
  const [analysisMemory, setAnalysisMemory] = useState(new Map());

  // Fetch files on component mount
  useEffect(() => {
    fetchFiles();
  }, []);

  const fetchFiles = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/files`);
      const data = await response.json();
      setFiles(data);
    } catch (error) {
      console.error('Error fetching files:', error);
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
    // Use DocumentContext to select the file
    await selectDocument(file);
    setPreviewData(null);
    setActiveTab('analysis'); // Reset to analysis tab

    // Check if we have analysis results in memory first
    if (analysisMemory.has(file.file_id)) {
      setAnalysisData(analysisMemory.get(file.file_id));
    } else {
      setAnalysisData(null);
    }

    // Fetch file preview
    try {
      const response = await fetch(`${API_BASE_URL}/api/file-preview/${file.file_id}`);
      const preview = await response.json();
      setPreviewData(preview);
    } catch (error) {
      console.error('Error fetching preview:', error);
    }

    // Only fetch from server if not in memory and status is completed
    if (!analysisMemory.has(file.file_id) && file.status === 'completed') {
      try {
        const response = await fetch(`${API_BASE_URL}/api/analysis/${file.file_id}`);
        const analysis = await response.json();
        // Store in memory for future use
        setAnalysisMemory(prev => new Map(prev).set(file.file_id, analysis));
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
        // Store in both current state and memory
        setAnalysisData(result);
        setAnalysisMemory(prev => new Map(prev).set(fileId, result));
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
          // Remove from analysis memory
          setAnalysisMemory(prev => {
            const newMap = new Map(prev);
            newMap.delete(fileId);
            return newMap;
          });
          
          if (selectedDocument && selectedDocument.file_id === fileId) {
            await selectDocument(null);
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
    if (!selectedDocument) {
      alert('Please select a file first');
      return;
    }
    
    console.log('Navigating to group configuration for file:', selectedDocument.file_id);

    try {
      // Navigate to the new configuration preview page
      navigate(`/configure-groups/${selectedDocument.file_id}`);
      // Scroll to top after navigation
      setTimeout(() => window.scrollTo(0, 0), 100);
    } catch (error) {
      console.error('Navigation error:', error);
      // Fallback to direct navigation
      window.location.href = `/configure-groups/${selectedDocument.file_id}`;
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
    <div className="min-h-screen bg-gray-50 pt-16">
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
                        selectedDocument?.file_id === file.file_id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
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
            {!selectedDocument ? (
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
                        <h2 className="text-lg font-semibold text-gray-900">{selectedDocument.filename}</h2>
                        <p className="text-sm text-gray-600">
                          {selectedDocument.total_rows} rows • {selectedDocument.columns?.length} columns
                        </p>
                      </div>
                      <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(selectedDocument.status)}`}>
                        {selectedDocument.status}
                      </span>
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
                          navigate(`/configure-groups/${selectedDocument.file_id}`);
                          setTimeout(() => window.scrollTo(0, 0), 100);
                        }}
                        className="flex-1 text-center py-2 px-4 rounded-md text-sm font-medium transition-colors text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                      >
                        <div className="flex items-center justify-center space-x-2">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          </svg>
                          <span>Configure AI Groups</span>
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
                          {!analysisMemory.has(selectedDocument.file_id) && selectedDocument.status === 'uploaded' && (
                            <button
                              onClick={() => handleAnalyze(selectedDocument.file_id)}
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
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                                  </svg>
                                  Start Analysis
                                </>
                              )}
                            </button>
                          )}
                          {analysisMemory.has(selectedDocument.file_id) && (
                            <button
                              onClick={() => handleAnalyze(selectedDocument.file_id)}
                              disabled={isAnalyzing}
                              className="inline-flex items-center px-4 py-2 bg-gray-600 text-white text-sm font-medium rounded-lg hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {isAnalyzing ? (
                                <>
                                  <svg className="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                  </svg>
                                  Re-analyzing...
                                </>
                              ) : (
                                <>
                                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                  </svg>
                                  Re-analyze
                                </>
                              )}
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Analysis Results - Only shown in analysis tab */}
                {activeTab === 'analysis' && analysisData && (
                  <div className="bg-white rounded-lg shadow-sm border">
                    <div className="p-4 border-b">
                      <div className="flex items-center justify-between">
                        <div>
                          <h2 className="text-lg font-semibold text-gray-900">AI Analysis Results</h2>
                          <p className="text-sm text-gray-600">Bulk procurement optimization groupings</p>
                        </div>
                        {analysisMemory.has(selectedDocument.file_id) && (
                          <span className="inline-flex items-center px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded-full">
                            <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                              <path d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zM3 10a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1v-6zM14 9a1 1 0 00-1 1v6a1 1 0 001 1h2a1 1 0 001-1v-6a1 1 0 00-1-1h-2z" />
                            </svg>
                            Cached
                          </span>
                        )}
                      </div>
                    </div>
                    
                    {/* Summary Stats */}
                    {analysisData.summary && (
                      <div className="p-4 border-b bg-gray-50">
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                          <div className="text-center">
                            <div className="text-2xl font-bold text-blue-600">{analysisData.summary.total_groups_created}</div>
                            <div className="text-xs text-gray-600">Groups Created</div>
                          </div>
                          <div className="text-center">
                            <div className="text-2xl font-bold text-green-600">{analysisData.summary.items_grouped}</div>
                            <div className="text-xs text-gray-600">Items Grouped</div>
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
                                <div className="space-y-3">
                                  {Object.entries(group.subgroups).map(([subName, subItems]) => {
                                    // Count unique items in this subgroup
                                    const itemCounts = {};
                                    if (Array.isArray(subItems)) {
                                      subItems.forEach(item => {
                                        const itemName = typeof item === 'string' ? item : (item?.name || item?.description || JSON.stringify(item));
                                        itemCounts[itemName] = (itemCounts[itemName] || 0) + 1;
                                      });
                                    }
                                    
                                    return (
                                      <div key={subName} className="bg-gray-50 rounded-lg p-3">
                                        <div className="flex items-center justify-between mb-2">
                                          <h4 className="text-sm font-medium text-gray-800">{subName}</h4>
                                          <span className="text-xs text-gray-600">
                                            {Object.keys(itemCounts).length} unique items, {subItems?.length} total
                                          </span>
                                        </div>
                                        <div className="space-y-1">
                                          {Object.entries(itemCounts).map(([itemName, count]) => (
                                            <div key={itemName} className="flex items-center justify-between text-xs">
                                              <span className="text-gray-700 truncate pr-2" title={itemName}>
                                                {itemName.length > 40 ? `${itemName.substring(0, 40)}...` : itemName}
                                              </span>
                                              <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 font-medium">
                                                {count}
                                              </span>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    );
                                  })}
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