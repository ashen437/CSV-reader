import React, { createContext, useContext, useState, useCallback } from 'react';

const ColumnSelectionContext = createContext();

export const useColumnSelection = () => {
  const context = useContext(ColumnSelectionContext);
  if (!context) {
    throw new Error('useColumnSelection must be used within a ColumnSelectionProvider');
  }
  return context;
};

export const ColumnSelectionProvider = ({ children }) => {
  const [availableColumns, setAvailableColumns] = useState([]);
  const [selectedColumns, setSelectedColumns] = useState(['name']);
  const [fileColumnMapping, setFileColumnMapping] = useState({}); // Store columns per file

  const updateAvailableColumns = useCallback((fileId, columns) => {
    setAvailableColumns(columns);
    setFileColumnMapping(prev => ({
      ...prev,
      [fileId]: columns
    }));
    
    // If no columns are selected or selected columns don't exist in new columns,
    // default to 'name' or first available column
    if (selectedColumns.length === 0 || !selectedColumns.some(col => columns.includes(col))) {
      const defaultColumns = [];
      if (columns.includes('name')) defaultColumns.push('name');
      else if (columns.includes('Name')) defaultColumns.push('Name');
      else if (columns.includes('item_name')) defaultColumns.push('item_name');
      else if (columns.includes('product_name')) defaultColumns.push('product_name');
      else if (columns.length > 0) defaultColumns.push(columns[0]);
      
      // Add common useful columns if they exist
      const commonColumns = ['price', 'Price', 'category', 'Category', 'quantity', 'Quantity'];
      commonColumns.forEach(col => {
        if (columns.includes(col) && !defaultColumns.includes(col)) {
          defaultColumns.push(col);
        }
      });
      
      setSelectedColumns(defaultColumns);
    }
  }, [selectedColumns]);

  const updateSelectedColumns = useCallback((columns) => {
    setSelectedColumns(columns);
  }, []);

  const getColumnsForFile = useCallback((fileId) => {
    return fileColumnMapping[fileId] || [];
  }, [fileColumnMapping]);

  const resetColumnsForFile = useCallback((fileId) => {
    const fileColumns = getColumnsForFile(fileId);
    if (fileColumns.length > 0) {
      updateAvailableColumns(fileId, fileColumns);
    }
  }, [getColumnsForFile, updateAvailableColumns]);

  const value = {
    availableColumns,
    selectedColumns,
    updateAvailableColumns,
    updateSelectedColumns,
    getColumnsForFile,
    resetColumnsForFile,
    fileColumnMapping
  };

  return (
    <ColumnSelectionContext.Provider value={value}>
      {children}
    </ColumnSelectionContext.Provider>
  );
};
