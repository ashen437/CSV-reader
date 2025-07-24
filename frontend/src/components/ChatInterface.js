import React, { useState, useRef, useEffect } from 'react';
import { useDocumentContext } from '../contexts/DocumentContext';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

const ChatInterface = () => {
  const { 
    selectedDocument, 
    getChatMessages, 
    addChatMessage 
  } = useDocumentContext();
  
  const [chatInput, setChatInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('connected'); // 'connected', 'disconnected', 'error'
  const [retryingMessageId, setRetryingMessageId] = useState(null);
  const [failedMessages, setFailedMessages] = useState(new Set());
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

  // Get messages for the selected document
  const messages = selectedDocument ? getChatMessages(selectedDocument.file_id) : [];

  // Auto-scroll to bottom when new messages are added
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Focus input when document is selected
  useEffect(() => {
    if (selectedDocument && inputRef.current) {
      inputRef.current.focus();
    }
  }, [selectedDocument]);

  // Handle sending a message
  const handleSendMessage = async () => {
    if (!chatInput.trim() || !selectedDocument || isLoading) return;

    const userMessage = {
      id: `${Date.now()}-${Math.random()}`,
      file_id: selectedDocument.file_id,
      message: chatInput,
      sender: 'user',
      timestamp: new Date().toISOString()
    };

    // Add user message to context
    addChatMessage(selectedDocument.file_id, userMessage);
    
    const currentInput = chatInput;
    setChatInput('');
    setIsLoading(true);

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 minute timeout for AI processing

      const response = await fetch(`${API_BASE_URL}/api/chat/${selectedDocument.file_id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          message: currentInput, 
          file_id: selectedDocument.file_id 
        }),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        const result = await response.json();
        const aiMessage = {
          id: `${Date.now()}-${Math.random()}`,
          file_id: selectedDocument.file_id,
          message: result.response || 'I received your message but had trouble generating a response.',
          sender: 'ai',
          timestamp: new Date().toISOString(),
          chart_data: result.chart_data || null,
          chart_type: result.chart_type || null
        };
        
        addChatMessage(selectedDocument.file_id, aiMessage);
        setConnectionStatus('connected');
        // Remove from failed messages if it was there
        setFailedMessages(prev => {
          const newSet = new Set(prev);
          newSet.delete(userMessage.id);
          return newSet;
        });
        
        console.log('Chat response received:', {
          hasResponse: !!result.response,
          hasChart: !!result.chart_data,
          chartType: result.chart_type
        });
      } else {
        let errorMessage = 'Failed to process your request';
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch (e) {
          // Use default error message if JSON parsing fails
        }

        // Mark user message as failed
        setFailedMessages(prev => new Set(prev).add(userMessage.id));

        const aiErrorMessage = {
          id: `${Date.now()}-${Math.random()}`,
          file_id: selectedDocument.file_id,
          message: `I apologize, but I encountered an error: ${errorMessage}. Please try rephrasing your question or try again later.`,
          sender: 'ai',
          timestamp: new Date().toISOString()
        };
        
        addChatMessage(selectedDocument.file_id, aiErrorMessage);
        setConnectionStatus('error');
        console.error('Chat API error:', response.status, errorMessage);
      }
    } catch (error) {
      console.error('Chat error:', error);
      let errorMessage = 'Sorry, I encountered an error processing your request. Please try again.';
      
      // Mark user message as failed
      setFailedMessages(prev => new Set(prev).add(userMessage.id));
      
      if (error.name === 'AbortError') {
        errorMessage = 'The request timed out. Please try again with a simpler question.';
        setConnectionStatus('error');
      } else if (error.message.includes('fetch') || error.message.includes('NetworkError')) {
        errorMessage = 'Unable to connect to the server. Please check your connection and try again.';
        setConnectionStatus('disconnected');
      } else {
        setConnectionStatus('error');
      }

      const aiErrorMessage = {
        id: `${Date.now()}-${Math.random()}`,
        file_id: selectedDocument.file_id,
        message: errorMessage,
        sender: 'ai',
        timestamp: new Date().toISOString()
      };
      
      addChatMessage(selectedDocument.file_id, aiErrorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle retry for failed messages
  const handleRetryMessage = async (originalMessage) => {
    if (isLoading || !selectedDocument) return;

    setRetryingMessageId(originalMessage.id);
    setIsLoading(true);

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000);

      const response = await fetch(`${API_BASE_URL}/api/chat/${selectedDocument.file_id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          message: originalMessage.message, 
          file_id: selectedDocument.file_id 
        }),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        const result = await response.json();
        const aiMessage = {
          id: `${Date.now()}-${Math.random()}`,
          file_id: selectedDocument.file_id,
          message: result.response || 'I received your message but had trouble generating a response.',
          sender: 'ai',
          timestamp: new Date().toISOString(),
          chart_data: result.chart_data || null,
          chart_type: result.chart_type || null
        };
        
        addChatMessage(selectedDocument.file_id, aiMessage);
        setConnectionStatus('connected');
        
        // Remove from failed messages on successful retry
        setFailedMessages(prev => {
          const newSet = new Set(prev);
          newSet.delete(originalMessage.id);
          return newSet;
        });
      } else {
        setConnectionStatus('error');
        throw new Error('Failed to retry message');
      }
    } catch (error) {
      console.error('Retry error:', error);
      setConnectionStatus('error');
    } finally {
      setIsLoading(false);
      setRetryingMessageId(null);
    }
  };

  // Handle key press in input
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Format timestamp for display
  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  // Render empty state when no document is selected
  if (!selectedDocument) {
    return (
      <div className="h-full flex items-center justify-center bg-white">
        <div className="text-center text-gray-500 max-w-md mx-auto px-4">
          <div className="mb-6">
            <svg className="mx-auto h-16 w-16 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">Select a document to start chatting</h3>
          <p className="text-sm text-gray-600">
            Choose a CSV file from the sidebar to begin asking questions about your data. 
            You can request statistics, charts, or general analysis.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-white no-overscroll">
      {/* Chat Header */}
      <div className="flex-shrink-0 px-3 sm:px-6 py-3 sm:py-4 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center justify-between">
          <div className="flex-1 min-w-0">
            <h2 className="text-base sm:text-lg font-semibold text-gray-900 truncate">
              {selectedDocument.filename}
            </h2>
            <p className="text-xs sm:text-sm text-gray-600 truncate">
              {selectedDocument.total_rows.toLocaleString()} rows • Ask questions about your data
            </p>
          </div>
          <div className="flex items-center space-x-1 sm:space-x-2 flex-shrink-0 ml-2">
            <div className={`w-2 h-2 rounded-full ${
              connectionStatus === 'connected' ? 'bg-green-500' :
              connectionStatus === 'error' ? 'bg-red-500' : 'bg-yellow-500'
            }`} title={
              connectionStatus === 'connected' ? 'Connected and ready' :
              connectionStatus === 'error' ? 'Connection error - some features may not work' : 
              'Connecting to server...'
            }></div>
            <span className="text-xs text-gray-600 hidden sm:inline">
              {connectionStatus === 'connected' ? 'Ready' :
               connectionStatus === 'error' ? 'Error' : 
               connectionStatus === 'disconnected' ? 'Offline' : 'Connecting...'}
            </span>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-3 sm:px-6 py-3 sm:py-4 space-y-3 sm:space-y-4">
        {messages.length === 0 ? (
          <div className="text-center text-gray-500 py-8 sm:py-12">
            <div className="mb-4">
              <svg className="mx-auto h-10 w-10 sm:h-12 sm:w-12 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <h3 className="text-sm font-medium text-gray-900 mb-2">Start a conversation</h3>
            <p className="text-xs text-gray-500 mb-4 px-4">
              Ask questions like "What's the average price?" or "Show me a chart of categories"
            </p>
            <div className="text-xs text-gray-400 space-y-1 px-4">
              <p>• Request data analysis and statistics</p>
              <p>• Generate charts and visualizations</p>
              <p>• Ask about specific data patterns</p>
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <div key={message.id} className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] sm:max-w-xs lg:max-w-md xl:max-w-lg ${
                message.sender === 'user' ? 'order-2' : 'order-1'
              }`}>
                {/* Message bubble */}
                <div className={`px-3 sm:px-4 py-2 sm:py-3 rounded-2xl ${
                  message.sender === 'user' 
                    ? 'bg-blue-600 text-white rounded-br-md' 
                    : 'bg-gray-100 text-gray-900 rounded-bl-md'
                }`}>
                  <p className="text-sm whitespace-pre-wrap break-words message-content">{message.message}</p>
                  
                  {/* Chart display for AI responses */}
                  {message.chart_data && message.chart_type === 'image_url' && (
                    <div className="mt-2 sm:mt-3 -mx-1">
                      <img 
                        src={message.chart_data} 
                        alt="Generated chart" 
                        className="max-w-full h-auto rounded-lg border border-gray-200 shadow-sm cursor-pointer hover:shadow-md transition-shadow touch-manipulation"
                        onError={(e) => {
                          e.target.style.display = 'none';
                          // Show error message
                          const errorDiv = document.createElement('div');
                          errorDiv.className = 'text-xs text-gray-500 italic mt-2 p-2 bg-gray-50 rounded border';
                          errorDiv.textContent = 'Chart could not be loaded. Please try asking for the visualization again.';
                          e.target.parentNode.appendChild(errorDiv);
                        }}
                        onClick={() => {
                          // Open chart in new tab for better viewing
                          window.open(message.chart_data, '_blank');
                        }}
                        title="Tap to view chart in full size"
                      />
                    </div>
                  )}
                  
                  {/* Retry button for failed user messages */}
                  {message.sender === 'user' && failedMessages.has(message.id) && (
                    <div className="mt-2">
                      <button
                        onClick={() => handleRetryMessage(message)}
                        disabled={isLoading || retryingMessageId === message.id}
                        className="text-xs text-white/80 hover:text-white underline disabled:opacity-50 touch-manipulation"
                      >
                        {retryingMessageId === message.id ? 'Retrying...' : 'Retry'}
                      </button>
                    </div>
                  )}
                </div>
                
                {/* Timestamp */}
                <div className={`text-xs text-gray-500 mt-1 px-1 ${
                  message.sender === 'user' ? 'text-right' : 'text-left'
                }`}>
                  {formatTimestamp(message.timestamp)}
                </div>
              </div>
            </div>
          ))
        )}
        
        {/* Loading indicator */}
        {isLoading && (
          <div className="flex justify-start">
            <div className="max-w-xs lg:max-w-md">
              <div className="bg-gray-100 px-4 py-3 rounded-2xl rounded-bl-md">
                <div className="flex items-center space-x-2">
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  </div>
                  <span className="text-xs text-gray-500">AI is thinking...</span>
                </div>
              </div>
            </div>
          </div>
        )}
        
        {/* Scroll anchor */}
        <div ref={chatEndRef} />
      </div>

      {/* Input Area */}
      <div className="flex-shrink-0 px-3 sm:px-6 py-3 sm:py-4 border-t border-gray-200 bg-white">
        <div className="flex items-end space-x-2 sm:space-x-3">
          <div className="flex-1">
            <textarea
              ref={inputRef}
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask a question about your data..."
              className="w-full px-3 sm:px-4 py-2 sm:py-3 border border-gray-300 rounded-2xl resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors text-sm sm:text-base touch-manipulation"
              rows="1"
              style={{ 
                minHeight: '40px',
                maxHeight: '120px',
                overflowY: chatInput.length > 100 ? 'auto' : 'hidden'
              }}
              disabled={isLoading}
            />
          </div>
          <button
            onClick={handleSendMessage}
            disabled={!chatInput.trim() || isLoading}
            className="flex-shrink-0 p-2 sm:p-3 bg-blue-600 text-white rounded-2xl hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors touch-manipulation active:bg-blue-800"
            style={{ minHeight: '40px', minWidth: '40px' }}
          >
            {isLoading ? (
              <svg className="w-4 h-4 sm:w-5 sm:h-5 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            ) : (
              <svg className="w-4 h-4 sm:w-5 sm:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            )}
          </button>
        </div>
        
        {/* Input hint */}
        <div className="mt-2 text-xs text-gray-500 text-center hidden sm:block">
          Press Enter to send • Shift+Enter for new line
        </div>
        <div className="mt-1 text-xs text-gray-500 text-center sm:hidden">
          Tap to send
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;