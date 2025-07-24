import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, FileText, Trash2, MessageSquare, Plus, Settings } from 'lucide-react';
import { useDocumentContext } from '../contexts/DocumentContext';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

const ChatSidebar = ({ 
  isOpen,
  onSelectChat,
  onNewChat
}) => {
  const { 
    documents = [], 
    selectedDocument, 
    selectDocument, 
    refreshDocuments, 
    clearChatHistory,
    getChatSessions,
    createNewChatSession,
    selectChatSession,
    deleteChatSession,
    currentChatSession,
    activeChatId,
    chatStates = {}, // Enhanced: Per-chat AI state
    getChatState,    // Enhanced: Get chat state function
  } = useDocumentContext();
  const [searchTerm, setSearchTerm] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [expandedFiles, setExpandedFiles] = useState(new Set());
  const [uploadProgress, setUploadProgress] = useState(null);

  // Auto-expand files when they have an active chat
  useEffect(() => {
    if (activeChatId && currentChatSession) {
      setExpandedFiles(prev => new Set([...prev, currentChatSession.fileId]));
    }
  }, [activeChatId, currentChatSession]);

  const handleFileUpload = async (file) => {
    if (!file || !file.name.endsWith('.csv')) {
      alert('Please select a CSV file');
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const xhr = new XMLHttpRequest();
      
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          const percentComplete = (event.loaded / event.total) * 100;
          setUploadProgress(Math.round(percentComplete));
        }
      };

      xhr.onload = async () => {
        if (xhr.status === 200) {
          const result = JSON.parse(xhr.responseText);
          console.log('Upload successful:', result);
          await refreshDocuments(); // Refresh the documents list
          setUploadProgress(100);
          setTimeout(() => {
            setIsUploading(false);
            setUploadProgress(null);
          }, 1000);
        } else {
          throw new Error(`Upload failed with status ${xhr.status}`);
        }
      };

      xhr.onerror = () => {
        throw new Error('Upload failed due to network error');
      };

      xhr.open('POST', `${API_BASE_URL}/api/upload-csv`);
      xhr.send(formData);
    } catch (error) {
      console.error('Upload error:', error);
      alert('Upload failed. Please try again.');
      setIsUploading(false);
      setUploadProgress(null);
    }
  };

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      handleFileUpload(file);
    }
    // Reset the input so the same file can be selected again
    event.target.value = '';
  };

  const handleDeleteChat = async (session, event) => {
    // Prevent event bubbling
    event?.stopPropagation();
    
    if (window.confirm(`Are you sure you want to delete "${session.title}"? This action cannot be undone.`)) {
      try {
        const success = await deleteChatSession(session.id, session.fileId);
        if (!success) {
          alert('Failed to delete chat. Please try again.');
        }
      } catch (error) {
        console.error('Error deleting chat:', error);
        alert('Failed to delete chat. Please try again.');
      }
    }
  };

  const handleNewChat = (document) => {
    // Select the document first
    selectDocument(document);
    
    // Create a new chat session
    const newSession = createNewChatSession(document.file_id);
    
    // Expand the file to show the new chat
    setExpandedFiles(prev => new Set([...prev, document.file_id]));
    
    // Select the new session directly instead of calling onNewChat
    if (newSession && onSelectChat) {
      onSelectChat(newSession);
    }
  };

  const handleSelectChat = (document, session) => {
    selectDocument(document);
    selectChatSession(session);
    if (onSelectChat) {
      onSelectChat(session);
    }
  };

  const handleConfigureGroups = (document) => {
    navigate(`/configure-groups/${document.id}`);
    setTimeout(() => window.scrollTo(0, 0), 100);
  };

  // Get chat sessions for a specific file
  const getChatSessionsForFile = (fileId) => {
    const sessions = getChatSessions(fileId);
    // Sort by most recent first
    return sessions.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
  };

  // Toggle file expansion
  const toggleFileExpansion = (fileId) => {
    setExpandedFiles(prev => {
      const newSet = new Set(prev);
      if (newSet.has(fileId)) {
        newSet.delete(fileId);
      } else {
        newSet.add(fileId);
      }
      return newSet;
    });
  };

  const formatChatTime = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffHours = diffMs / (1000 * 60 * 60);
    const diffDays = diffMs / (1000 * 60 * 60 * 24);

    if (diffHours < 1) {
      return 'Just now';
    } else if (diffHours < 24) {
      return `${Math.floor(diffHours)}h ago`;
    } else if (diffDays < 7) {
      return `${Math.floor(diffDays)}d ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  if (!isOpen) {
    return null;
  }

  return (
    <nav className="bg-white h-full w-full border-r border-gray-200 flex flex-col shadow-sm">
      {/* File Upload Section */}
      <div className="px-3 py-4 border-b border-gray-100">
        <div className="space-y-2">
          <input
            type="file"
            accept=".csv"
            onChange={handleFileSelect}
            className="hidden"
            id="file-upload"
            disabled={isUploading}
          />
          <label
            htmlFor="file-upload"
            className={`w-full flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-lg border-2 border-dashed transition-colors cursor-pointer ${
              isUploading
                ? 'border-blue-300 bg-blue-50 text-blue-700 cursor-not-allowed'
                : 'border-gray-300 text-gray-700 hover:border-blue-400 hover:bg-blue-50 hover:text-blue-700'
            }`}
          >
            <Upload size={18} className={isUploading ? "text-blue-500" : "text-gray-500"} />
            <span className="flex-1 text-left">
              {isUploading ? 'Uploading...' : 'Upload CSV File'}
            </span>
            {isUploading && uploadProgress !== null && (
              <span className="text-xs text-blue-600">{uploadProgress}%</span>
            )}
          </label>
          {isUploading && (
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-blue-600 h-2 rounded-full transition-all duration-300" 
                style={{ width: `${uploadProgress || 0}%` }}
              ></div>
            </div>
          )}
        </div>
      </div>

      {/* Files and Chat History */}
      <div className="flex-1 overflow-hidden flex flex-col">
        <div className="px-4 py-3 border-b border-gray-100">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Files & Chat History
            </h4>
            <span className="text-xs text-gray-400">
              {documents.length} file{documents.length !== 1 ? 's' : ''}
            </span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-2">
          {documents.length === 0 ? (
            <div className="text-center py-8">
              <FileText size={32} className="mx-auto text-gray-300 mb-3" />
              <p className="text-sm text-gray-500">No documents yet</p>
              <p className="text-xs text-gray-400 mt-1">Upload a CSV file to get started</p>
            </div>
          ) : (
            <div className="space-y-2">
              {documents.map((document) => {
                const isSelected = selectedDocument?.file_id === document.file_id;
                const isExpanded = expandedFiles.has(document.file_id);
                const chatSessions = getChatSessionsForFile(document.file_id);
                const hasActiveChat = activeChatId && chatSessions.some(session => session.id === activeChatId);
                
                return (
                  <div
                    key={document.file_id}
                    className={`rounded-lg border transition-all duration-200 ${
                      isSelected && hasActiveChat
                        ? "bg-blue-50 border-blue-200 shadow-sm"
                        : isSelected 
                        ? "bg-gray-50 border-gray-200" 
                        : "bg-white border-gray-100 hover:border-gray-200 hover:shadow-sm"
                    }`}
                  >
                    {/* File Header */}
                    <div className="p-3">
                      <div className="flex items-center justify-between">
                        <button
                          onClick={() => {
                            selectDocument(document);
                            // Auto-expand to show chat list when file is selected
                            setExpandedFiles(prev => new Set([...prev, document.file_id]));
                            if (onSelectChat) onSelectChat(null);
                          }}
                          className="flex-1 text-left flex items-start gap-3 min-w-0"
                          title="Select this file and show chat list"
                        >
                          <div className="flex-shrink-0 mt-0.5">
                            <FileText
                              size={16}
                              className={`${
                                isSelected && hasActiveChat
                                  ? "text-blue-600"
                                  : isSelected
                                  ? "text-gray-600"
                                  : "text-gray-400"
                              }`}
                            />
                          </div>
                          <div className="flex-1 min-w-0">
                            <h3
                              className={`text-sm font-medium truncate ${
                                isSelected && hasActiveChat
                                  ? "text-blue-900"
                                  : isSelected
                                  ? "text-gray-900"
                                  : "text-gray-700"
                              }`}
                            >
                              {document.filename}
                            </h3>
                            <p className="text-xs text-gray-500 mt-0.5">
                              {document.total_rows || 0} rows • {chatSessions.length} chat{chatSessions.length !== 1 ? 's' : ''}
                              {hasActiveChat && <span className="text-blue-600 ml-1">• Active</span>}
                            </p>
                          </div>
                        </button>
                        
                        {/* Expand/Collapse Button */}
                        <div className="flex items-center gap-1">
                          {/* Expand Toggle */}
                          <button
                            onClick={() => toggleFileExpansion(document.file_id)}
                            className="p-1.5 hover:bg-gray-100 rounded-md transition-colors"
                            title={isExpanded ? "Collapse chats" : "Show chats"}
                          >
                            <svg 
                              className={`w-4 h-4 text-gray-400 transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`}
                              fill="none" 
                              stroke="currentColor" 
                              viewBox="0 0 24 24"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Chat Sessions List */}
                    {isExpanded && (
                      <div className="border-t border-gray-100">
                        <div className="p-2 space-y-1">
                          {/* New Chat Button */}
                          <button
                            onClick={() => handleNewChat(document)}
                            className="w-full flex items-center gap-3 p-3 text-left bg-gradient-to-r from-blue-50 to-blue-100 hover:from-blue-100 hover:to-blue-200 rounded-lg transition-all duration-200 group border border-blue-200"
                          >
                            <div className="flex items-center justify-center w-8 h-8 bg-blue-500 rounded-lg group-hover:bg-blue-600 transition-colors">
                              <Plus size={16} className="text-white" />
                            </div>
                            <div className="flex-1">
                              <p className="text-sm font-semibold text-blue-800 group-hover:text-blue-900">
                                Start New Chat
                              </p>
                              <p className="text-xs text-blue-600">
                                Begin a fresh conversation about this data
                              </p>
                            </div>
                          </button>

                          {/* Existing Chat Sessions */}
                          {chatSessions.length > 0 && (
                            <div className="space-y-1 mt-3">
                              <div className="px-2 py-1">
                                <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                                  Previous Chats
                                </h4>
                              </div>
                              {chatSessions.map((session) => {
                                const isActiveSession = activeChatId === session.id;
                                const sessionState = getChatState ? getChatState(session.id) : null;
                                const isAIResponding = sessionState?.isAIResponding || false;
                                const isLoading = sessionState?.isLoading || false;
                                
                                return (
                                  <div
                                    key={session.id}
                                    className={`group flex items-center justify-between p-2 rounded-lg transition-all duration-200 ${
                                      isActiveSession 
                                        ? 'bg-blue-100 border border-blue-300 shadow-sm' 
                                        : 'hover:bg-gray-50 border border-transparent hover:border-gray-200'
                                    }`}
                                  >
                                    <button
                                      onClick={() => handleSelectChat(document, session)}
                                      className="flex-1 text-left min-w-0"
                                    >
                                      <div className="flex items-start gap-2">
                                        <div className="mt-1 flex-shrink-0 relative">
                                          <MessageSquare 
                                            size={12} 
                                            className={`${
                                              isActiveSession ? 'text-blue-600' : 'text-gray-400'
                                            }`} 
                                          />
                                          {isAIResponding && (
                                            <div className="absolute -top-1 -right-1 w-3 h-3 bg-blue-500 rounded-full animate-pulse">
                                              <div className="w-full h-full bg-blue-400 rounded-full animate-ping"></div>
                                            </div>
                                          )}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                          <div className="flex items-center gap-2">
                                            <p className={`text-xs font-medium truncate ${
                                              isActiveSession ? 'text-blue-900' : 'text-gray-700'
                                            }`}>
                                              {session.title}
                                            </p>
                                            {isLoading && (
                                              <div className="flex-shrink-0">
                                                <div className="w-3 h-3 border border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                                              </div>
                                            )}
                                          </div>
                                          <p className="text-xs text-gray-500 mt-0.5 flex items-center gap-1">
                                            {formatChatTime(session.updatedAt || session.createdAt)} • {session.messageCount || 0} message{(session.messageCount || 0) !== 1 ? 's' : ''}
                                            {isAIResponding && <span className="text-blue-600">• AI responding...</span>}
                                          </p>
                                        </div>
                                      </div>
                                    </button>
                                    
                                    <button
                                      onClick={(e) => handleDeleteChat(session, e)}
                                      className={`opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-100 hover:text-red-600 rounded-md transition-all ${
                                        isActiveSession ? 'opacity-100' : ''
                                      }`}
                                      title="Delete chat"
                                    >
                                      <Trash2 size={12} />
                                    </button>
                                  </div>
                                );
                              })}
                            </div>
                          )}

                          {/* Empty State for Sessions */}
                          {chatSessions.length === 0 && (
                            <div className="text-center py-4">
                              <MessageSquare size={24} className="mx-auto text-gray-300 mb-2" />
                              <p className="text-xs text-gray-500">No conversations yet</p>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </nav>
  );
};

export default ChatSidebar;
