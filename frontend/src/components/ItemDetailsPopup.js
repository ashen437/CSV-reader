import React, { useState, useEffect } from 'react';

const ItemDetailsPopup = ({ 
  item, 
  subGroupItems, 
  availableColumns, 
  selectedColumns, 
  onColumnsChange, 
  onClose, 
  isOpen 
}) => {
  const [localSelectedColumns, setLocalSelectedColumns] = useState(selectedColumns);

  useEffect(() => {
    setLocalSelectedColumns(selectedColumns);
  }, [selectedColumns]);

  if (!isOpen || !item) return null;

  const handleColumnToggle = (column) => {
    const newColumns = localSelectedColumns.includes(column)
      ? localSelectedColumns.filter(col => col !== column)
      : [...localSelectedColumns, column];
    
    setLocalSelectedColumns(newColumns);
    onColumnsChange(newColumns);
  };

  const getItemValue = (item, column) => {
    // Try different ways to get the value
    if (item.row_data && item.row_data[column] !== undefined) {
      return item.row_data[column];
    }
    if (item[column] !== undefined) {
      return item[column];
    }
    // Check if column exists in any nested data
    if (item.data && item.data[column] !== undefined) {
      return item.data[column];
    }
    return 'N/A';
  };

  const formatValue = (value) => {
    if (value === null || value === undefined || value === '') {
      return 'N/A';
    }
    if (typeof value === 'number') {
      return value.toLocaleString();
    }
    return String(value);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex-1">
            <h2 className="text-xl font-semibold text-gray-900">
              Item Details: {item.name || 'Selected Item'}
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              Viewing details for the selected item
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-md text-gray-400 hover:text-gray-600 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors"
            aria-label="Close dialog"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Column Selection Panel */}
        <div className="p-4 bg-gray-50 border-b border-gray-200">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-gray-700 mr-3">
              Select columns to display:
            </span>
            <div className="flex flex-wrap gap-2">
              {availableColumns.map((column) => (
                <button
                  key={column}
                  onClick={() => handleColumnToggle(column)}
                  className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                    localSelectedColumns.includes(column)
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-gray-700 border-gray-300 hover:border-gray-400'
                  }`}
                >
                  {column}
                </button>
              ))}
            </div>
          </div>
          
          <div className="mt-2 flex items-center gap-4 text-xs text-gray-600">
            <span>
              {localSelectedColumns.length} of {availableColumns.length} columns selected
            </span>
            <button
              onClick={() => {
                setLocalSelectedColumns(availableColumns);
                onColumnsChange(availableColumns);
              }}
              className="text-blue-600 hover:text-blue-800"
            >
              Select All
            </button>
            <button
              onClick={() => {
                setLocalSelectedColumns(['name']);
                onColumnsChange(['name']);
              }}
              className="text-blue-600 hover:text-blue-800"
            >
              Reset to Name Only
            </button>
          </div>
        </div>

        {/* Table Content */}
        <div className="flex-1 overflow-auto p-6">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  {localSelectedColumns.map((column) => (
                    <th
                      key={column}
                      className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                    >
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                <tr className="bg-blue-50">
                  {localSelectedColumns.map((column) => (
                    <td
                      key={column}
                      className="px-6 py-4 whitespace-nowrap text-sm text-gray-900"
                    >
                      <div className="max-w-xs truncate" title={formatValue(getItemValue(item, column))}>
                        {formatValue(getItemValue(item, column))}
                      </div>
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
          <div className="text-sm text-gray-600">
            Showing 1 item with {localSelectedColumns.length} columns
          </div>
          <div className="flex space-x-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ItemDetailsPopup;
