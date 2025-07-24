import React, { createContext, useContext, useState, useEffect } from 'react';

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
  const [chatHistories, setChatHistories] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [connectionStatus, setConnectionStatus] = useState('connected'); // 'connected', 'disconnected', 'error'

  // Function to fetch documents from the API with retry logic
  const refreshDocuments = async (retryAttempt = 0) => {
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
        status: file.status || 'uploaded',
        has_charts: file.has_charts || false,
        last_chat_activity: file.last_chat_activity || null
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
  };

  // Function to select a document
  const selectDocument = async (document) => {
    setSelectedDocument(document);
    setError(null); // Clear any previous errors when selecting a new document
    
    // Load chat history for the selected document if not already loaded
    if (document && !chatHistories[document.file_id]) {
      console.log(`Loading chat history for document: ${document.filename} (${document.file_id})`);
      setIsLoading(true);
      await loadChatHistory(document.file_id);
      setIsLoading(false);
    } else if (document) {
      console.log(`Chat history already loaded for document: ${document.filename} (${chatHistories[document.file_id]?.length || 0} messages)`);
    }
  };

  // Function to load chat history for a specific document
  const loadChatHistory = async (fileId) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat-history/${fileId}`);
      if (response.ok) {
        const history = await response.json();
        const messages = history.messages || [];
        
        // Transform messages to match our ChatMessage interface
        const transformedMessages = messages.map(msg => ({
          id: msg.id || `${msg.timestamp || Date.now()}-${Math.random()}`,
          file_id: fileId,
          message: msg.message,
          sender: msg.sender,
          timestamp: msg.timestamp || new Date().toISOString(),
          chart_data: msg.chart_data || null,
          chart_type: msg.chart_type || null
        }));
        
        setChatHistories(prev => ({
          ...prev,
          [fileId]: transformedMessages
        }));
        
        console.log(`Loaded ${transformedMessages.length} messages for file ${fileId}`);
      } else if (response.status === 404) {
        // No history exists yet, initialize empty array
        setChatHistories(prev => ({
          ...prev,
          [fileId]: []
        }));
        console.log(`No chat history found for file ${fileId}, initialized empty array`);
      } else {
        throw new Error(`Failed to load chat history: ${response.status}`);
      }
    } catch (error) {
      console.error('Error loading chat history:', error);
      // Initialize empty array on error but set error state
      setChatHistories(prev => ({
        ...prev,
        [fileId]: []
      }));
      setError(`Failed to load chat history: ${error.message}`);
    }
  };

  // Function to add a chat message to a specific document's history
  const addChatMessage = (fileId, message) => {
    const newMessage = {
      id: message.id || `${Date.now()}-${Math.random()}`,
      file_id: fileId,
      message: message.message,
      sender: message.sender,
      timestamp: message.timestamp || new Date().toISOString(),
      chart_data: message.chart_data || null,
      chart_type: message.chart_type || null
    };

    setChatHistories(prev => ({
      ...prev,
      [fileId]: [...(prev[fileId] || []), newMessage]
    }));

    // Update the document's last_chat_activity and has_charts if chart is present
    setDocuments(prev => prev.map(doc => 
      doc.file_id === fileId 
        ? { 
            ...doc, 
            last_chat_activity: newMessage.timestamp,
            has_charts: doc.has_charts || (message.chart_data ? true : false)
          }
        : doc
    ));

    console.log(`Added ${message.sender} message to ${fileId}:`, {
      messageLength: message.message.length,
      hasChart: !!message.chart_data,
      timestamp: newMessage.timestamp
    });
  };

  // Function to clear chat history for a specific document
  const clearChatHistory = async (fileId) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat-history/${fileId}`, {
        method: 'DELETE',
      });
      
      if (response.ok) {
        setChatHistories(prev => ({
          ...prev,
          [fileId]: []
        }));
      }
    } catch (error) {
      console.error('Error clearing chat history:', error);
    }
  };

  // Function to get chat messages for a specific document
  const getChatMessages = (fileId) => {
    return chatHistories[fileId] || [];
  };

  // Load documents on mount
  useEffect(() => {
    refreshDocuments();
  }, []);

  // Context value
  const contextValue = {
    // State
    documents,
    selectedDocument,
    chatHistories,
    isLoading,
    error,
    retryCount,
    connectionStatus,
    
    // Functions
    selectDocument,
    refreshDocuments,
    addChatMessage,
    clearChatHistory,
    getChatMessages,
    loadChatHistory
  };

  return (
    <DocumentContext.Provider value={contextValue}>
      {children}
    </DocumentContext.Provider>
  );
};

export default DocumentContext;