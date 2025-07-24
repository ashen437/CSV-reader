import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Send, Menu } from 'lucide-react';
import ChatSidebar from './ChatSidebar';
import { useDocumentContext } from '../contexts/DocumentContext';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

const ChartsPage = () => {
  const { 
    selectedDocument, 
    getChatMessages, 
    addChatMessage, 
    addChatMessageToSession,
    currentChatSession,
    createNewChatSession,
    sendChatMessage,     // Enhanced: Use the new polling-enabled function
    chatStates = {},     // Enhanced: Per-chat AI state
    getChatState,        // Enhanced: Get chat state function
    activeChatId         // Enhanced: Track active chat for real-time updates
  } = useDocumentContext();
  
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  // Get current chat's state for loading indicators
  const currentChatState = currentChatSession && getChatState ? getChatState(currentChatSession.id) : null;
  const isLoading = currentChatState?.isLoading || false;
  const isAIResponding = currentChatState?.isAIResponding || false;

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // Function to add system message for document changes
  const addDocumentChangeNotification = useCallback((message) => {
    const systemMessage = {
      id: `system_${Date.now()}`,
      message: `ℹ️ ${message}`,
      sender: 'ai',
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, systemMessage]);
  }, []);

  // Listen for AI responding state changes
  useEffect(() => {
    const handleAIStateChange = (event) => {
      // You can add any global UI updates here based on AI state
      console.log('AI responding state changed:', event.detail.isAIResponding);
    };

    window.addEventListener('aiRespondingStateChange', handleAIStateChange);
    return () => window.removeEventListener('aiRespondingStateChange', handleAIStateChange);
  }, []);

  // Get messages for the selected document when it changes
  useEffect(() => {
    if (selectedDocument) {
      const documentMessages = getChatMessages(selectedDocument.file_id);
      setMessages(documentMessages);
    } else {
      setMessages([]);
    }
  }, [selectedDocument, getChatMessages]);

  // Auto-scroll to bottom when new messages are added
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [input]);

  const createNewChat = () => {
    // Clear current messages and input
    setMessages([]);
    setInput('');
    
    // If a document is selected and no current session exists, create a new session for it
    if (selectedDocument && !currentChatSession) {
      createNewChatSession(selectedDocument.file_id);
    }
  };

  const handleSelectChat = (chat) => {
    if (chat) {
      // Load the selected chat's messages
      // For now, we'll just clear messages as we don't have individual chat loading yet
      // In a more advanced implementation, you would load the specific chat's messages
      setMessages([]);
      setInput('');
    } else {
      // No specific chat selected, just clear to start fresh
      setMessages([]);
      setInput('');
    }
  };

  const handleSend = async () => {
    if (!input.trim() || !selectedDocument) return;

    const messageContent = input.trim();
    setInput('');

    // Check if we have a current chat session, create one if not
    if (!currentChatSession) {
      createNewChatSession(selectedDocument.file_id);
      // Add a small delay to allow the session to be created
      setTimeout(() => {
        if (sendChatMessage) {
          sendChatMessage(selectedDocument.file_id, messageContent);
        } else {
          // Fallback to legacy method
          handleSendLegacy(messageContent);
        }
      }, 100);
    } else {
      // Use the enhanced sendChatMessage with polling
      if (sendChatMessage) {
        sendChatMessage(selectedDocument.file_id, messageContent);
      } else {
        // Fallback to legacy method
        handleSendLegacy(messageContent);
      }
    }
  };

  // Legacy send method as fallback
  const handleSendLegacy = async (messageContent) => {
    if (!selectedDocument) return;

    // Create user message
    const userMessage = {
      id: `${Date.now()}-${Math.random()}`,
      file_id: selectedDocument.file_id,
      message: messageContent,
      sender: 'user',
      timestamp: new Date().toISOString()
    };

    // Add user message to context and local state
    if (currentChatSession) {
      addChatMessageToSession(selectedDocument.file_id, userMessage);
    } else {
      createNewChatSession(selectedDocument.file_id);
      addChatMessageToSession(selectedDocument.file_id, userMessage);
    }
    setMessages(prev => [...prev, userMessage]);

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 120000);

      const response = await fetch(`${API_BASE_URL}/api/chat/${selectedDocument.file_id}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          message: messageContent, 
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
        
        addChatMessageToSession(selectedDocument.file_id, aiMessage);
        setMessages(prev => [...prev, aiMessage]);
      } else {
        let errorMessage = 'Failed to process your request';
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch (e) {
          // Use default error message
        }

        const aiErrorMessage = {
          id: `${Date.now()}-${Math.random()}`,
          file_id: selectedDocument.file_id,
          message: `I apologize, but I encountered an error: ${errorMessage}. Please try rephrasing your question or try again later.`,
          sender: 'ai',
          timestamp: new Date().toISOString()
        };
        
        addChatMessageToSession(selectedDocument.file_id, aiErrorMessage);
        setMessages(prev => [...prev, aiErrorMessage]);
      }
    } catch (error) {
      console.error('Chat error:', error);
      let errorMessage = 'Sorry, I encountered an error processing your request. Please try again.';
      
      if (error.name === 'AbortError') {
        errorMessage = 'The request timed out. Please try again with a simpler question.';
      } else if (error.message.includes('fetch') || error.message.includes('NetworkError')) {
        errorMessage = 'Unable to connect to the server. Please check your connection and try again.';
      }

      const aiErrorMessage = {
        id: `${Date.now()}-${Math.random()}`,
        file_id: selectedDocument.file_id,
        message: errorMessage,
        sender: 'ai',
        timestamp: new Date().toISOString()
      };
      
      addChatMessageToSession(selectedDocument.file_id, aiErrorMessage);
      setMessages(prev => [...prev, aiErrorMessage]);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatTime = (date) => {
    return new Date(date).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col pt-16">
      <div className="flex h-[calc(100vh-4rem)] bg-gray-50 overflow-hidden">
        {/* Sidebar */}
        <div
          className={`${
            isSidebarOpen ? 'w-80' : 'w-0'
          } transition-all duration-300 overflow-hidden flex-shrink-0`}
        >
          <ChatSidebar
            onNewChat={createNewChat}
            onSelectChat={handleSelectChat}
            isOpen={isSidebarOpen}
          />
        </div>

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Header */}
          <div className="bg-white border-b border-gray-200 p-4 flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-3 min-w-0">
              <button
                onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                className="p-2 hover:bg-gray-100 rounded-lg flex-shrink-0"
              >
                <Menu size={24} />
              </button>
              <h1 className="text-xl font-semibold text-gray-900 truncate">
                {selectedDocument ? `Chat with ${selectedDocument.filename}` : 'AI Assistant'}
              </h1>
            </div>

            {/* Status indicator */}
            <div className="flex items-center gap-3">
              {selectedDocument && (
                <span className="text-sm text-gray-600 bg-gray-100 px-3 py-1 rounded-full">
                  CSV Document
                </span>
              )}
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
            {!selectedDocument ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <div className="w-16 h-16 mx-auto mb-4 bg-blue-100 rounded-full flex items-center justify-center">
                    <Send className="w-8 h-8 text-blue-600" />
                  </div>
                  <h3 className="text-lg font-medium text-gray-900 mb-2">Welcome to CSV Chat</h3>
                  <p className="text-gray-600 mb-4">Select a CSV document from the sidebar to start chatting with your data.</p>
                </div>
              </div>
            ) : messages.length === 0 ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <div className="w-16 h-16 mx-auto mb-4 bg-green-100 rounded-full flex items-center justify-center">
                    <Send className="w-8 h-8 text-green-600" />
                  </div>
                  <h3 className="text-lg font-medium text-gray-900 mb-2">Start Your Conversation</h3>
                  <p className="text-gray-600 mb-4">Ask me anything about your CSV data. I can help analyze, summarize, and create charts.</p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-md mx-auto">
                    <button 
                      onClick={() => setInput("Show me a summary of this data")}
                      className="p-3 text-left bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      <div className="font-medium text-sm">Summarize Data</div>
                      <div className="text-xs text-gray-500">Get an overview of your CSV</div>
                    </button>
                    <button 
                      onClick={() => setInput("Create a chart from this data")}
                      className="p-3 text-left bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      <div className="font-medium text-sm">Create Chart</div>
                      <div className="text-xs text-gray-500">Visualize your data</div>
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${
                    message.sender === 'user' ? 'justify-end' : 'justify-start'
                  }`}
                >
                  <div
                    className={`max-w-[75%] sm:max-w-md lg:max-w-2xl px-4 py-3 rounded-lg ${
                      message.sender === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-white border border-gray-200 text-gray-900'
                    }`}
                  >
                    <p className="text-sm whitespace-pre-wrap break-words">
                      {message.message}
                    </p>
                    <p
                      className={`text-xs mt-1 ${
                        message.sender === 'user'
                          ? 'text-blue-100'
                          : 'text-gray-500'
                      }`}
                    >
                      {formatTime(message.timestamp)}
                    </p>
                  </div>
                </div>
              ))
            )}

            {(isLoading || isAIResponding) && (
              <div className="flex justify-start">
                <div className="bg-white border border-gray-200 rounded-lg px-4 py-3">
                  <div className="flex items-center space-x-2">
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                    </div>
                    <span className="text-sm text-blue-600">
                      {isAIResponding ? 'AI is analyzing your data...' : 'Preparing response...'}
                    </span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="bg-white border-t border-gray-200 p-4 flex-shrink-0">
            <div className="max-w-4xl mx-auto w-full">
              <div className="flex items-end gap-3 bg-gray-100 rounded-lg p-3 min-h-[52px]">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={
                    !selectedDocument 
                      ? "Select a CSV document to start chatting..."
                      : isAIResponding
                      ? "AI is processing your previous message..."
                      : isLoading
                      ? "Preparing response..."
                      : currentChatSession
                      ? `Continue chatting about ${selectedDocument.filename}...`
                      : `Ask questions about ${selectedDocument.filename}...`
                  }
                  disabled={!selectedDocument}
                  rows={1}
                  className="flex-1 bg-transparent border-none outline-none resize-none text-gray-900 placeholder-gray-500 min-h-[28px] max-h-[120px] disabled:cursor-not-allowed"
                />

                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    onClick={handleSend}
                    disabled={!input.trim() || !selectedDocument} // Only disable if no input or document, not if loading
                    className="p-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-lg transition-colors flex-shrink-0"
                  >
                    {isLoading || isAIResponding ? (
                      <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <Send className="w-5 h-5" />
                    )}
                  </button>
                </div>
              </div>

              <p className="text-xs text-gray-500 mt-2 text-center">
                Press Enter to send, Shift + Enter for new line
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChartsPage;