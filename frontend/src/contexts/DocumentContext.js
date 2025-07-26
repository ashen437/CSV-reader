import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

// Create the context
const DocumentContext = createContext();

// Custom hook to use the DocumentContext
export const useDocumentContext = () => {
  const context = useContext(DocumentContext);
  if (!context) {
    throw new Error('useDocumentContext must be used within a DocumentProvider');
  }
  return context;
};

// DocumentProvider component
export const DocumentProvider = ({ children }) => {
  const [documents, setDocuments] = useState([]);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [connectionStatus, setConnectionStatus] = useState('connected'); // 'connected', 'disconnected', 'error'

  // Function to fetch documents from the API with retry logic
  const refreshDocuments = useCallback(async (retryAttempt = 0) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
      
      const response = await fetch(`${API_BASE_URL}/api/files`, {
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        if (response.status >= 500 && retryAttempt < 2) {
          // Retry on server errors
          console.log(`Server error, retrying... (attempt ${retryAttempt + 1})`);
          setTimeout(() => refreshDocuments(retryAttempt + 1), 1000 * (retryAttempt + 1));
          return;
        }
        throw new Error(`Failed to fetch documents (${response.status})`);
      }
      
      const data = await response.json();
      
      // Transform the data to match our Document interface
      const transformedDocuments = data.map(file => ({
        file_id: file.file_id,
        filename: file.filename,
        upload_date: file.upload_date || new Date().toISOString(),
        total_rows: file.total_rows || 0,
        columns: file.columns || [],
        status: file.status || 'uploaded'
      }));
      
      setDocuments(transformedDocuments);
      setConnectionStatus('connected');
      setRetryCount(0);
      
    } catch (error) {
      console.error('Error fetching documents:', error);
      
      if (error.name === 'AbortError') {
        setError('Request timed out. Please check your connection.');
        setConnectionStatus('disconnected');
      } else if (error.message.includes('fetch')) {
        setError('Unable to connect to server. Please check your connection.');
        setConnectionStatus('disconnected');
      } else {
        setError(error.message);
        setConnectionStatus('error');
      }
      
      setDocuments([]);
      setRetryCount(retryAttempt);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Function to select a document
  const selectDocument = useCallback(async (document) => {
    setSelectedDocument(document);
    setError(null); // Clear any previous errors when selecting a new document
  }, []);

  // Function to delete a document
  const deleteDocument = useCallback(async (fileId) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/files/${fileId}`, {
        method: 'DELETE',
      });
      
      if (response.ok) {
        // Remove from local state
        setDocuments(prev => prev.filter(doc => doc.file_id !== fileId));
        
        // Clear selected document if it was the deleted one
        if (selectedDocument && selectedDocument.file_id === fileId) {
          setSelectedDocument(null);
        }
      } else {
        throw new Error(`Failed to delete document: ${response.status}`);
      }
    } catch (error) {
      console.error('Error deleting document:', error);
      setError(`Failed to delete document: ${error.message}`);
    }
  }, [selectedDocument]);

  // Function to upload a new document
  const uploadDocument = useCallback(async (file) => {
    try {
      setIsLoading(true);
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await fetch(`${API_BASE_URL}/api/upload-csv`, {
        method: 'POST',
        body: formData,
      });
      
      if (response.ok) {
        const result = await response.json();
        
        // Add the new document to the list
        const newDocument = {
          file_id: result.file_id,
          filename: result.filename,
          upload_date: new Date().toISOString(),
          total_rows: result.total_rows || 0,
          columns: result.columns || [],
          status: result.status || 'uploaded'
        };
        
        setDocuments(prev => [...prev, newDocument]);
        return newDocument;
      } else {
        throw new Error(`Upload failed: ${response.status}`);
      }
    } catch (error) {
      console.error('Error uploading document:', error);
      setError(`Failed to upload document: ${error.message}`);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Function to get file preview
  const getFilePreview = useCallback(async (fileId, rows = 10) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/file-preview/${fileId}?rows=${rows}`);
      
      if (response.ok) {
        return await response.json();
      } else {
        throw new Error(`Failed to get file preview: ${response.status}`);
      }
    } catch (error) {
      console.error('Error getting file preview:', error);
      setError(`Failed to get file preview: ${error.message}`);
      throw error;
    }
  }, []);

  // Initialize documents on mount
  useEffect(() => {
    refreshDocuments();
  }, [refreshDocuments]);

  // Auto-refresh documents every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      if (connectionStatus === 'connected') {
        refreshDocuments();
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [refreshDocuments, connectionStatus]);

  // Context value - only grouping-related functionality
  const contextValue = {
    // State
    documents,
    selectedDocument,
    isLoading,
    error,
    retryCount,
    connectionStatus,
    
    // Functions
    selectDocument,
    refreshDocuments,
    deleteDocument,
    uploadDocument,
    getFilePreview,
  };

  return (
    <DocumentContext.Provider value={contextValue}>
      {children}
    </DocumentContext.Provider>
  );
};
