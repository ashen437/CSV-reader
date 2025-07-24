import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

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

// Interface for tracking per-chat AI response state
const createChatState = () => ({
  isAIResponding: false,
  isLoading: false,
  pollingInterval: null,
});

// DocumentProvider component
export const DocumentProvider = ({ children }) => {
  const [documents, setDocuments] = useState([]);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [chatHistories, setChatHistories] = useState({});
  const [chatSessions, setChatSessions] = useState({}); // { fileId: [sessions] }
  const [currentChatSession, setCurrentChatSession] = useState(null);
  const [activeChatId, setActiveChatId] = useState(null); // Track currently active chat
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);
  const [connectionStatus, setConnectionStatus] = useState('connected'); // 'connected', 'disconnected', 'error'

  // Enhanced chat state management
  const [chatStates, setChatStates] = useState({}); // Per-chat AI responding state
  const pollingIntervalRef = useRef(null); // Polling interval reference

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
    // If switching to a different document, clear any existing chat for the previous document
    if (selectedDocument && selectedDocument.file_id !== document?.file_id) {
      console.log(`Switching from ${selectedDocument.filename} to ${document?.filename || 'none'} - clearing previous chat state`);
    }
    
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
    } else {
      console.log('No document selected - clearing selection');
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

  // Function to create a new chat session
  const createNewChatSession = (fileId) => {
    const sessionId = `chat-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const newSession = {
      id: sessionId,
      fileId: fileId,
      title: 'New Chat',
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      messageCount: 0
    };

    // Add to sessions
    setChatSessions(prev => ({
      ...prev,
      [fileId]: [...(prev[fileId] || []), newSession]
    }));

    // Set as current active session
    setCurrentChatSession(newSession);
    setActiveChatId(sessionId);
    
    // Clear current chat history to start fresh
    setChatHistories(prev => ({
      ...prev,
      [fileId]: []
    }));

    console.log(`Created new chat session: ${sessionId} for file: ${fileId}`);
    return newSession;
  };

  // Function to select a chat session
  const selectChatSession = (session) => {
    if (!session) {
      setCurrentChatSession(null);
      setActiveChatId(null);
      return;
    }

    setCurrentChatSession(session);
    setActiveChatId(session.id);
    
    // Load the session's messages into current chat history
    setChatHistories(prev => ({
      ...prev,
      [session.fileId]: session.messages || []
    }));

    console.log(`Selected chat session: ${session.id} with ${session.messages?.length || 0} messages`);
  };

  // Function to get chat sessions for a file
  const getChatSessions = (fileId) => {
    return chatSessions[fileId] || [];
  };

  // Function to delete a specific chat session
  const deleteChatSession = async (sessionId, fileId) => {
    try {
      // Remove from local state
      setChatSessions(prev => ({
        ...prev,
        [fileId]: (prev[fileId] || []).filter(session => session.id !== sessionId)
      }));

      // If this was the active session, clear it
      if (activeChatId === sessionId) {
        setCurrentChatSession(null);
        setActiveChatId(null);
        setChatHistories(prev => ({
          ...prev,
          [fileId]: []
        }));
      }

      console.log(`Deleted chat session: ${sessionId}`);
      return true;
    } catch (error) {
      console.error('Error deleting chat session:', error);
      return false;
    }
  };

  // Enhanced addChatMessage to work with sessions
  const addChatMessageToSession = (fileId, message) => {
    const newMessage = {
      id: message.id || `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      file_id: fileId,
      message: message.message,
      sender: message.sender,
      timestamp: message.timestamp || new Date().toISOString(),
      chart_data: message.chart_data || null,
      chart_type: message.chart_type || null
    };

    // Add to current chat history
    setChatHistories(prev => ({
      ...prev,
      [fileId]: [...(prev[fileId] || []), newMessage]
    }));

    // Update current session if one is active
    if (currentChatSession && currentChatSession.fileId === fileId) {
      const updatedMessages = [...(currentChatSession.messages || []), newMessage];
      const updatedSession = {
        ...currentChatSession,
        messages: updatedMessages,
        messageCount: updatedMessages.length,
        updatedAt: new Date().toISOString(),
        title: currentChatSession.title === 'New Chat' && message.sender === 'user' 
          ? message.message.slice(0, 50) + (message.message.length > 50 ? '...' : '')
          : currentChatSession.title
      };

      // Update in sessions list
      setChatSessions(prev => ({
        ...prev,
        [fileId]: (prev[fileId] || []).map(session => 
          session.id === currentChatSession.id ? updatedSession : session
        )
      }));

      setCurrentChatSession(updatedSession);
    } else if (!currentChatSession) {
      // If no active session, create one
      const newSession = createNewChatSession(fileId);
      addChatMessageToSession(fileId, message);
      return;
    }

    // Update the document's last_chat_activity
    setDocuments(prev => prev.map(doc => 
      doc.file_id === fileId 
        ? { 
            ...doc, 
            last_chat_activity: newMessage.timestamp,
            has_charts: doc.has_charts || (message.chart_data ? true : false)
          }
        : doc
    ));

    console.log(`Added ${message.sender} message to session: ${currentChatSession?.id}`);
  };

  // Enhanced chat state management functions
  
  // Function to update AI responding state for a specific chat
  const updateChatState = useCallback((chatId, updates) => {
    setChatStates(prev => ({
      ...prev,
      [chatId]: {
        ...createChatState(),
        ...prev[chatId],
        ...updates,
      },
    }));

    // Broadcast state change to other components
    window.dispatchEvent(
      new CustomEvent('aiRespondingStateChange', {
        detail: { isAIResponding: updates.isAIResponding || false },
      })
    );
  }, []);

  // Helper function to get or initialize chat state
  const getChatState = useCallback((chatId) => {
    return chatStates[chatId] || createChatState();
  }, [chatStates]);

  // Function to start polling for new messages for a specific chat
  const startPollingForMessages = useCallback((chatId, expectedMessageCount = 0) => {
    if (!chatId) return;

    const chatState = getChatState(chatId);

    // Clear any existing polling for this chat
    if (chatState.pollingInterval) {
      clearInterval(chatState.pollingInterval);
    }

    let pollCount = 0;
    const maxPolls = 120; // Poll for up to 2 minutes (120 * 1 second)

    const pollingInterval = setInterval(async () => {
      pollCount++;

      try {
        // Find the session by ID
        const session = Object.values(chatSessions).flat().find(s => s.id === chatId);
        if (!session) return;

        const response = await fetch(`${API_BASE_URL}/api/chat-history/${session.fileId}`);
        if (response.ok) {
          const chatData = await response.json();
          const newMessages = chatData.messages || [];

          // Update the session if new messages are found
          if (newMessages.length > expectedMessageCount) {
            // Update sessions
            setChatSessions(prev => ({
              ...prev,
              [session.fileId]: (prev[session.fileId] || []).map(s =>
                s.id === chatId
                  ? { ...s, messages: newMessages, updatedAt: new Date().toISOString(), messageCount: newMessages.length }
                  : s
              )
            }));

            // Update current session if it's active
            if (currentChatSession?.id === chatId) {
              setCurrentChatSession(prev => prev ? { ...prev, messages: newMessages, messageCount: newMessages.length } : null);
              setChatHistories(prev => ({ ...prev, [session.fileId]: newMessages }));
            }

            // New messages found, stop polling for this chat
            updateChatState(chatId, {
              isLoading: false,
              isAIResponding: false,
              pollingInterval: null,
            });
            clearInterval(pollingInterval);
            return;
          }
        }
      } catch (error) {
        console.error('Error polling for messages:', error);
      }

      // Stop polling after max attempts
      if (pollCount >= maxPolls) {
        updateChatState(chatId, {
          isLoading: false,
          isAIResponding: false,
          pollingInterval: null,
        });
        clearInterval(pollingInterval);
      }
    }, 1000); // Poll every second

    // Store the polling interval in the chat state
    updateChatState(chatId, {
      pollingInterval: pollingInterval,
    });
  }, [getChatState, updateChatState, chatSessions, currentChatSession]);

  // Enhanced sendChatMessage with polling support
  const sendChatMessage = async (fileId, message) => {
    if (!currentChatSession) {
      console.warn('No active chat session to send message to');
      return;
    }

    const chatId = currentChatSession.id;
    
    // Set loading state BEFORE adding user message
    updateChatState(chatId, {
      isLoading: true,
      isAIResponding: true,
    });

    // Add user message locally first
    const userMessage = {
      id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      message: message,
      sender: 'user',
      timestamp: new Date().toISOString()
    };

    addChatMessageToSession(fileId, userMessage);

    // Store the current message count for polling comparison
    const currentMessageCount = (currentChatSession.messages?.length || 0) + 1;

    try {
      // Fire-and-forget API call - don't wait for the response
      fetch(`${API_BASE_URL}/api/chat/${fileId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: message,
          chatId: chatId,
          currentMessageCount, // Pass current count for polling comparison
        }),
      }).catch((error) => {
        console.error('Error sending message:', error);
        const errorMessage = {
          id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          message: 'Sorry, something went wrong. Please try again.',
          sender: 'ai',
          timestamp: new Date().toISOString()
        };
        addChatMessageToSession(fileId, errorMessage);
        updateChatState(chatId, {
          isLoading: false,
          isAIResponding: false,
        });
      });

      // Start polling for new messages with current count
      startPollingForMessages(chatId, currentMessageCount);
    } catch (error) {
      console.error('Error initiating chat message:', error);
      const errorMessage = {
        id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        message: 'Sorry, something went wrong. Please try again.',
        sender: 'ai',
        timestamp: new Date().toISOString()
      };
      addChatMessageToSession(fileId, errorMessage);
      updateChatState(chatId, {
        isLoading: false,
        isAIResponding: false,
      });
    }
  };

  // Cleanup polling on component unmount
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      
      // Clean up all chat polling intervals
      Object.values(chatStates).forEach(state => {
        if (state.pollingInterval) {
          clearInterval(state.pollingInterval);
        }
      });
    };
  }, [chatStates]);

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
    chatSessions,
    currentChatSession,
    activeChatId,
    isLoading,
    error,
    retryCount,
    connectionStatus,
    chatStates, // Enhanced: Per-chat AI state
    
    // Functions
    selectDocument,
    refreshDocuments,
    addChatMessage,
    addChatMessageToSession,
    clearChatHistory,
    getChatMessages,
    getChatSessions,
    createNewChatSession,
    selectChatSession,
    deleteChatSession,
    loadChatHistory,
    
    // Enhanced functions
    updateChatState,
    getChatState,
    startPollingForMessages,
    sendChatMessage, // Enhanced chat message sending with polling
  };

  return (
    <DocumentContext.Provider value={contextValue}>
      {children}
    </DocumentContext.Provider>
  );
};

export default DocumentContext;