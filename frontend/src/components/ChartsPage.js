import React, { useState } from 'react';
import NavigationBar from './NavigationBar';
import NavigationErrorBoundary from './NavigationErrorBoundary';
import ErrorBoundary from './ErrorBoundary';
import DocumentSidebar from './DocumentSidebar';
import ChatInterface from './ChatInterface';

const ChartsPage = () => {
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  const handleMobileSidebarToggle = () => {
    setIsMobileSidebarOpen(!isMobileSidebarOpen);
  };

  const handleMobileSidebarClose = () => {
    setIsMobileSidebarOpen(false);
  };

  // Handle swipe gestures for mobile sidebar
  const [touchStart, setTouchStart] = useState(null);
  const [touchEnd, setTouchEnd] = useState(null);

  const handleTouchStart = (e) => {
    setTouchEnd(null);
    setTouchStart(e.targetTouches[0].clientX);
  };

  const handleTouchMove = (e) => {
    setTouchEnd(e.targetTouches[0].clientX);
  };

  const handleTouchEnd = () => {
    if (!touchStart || !touchEnd) return;
    
    const distance = touchStart - touchEnd;
    const isLeftSwipe = distance > 50;
    const isRightSwipe = distance < -50;

    // Close sidebar on left swipe, open on right swipe from left edge
    if (isLeftSwipe && isMobileSidebarOpen) {
      handleMobileSidebarClose();
    } else if (isRightSwipe && !isMobileSidebarOpen && touchStart < 50) {
      setIsMobileSidebarOpen(true);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <NavigationErrorBoundary>
        <NavigationBar />
      </NavigationErrorBoundary>
      
      {/* Mobile header with sidebar toggle */}
      <div className="lg:hidden flex items-center justify-between p-3 sm:p-4 bg-white border-b border-gray-200">
        <button
          onClick={handleMobileSidebarToggle}
          className="p-2 rounded-md text-gray-600 hover:text-gray-900 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors touch-manipulation active:bg-gray-200"
          aria-label="Toggle document sidebar"
        >
          <svg className="w-5 h-5 sm:w-6 sm:h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <h1 className="text-base sm:text-lg font-semibold text-gray-900">Charts</h1>
        <div className="w-9 sm:w-10"></div> {/* Spacer for centering */}
      </div>

      {/* Main content area with two-panel layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Desktop: Two-panel grid layout */}
        <div className="hidden lg:grid lg:grid-cols-[300px_1fr] lg:h-full lg:w-full">
          {/* Left sidebar - Document list */}
          <div className="border-r border-gray-200 bg-white">
            <ErrorBoundary fallbackMessage="Error loading document list. Please refresh the page.">
              <DocumentSidebar 
                isMobileOpen={false}
                onMobileClose={() => {}}
              />
            </ErrorBoundary>
          </div>
          
          {/* Right panel - Chat interface */}
          <div className="bg-white">
            <ErrorBoundary fallbackMessage="Error loading chat interface. Please refresh the page.">
              <ChatInterface />
            </ErrorBoundary>
          </div>
        </div>

        {/* Mobile: Single column with overlay sidebar */}
        <div 
          className="lg:hidden flex-1 relative"
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
          onTouchEnd={handleTouchEnd}
        >
          {/* Mobile sidebar overlay */}
          <ErrorBoundary fallbackMessage="Error loading document list. Please refresh the page.">
            <DocumentSidebar 
              isMobileOpen={isMobileSidebarOpen}
              onMobileClose={handleMobileSidebarClose}
            />
          </ErrorBoundary>
          
          {/* Mobile chat interface (always visible) */}
          <div className="h-full bg-white">
            <ErrorBoundary fallbackMessage="Error loading chat interface. Please refresh the page.">
              <ChatInterface />
            </ErrorBoundary>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChartsPage;