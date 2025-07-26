import React, { useEffect } from 'react';
import { useDocumentContext } from '../contexts/DocumentContext';

const DocumentSidebar = ({ isMobileOpen = false, onMobileClose = () => {} }) => {
  const { 
    documents, 
    selectedDocument, 
    selectDocument, 
    isLoading, 
    error,
    refreshDocuments,
    connectionStatus,
    retryCount
  } = useDocumentContext();

  // Helper function to format date relative to now
  const formatRelativeDate = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffInHours = Math.floor((now - date) / (1000 * 60 * 60));
    
    if (diffInHours < 1) {
      return 'Just now';
    } else if (diffInHours < 24) {
      return `${diffInHours} hour${diffInHours > 1 ? 's' : ''} ago`;
    } else {
      const diffInDays = Math.floor(diffInHours / 24);
      if (diffInDays < 7) {
        return `${diffInDays} day${diffInDays > 1 ? 's' : ''} ago`;
      } else {
        return date.toLocaleDateString();
      }
    }
  };

  // Helper function to format row count with commas
  const formatRowCount = (count) => {
    return count.toLocaleString();
  };

  // Helper function to get status badge styling
  const getStatusBadge = (status) => {
    const baseClasses = 'px-2 py-1 text-xs font-medium rounded-full';
    
    switch (status) {
      case 'completed':
        return `${baseClasses} bg-green-100 text-green-800`;
      case 'processing':
        return `${baseClasses} bg-yellow-100 text-yellow-800`;
      case 'error':
        return `${baseClasses} bg-red-100 text-red-800`;
      case 'uploaded':
      default:
        return `${baseClasses} bg-blue-100 text-blue-800`;
    }
  };

  // Handle document selection
  const handleDocumentSelect = (document) => {
    selectDocument(document);
    // Close mobile sidebar after selection
    if (isMobileOpen) {
      onMobileClose();
    }
  };

  // Render loading state
  if (isLoading && documents.length === 0) {
    return (
      <div className={`
        bg-white border-r border-gray-200 h-full
        ${isMobileOpen ? 'fixed inset-0 z-50 lg:relative lg:inset-auto' : 'hidden lg:block'}
      `}>
        {/* Mobile header with close button */}
        <div className="lg:hidden flex items-center justify-between p-4 border-b border-gray-200 bg-white">
          <h2 className="text-lg font-semibold text-gray-900">Documents</h2>
          <button
            onClick={onMobileClose}
            className="p-2 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors touch-manipulation"
            aria-label="Close document sidebar"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Desktop header */}
        <div className="hidden lg:block p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Documents</h2>
        </div>

        <div className="p-4">
          <div className="flex items-center justify-center mb-4">
            <div className="flex items-center space-x-2 text-blue-600">
              <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span className="text-sm font-medium">Loading documents...</span>
            </div>
          </div>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse">
                <div className="h-20 bg-gray-200 rounded-lg"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  // Render error state
  if (error) {
    return (
      <div className={`
        bg-white border-r border-gray-200 h-full
        ${isMobileOpen ? 'fixed inset-0 z-50 lg:relative lg:inset-auto' : 'hidden lg:block'}
      `}>
        <div className="p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Documents</h2>
          <div className="text-center py-8">
            <div className={`mb-4 ${
              connectionStatus === 'disconnected' ? 'text-yellow-500' : 'text-red-500'
            }`}>
              {connectionStatus === 'disconnected' ? (
                <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M18.364 5.636l-3.536 3.536m0 5.656l3.536 3.536M9.172 9.172L5.636 5.636m3.536 9.192L5.636 18.364M12 2v6m0 8v6m8-12h-6m-8 0h6" />
                </svg>
              ) : (
                <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
              )}
            </div>
            <h3 className="text-sm font-medium text-gray-900 mb-2">
              {connectionStatus === 'disconnected' ? 'Connection Lost' : 'Error Loading Documents'}
            </h3>
            <p className="text-gray-600 text-sm mb-4">{error}</p>
            {retryCount > 0 && (
              <p className="text-xs text-gray-500 mb-3">
                Retry attempt: {retryCount}/2
              </p>
            )}
            <div className="space-y-2">
              <button 
                onClick={() => refreshDocuments()}
                disabled={isLoading}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isLoading ? 'Retrying...' : 'Try Again'}
              </button>
              {connectionStatus === 'error' && (
                <button 
                  onClick={() => window.location.reload()}
                  className="w-full px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors"
                >
                  Refresh Page
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Handle mobile overlay behavior
  useEffect(() => {
    if (isMobileOpen) {
      // Prevent body scroll when mobile sidebar is open
      document.body.style.overflow = 'hidden';
      
      // Handle escape key to close sidebar
      const handleEscape = (e) => {
        if (e.key === 'Escape') {
          onMobileClose();
        }
      };
      
      document.addEventListener('keydown', handleEscape);
      
      return () => {
        document.body.style.overflow = 'unset';
        document.removeEventListener('keydown', handleEscape);
      };
    } else {
      document.body.style.overflow = 'unset';
    }
  }, [isMobileOpen, onMobileClose]);

  return (
    <>
      {/* Mobile overlay backdrop */}
      {isMobileOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden transition-opacity duration-300"
          onClick={onMobileClose}
          style={{ touchAction: 'none' }} // Prevent scroll on mobile
        />
      )}
      
      {/* Sidebar */}
      <div className={`
        bg-white border-r border-gray-200 h-full w-80 lg:w-full transition-transform duration-300 ease-in-out
        ${isMobileOpen 
          ? 'fixed left-0 top-0 z-50 transform translate-x-0 lg:relative lg:inset-auto lg:transform-none' 
          : 'fixed left-0 top-0 z-50 transform -translate-x-full lg:relative lg:inset-auto lg:transform-none lg:block'
        }
      `}>
        {/* Mobile header with close button */}
        <div className="lg:hidden flex items-center justify-between p-4 border-b border-gray-200 bg-white">
          <h2 className="text-lg font-semibold text-gray-900">Documents</h2>
          <button
            onClick={onMobileClose}
            className="p-2 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors touch-manipulation"
            aria-label="Close document sidebar"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Desktop header */}
        <div className="hidden lg:block p-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">Documents</h2>
            {isLoading && documents.length > 0 && (
              <div className="flex items-center space-x-2 text-blue-600">
                <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span className="text-xs">Refreshing...</span>
              </div>
            )}
          </div>
        </div>

        {/* Document list */}
        <div className="overflow-y-auto h-full">
          {documents.length === 0 ? (
            <div className="text-center py-8 px-4">
              <div className="text-gray-400 mb-4">
                <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <p className="text-gray-600 text-sm">No documents uploaded yet</p>
              <p className="text-gray-500 text-xs mt-1">Upload a CSV file to get started</p>
            </div>
          ) : (
            <div className="p-2">
              {documents.map((document) => {
                const isSelected = selectedDocument?.file_id === document.file_id;
                
                return (
                  <div
                    key={document.file_id}
                    onClick={() => handleDocumentSelect(document)}
                    className={`
                      relative p-4 mb-2 rounded-lg cursor-pointer transition-all duration-200
                      ${isSelected 
                        ? 'bg-blue-50 border-l-4 border-blue-600 shadow-sm' 
                        : 'hover:bg-gray-50 border-l-4 border-transparent'
                      }
                    `}
                  >
                    {/* Document header */}
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1 min-w-0">
                        <h3 className={`
                          text-sm font-medium truncate
                          ${isSelected ? 'text-blue-900' : 'text-gray-900'}
                        `}>
                          {document.filename}
                        </h3>
                        <p className="text-xs text-gray-500 mt-1">
                          {formatRelativeDate(document.upload_date)}
                        </p>
                      </div>
                    </div>

                    {/* Document details */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3 text-xs text-gray-600">
                        <span>{formatRowCount(document.total_rows)} rows</span>
                        {document.columns && document.columns.length > 0 && (
                          <span>{document.columns.length} columns</span>
                        )}
                      </div>
                      
                      {/* Status badge */}
                      <span className={getStatusBadge(document.status)}>
                        {document.status}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </>
  );
};

export default DocumentSidebar;