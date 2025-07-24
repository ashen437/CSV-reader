import React, { useState } from 'react';

// Test component to verify error boundaries are working
const TestErrorComponent = () => {
  const [shouldThrow, setShouldThrow] = useState(false);

  if (shouldThrow) {
    throw new Error('Test error for error boundary verification');
  }

  return (
    <div className="p-4 border border-gray-300 rounded-lg bg-gray-50">
      <h3 className="text-lg font-medium text-gray-900 mb-2">Error Boundary Test</h3>
      <p className="text-sm text-gray-600 mb-4">
        This component can be used to test error boundaries in development.
      </p>
      <button
        onClick={() => setShouldThrow(true)}
        className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors"
      >
        Trigger Error
      </button>
    </div>
  );
};

export default TestErrorComponent;