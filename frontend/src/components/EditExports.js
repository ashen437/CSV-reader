import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Plus, Trash2, Download, Eye, EyeOff } from 'lucide-react';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

function EditExports() {
  const { groupId } = useParams();
  const navigate = useNavigate();
  
  const [group, setGroup] = useState(null);
  const [originalData, setOriginalData] = useState(null);
  const [availableColumns, setAvailableColumns] = useState([]);
  const [selectedColumns, setSelectedColumns] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isExporting, setIsExporting] = useState(false);
  const [previewVisible, setPreviewVisible] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState(''); // New status for detailed loading info

  useEffect(() => {
    if (groupId) {
      fetchGroupData();
    }
  }, [groupId]);

  const checkBackendHealth = async () => {
    try {
      console.log('Checking backend health at:', `${API_BASE_URL}/api/health`);
      
      // Create an AbortController for timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000); // Increased timeout
      
      const response = await fetch(`${API_BASE_URL}/api/health`, {
        method: 'GET',
        signal: controller.signal,
        // Add explicit headers to avoid CORS issues
        headers: {
          'Accept': 'application/json',
        },
        // Don't include credentials to avoid CORS issues
        credentials: 'omit'
      });
      
      clearTimeout(timeoutId);
      console.log('Health check response status:', response.status);
      console.log('Health check response ok:', response.ok);
      
      if (response.ok) {
        const data = await response.json();
        console.log('Health check response data:', data);
        return true;
      } else {
        console.log('Health check failed with status:', response.status);
        return false;
      }
    } catch (error) {
      console.log('Backend health check failed:', error);
      console.log('Error type:', error.name);
      console.log('Error message:', error.message);
      return false;
    }
  };

  const fetchGroupData = async () => {
    setIsLoading(true);
    setError(null);
    setLoadingStatus('Checking server connection...');
    
    try {
      // First, check if backend is responding
      const isBackendHealthy = await checkBackendHealth();
      console.log('Backend health check result:', isBackendHealthy);
      
      if (!isBackendHealthy) {
        console.log('Health check failed, but attempting to fetch data anyway...');
        setLoadingStatus('Health check failed, trying to load data...');
        // Don't return here - continue and try to fetch data anyway
        // The server might be running but health check might fail due to CORS or other issues
      }

      setLoadingStatus('Loading group data...');
      // Fetch the specific saved group
      const groupResponse = await fetch(`${API_BASE_URL}/api/saved-groups/${groupId}`);
      if (!groupResponse.ok) {
        if (groupResponse.status === 404) {
          throw new Error('Group not found');
        }
        throw new Error(`Failed to fetch group data: ${groupResponse.status}`);
      }
      
      const responseData = await groupResponse.json();
      
      console.log('API Response:', responseData);
      console.log('Response keys:', Object.keys(responseData));
      
      // Extract the actual group data from the response
      const selectedGroup = responseData.saved_group || responseData;
      
      console.log('Selected group:', selectedGroup);
      console.log('Group keys:', Object.keys(selectedGroup));
      console.log('Group file_id:', selectedGroup.file_id);
      console.log('Group file_name:', selectedGroup.file_name);
      
      setGroup(selectedGroup);

      // Fetch column metadata efficiently - no need to parse entire CSV
      if (selectedGroup.file_id) {
        setLoadingStatus('Loading column metadata...');
        console.log('Fetching column metadata for group:', groupId);
        
        // Retry logic for robustness
        let attempts = 0;
        const maxAttempts = 3;
        let lastError = null;
        
        while (attempts < maxAttempts) {
          try {
            if (attempts > 0) {
              // Wait a bit before retrying
              await new Promise(resolve => setTimeout(resolve, 1000 * attempts));
              console.log(`Retrying column metadata fetch, attempt ${attempts + 1}/${maxAttempts}`);
            }
            
            const columnsResponse = await fetch(`${API_BASE_URL}/api/saved-groups/${groupId}/columns`);
            console.log('Columns response status:', columnsResponse.status);
            
            if (columnsResponse.ok) {
              const columnsData = await columnsResponse.json();
              console.log('Column metadata received:', columnsData);
              console.log('Columns metadata structure:', {
                hasMetadata: !!columnsData.columns_metadata,
                metadataLength: columnsData.columns_metadata?.length || 0,
                hasAvailableColumns: !!columnsData.available_columns,
                availableColumnsLength: columnsData.available_columns?.length || 0,
                fileName: columnsData.file_name,
                totalRows: columnsData.total_rows
              });
              
              // Use the enhanced column metadata
              if (columnsData.columns_metadata && columnsData.columns_metadata.length > 0) {
                console.log('Using enhanced column metadata');
                console.log('Column metadata details:', columnsData.columns_metadata);
                setAvailableColumns(columnsData.columns_metadata);
                setOriginalData({
                  file_id: selectedGroup.file_id,
                  filename: columnsData.file_name,
                  columns_metadata: columnsData.columns_metadata,
                  total_rows: columnsData.total_rows,
                  columns: columnsData.available_columns
                });
              } else if (columnsData.available_columns && columnsData.available_columns.length > 0) {
                // Fallback to basic column names - try to migrate metadata first
                console.log('No enhanced metadata found, attempting migration...');
                
                try {
                  const migrateResponse = await fetch(`${API_BASE_URL}/api/saved-groups/${groupId}/migrate-metadata`, {
                    method: 'POST'
                  });
                  
                  if (migrateResponse.ok) {
                    const migrateResult = await migrateResponse.json();
                    console.log('Migration result:', migrateResult);
                    
                    // Retry fetching column metadata after migration
                    const retryResponse = await fetch(`${API_BASE_URL}/api/saved-groups/${groupId}/columns`);
                    if (retryResponse.ok) {
                      const retryData = await retryResponse.json();
                      if (retryData.columns_metadata && retryData.columns_metadata.length > 0) {
                        console.log('Successfully migrated and retrieved enhanced metadata');
                        setAvailableColumns(retryData.columns_metadata);
                        setOriginalData({
                          file_id: selectedGroup.file_id,
                          filename: retryData.file_name,
                          columns_metadata: retryData.columns_metadata,
                          total_rows: retryData.total_rows,
                          columns: retryData.available_columns
                        });
                        break; // Success, exit retry loop
                      }
                    }
                  }
                } catch (migrateError) {
                  console.log('Migration failed, using basic columns as fallback:', migrateError);
                }
                
                // Use basic column names as final fallback
                console.log('Using basic column names as fallback');
                const basicColumns = columnsData.available_columns.map(name => ({
                  name: name,
                  type: 'text', // Default type
                  sample_values: [],
                  null_count: 0,
                  total_count: columnsData.total_rows || 0
                }));
                console.log('Generated basic columns:', basicColumns);
                setAvailableColumns(basicColumns);
                setOriginalData({
                  file_id: selectedGroup.file_id,
                  filename: columnsData.file_name,
                  columns_metadata: basicColumns,
                  total_rows: columnsData.total_rows,
                  columns: columnsData.available_columns
                });
              } else {
                console.warn('No column data found in response');
                setError('No columns found for this saved group. The original file may be missing or corrupted.');
              }
              break; // Success, exit retry loop
              
            } else {
              console.error('Failed to fetch column metadata:', columnsResponse.status);
              
              // If new endpoint fails, try fallback to old method
              if (columnsResponse.status === 404) {
                console.log('New columns endpoint not found, trying fallback to old method...');
                try {
                  const dataResponse = await fetch(`${API_BASE_URL}/api/files/${selectedGroup.file_id}/data`);
                  if (dataResponse.ok) {
                    const originalCsvData = await dataResponse.json();
                    console.log('Fallback: Original CSV data received:', originalCsvData);
                    
                    setOriginalData(originalCsvData);
                    
                    // Extract column names from the first row of data
                    if (originalCsvData.data && originalCsvData.data.length > 0) {
                      const columns = Object.keys(originalCsvData.data[0]);
                      console.log('Fallback: Available columns extracted from data:', columns);
                      setAvailableColumns(columns);
                    } else if (originalCsvData.columns && originalCsvData.columns.length > 0) {
                      console.log('Fallback: Using columns from metadata:', originalCsvData.columns);
                      setAvailableColumns(originalCsvData.columns);
                    }
                    break; // Success with fallback
                  }
                } catch (fallbackError) {
                  console.error('Fallback method also failed:', fallbackError);
                }
              }
              
              try {
                const errorData = await columnsResponse.json();
                console.error('Error response:', errorData);
                let errorMessage = 'Failed to load column metadata';
                
                if (errorData.detail) {
                  if (errorData.detail.includes('not found')) {
                    errorMessage = 'The saved group or its original file could not be found.';
                  } else if (errorData.detail.includes('Database error')) {
                    errorMessage = 'Database connection error. Please check if the backend server is running properly.';
                  } else {
                    errorMessage = `Error: ${errorData.detail}`;
                  }
                }
                
                lastError = errorMessage;
                
                // For certain errors, don't retry
                if (errorData.detail && (
                  errorData.detail.includes('not found') || 
                  errorData.detail.includes('invalid ID format') ||
                  errorData.detail.includes('Database error')
                )) {
                  setError(errorMessage);
                  break;
                }
                
              } catch (parseError) {
                const errorText = await columnsResponse.text();
                console.error('Raw error response:', errorText);
                lastError = `Failed to load column metadata: ${columnsResponse.status}`;
              }
            }
            
          } catch (metadataError) {
            console.error('Error fetching column metadata:', metadataError);
            lastError = `Error loading column metadata: ${metadataError.message}`;
            
            // For network errors, provide specific guidance
            if (metadataError.message.includes('Failed to fetch')) {
              if (attempts === 0) {
                console.log('Network error detected on first attempt, will retry...');
                lastError = 'Backend server appears to be down. Retrying...';
              } else {
                console.log('Network error detected on retry, backend may be down');
                lastError = 'Backend server is not responding. Please check if the server is running on port 8000.';
              }
            } else if (metadataError.message.includes('CORS')) {
              lastError = 'CORS error: Backend server is not responding properly.';
            }
          }
          
          attempts++;
        }
        
        // If all attempts failed, set the last error
        if (attempts >= maxAttempts && lastError) {
          setError(lastError);
        }
        
      } else {
        console.warn('No file_id found in group:', selectedGroup);
        setError('No file ID found for this saved group - cannot load original CSV columns');
      }
      
    } catch (error) {
      console.error('Error fetching data:', error);
      
      // More specific error handling
      if (error.message.includes('Failed to fetch') || error.name === 'TypeError') {
        setError('Backend server is not responding. Please check if the server is running on port 8000.');
      } else if (error.message.includes('CORS')) {
        setError('CORS error: Backend server is not configured properly for cross-origin requests.');
      } else {
        setError(error.message);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const addColumn = (columnName) => {
    if (selectedColumns.find(col => col.name === columnName)) {
      return; // Column already added
    }

    // Determine if column is numeric by checking metadata or sample values
    const isNumeric = isColumnNumeric(columnName);
    
    const newColumn = {
      name: columnName,
      aggregationType: isNumeric ? 'sum' : 'majority', // Default based on data type
      canUseSum: true // Allow sum for all columns - users can decide what makes sense
    };
    
    setSelectedColumns([...selectedColumns, newColumn]);
  };

  const removeColumn = (columnName) => {
    setSelectedColumns(selectedColumns.filter(col => col.name !== columnName));
  };

  const updateAggregationType = (columnName, newType) => {
    setSelectedColumns(selectedColumns.map(col => 
      col.name === columnName 
        ? { ...col, aggregationType: newType }
        : col
    ));
  };

  const isColumnNumeric = (columnName) => {
    // Check if we have enhanced column metadata
    if (originalData && originalData.columns_metadata) {
      const columnMeta = originalData.columns_metadata.find(col => col.name === columnName);
      if (columnMeta) {
        // Use the pre-analyzed data type
        return columnMeta.type === 'integer' || columnMeta.type === 'decimal';
      }
    }
    
    // Fallback for older data without metadata
    if (!originalData || !originalData.data) return false;
    
    // Check first 10 rows to determine if column is numeric
    const sampleValues = originalData.data.slice(0, 10).map(row => row[columnName]);
    const numericCount = sampleValues.filter(value => {
      if (value === null || value === undefined || value === '') return false;
      return !isNaN(parseFloat(value)) && isFinite(value);
    }).length;
    
    // Consider numeric if at least 70% of sample values are numeric
    return numericCount / sampleValues.length >= 0.7;
  };

  const exportCustomExcel = async () => {
    if (selectedColumns.length === 0) {
      alert('Please add at least one column to export');
      return;
    }

    setIsExporting(true);
    try {
      const exportData = {
        group_id: groupId,
        custom_columns: selectedColumns.map(col => ({
          column_name: col.name,
          aggregation_type: col.aggregationType
        }))
      };

      console.log('Sending export request:', exportData);

      const response = await fetch(`${API_BASE_URL}/api/export-custom-excel`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(exportData),
      });

      console.log('Export response status:', response.status);
      console.log('Export response headers:', Object.fromEntries(response.headers.entries()));

      if (response.ok) {
        // Download the file
        const blob = await response.blob();
        console.log('Received blob size:', blob.size, 'bytes');
        
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${group.name}_custom_export.xlsx`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        console.log('File download initiated successfully');
      } else {
        const contentType = response.headers.get('content-type');
        let errorMessage = 'Export failed';
        
        if (contentType && contentType.includes('application/json')) {
          const errorData = await response.json();
          errorMessage = `Export failed: ${errorData.detail}`;
          console.error('Export error data:', errorData);
        } else {
          const errorText = await response.text();
          errorMessage = `Export failed (${response.status}): ${errorText}`;
          console.error('Export error text:', errorText);
        }
        
        alert(errorMessage);
      }
    } catch (error) {
      console.error('Error exporting:', error);
      alert(`Export failed: ${error.message}`);
    } finally {
      setIsExporting(false);
    }
  };

  const generatePreviewData = () => {
    if (!group || !group.structured_results) return [];
    
    const previewData = [];
    
    group.structured_results.main_groups?.forEach(mainGroup => {
      mainGroup.sub_groups?.forEach(subGroup => {
        subGroup.items?.forEach(item => {
          const row = {
            'Main Group': mainGroup.name,
            'Sub Group': subGroup.name,
            'Item Name': item.name,
            'Count': item.count
          };
          
          // Add preview values for selected columns with realistic data
          selectedColumns.forEach(col => {
            const columnMeta = originalData?.columns_metadata?.find(c => c.name === col.name);
            let previewValue = 'N/A';
            
            if (columnMeta && columnMeta.sample_values && columnMeta.sample_values.length > 0) {
              // Use actual sample values to generate realistic preview
              const samples = columnMeta.sample_values.filter(v => v !== null && v !== undefined && v !== '');
              
              if (samples.length > 0) {
                if (col.aggregationType === 'sum' && (columnMeta.type === 'integer' || columnMeta.type === 'decimal')) {
                  // For sum: show a realistic sum based on sample values
                  const numericSamples = samples.map(v => parseFloat(v)).filter(v => !isNaN(v));
                  if (numericSamples.length > 0) {
                    const avgValue = numericSamples.reduce((a, b) => a + b, 0) / numericSamples.length;
                    previewValue = (avgValue * item.count).toFixed(columnMeta.type === 'integer' ? 0 : 2);
                  }
                } else {
                  // For majority: show the first sample value
                  previewValue = samples[0];
                }
              }
            } else {
              // Fallback based on column type and aggregation
              if (col.aggregationType === 'sum') {
                previewValue = columnMeta?.type === 'integer' ? '42' : '42.50';
              } else {
                switch (columnMeta?.type) {
                  case 'integer':
                    previewValue = '10';
                    break;
                  case 'decimal':
                    previewValue = '10.5';
                    break;
                  case 'date':
                    previewValue = '2024-01-15';
                    break;
                  case 'boolean':
                    previewValue = 'true';
                    break;
                  default:
                    previewValue = 'Sample Value';
                }
              }
            }
            
            row[`${col.name} (${col.aggregationType})`] = previewValue;
          });
          
          previewData.push(row);
        });
      });
    });
    
    return previewData;
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 pt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex items-center justify-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            <div className="ml-4">
              <div className="text-gray-600">Loading export configuration...</div>
              {loadingStatus && (
                <div className="text-sm text-gray-500 mt-1">{loadingStatus}</div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    const isServerDown = error.includes('Backend server') || error.includes('CORS') || error.includes('not responding');
    
    return (
      <div className="min-h-screen bg-gray-50 pt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center">
            <div className="bg-red-50 border border-red-200 rounded-lg p-6 mb-6">
              <div className="text-red-600 mb-4 font-medium">Error Loading Export Configuration</div>
              <div className="text-red-600 mb-4">{error}</div>
              
              {isServerDown && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mt-4">
                  <div className="text-yellow-800 text-sm">
                    <strong>Server Connection Issue:</strong>
                    <br />
                    The backend server appears to be down. To fix this:
                    <br />
                    1. Open a terminal in the backend folder
                    <br />
                    2. Run: <code className="bg-gray-100 px-1 rounded">python server.py</code>
                    <br />
                    3. Wait for the server to start, then refresh this page
                  </div>
                </div>
              )}
            </div>
            
            <div className="space-y-4">
              <button
                onClick={() => window.location.reload()}
                className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 mr-4"
              >
                Retry Loading
              </button>
              <button
                onClick={() => navigate('/groups')}
                className="inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Groups
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const previewData = generatePreviewData();

  return (
    <div className="min-h-screen bg-gray-50 pt-16">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Edit Exports</h1>
              <p className="text-gray-600 mt-1">
                Customize export columns for: {group?.name}
              </p>
            </div>
            <button
              onClick={() => navigate('/groups')}
              className="inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Groups
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Available Columns */}
          <div className="bg-white rounded-lg shadow-sm border">
            <div className="p-6 border-b border-gray-200">
              <h3 className="text-lg font-medium text-gray-900">Available Columns</h3>
              <p className="text-sm text-gray-600 mt-1">
                Click to add columns from the original CSV file
              </p>
            </div>
            <div className="p-6">
              {availableColumns.length > 0 ? (
                <div className="grid grid-cols-1 gap-2">
                  {availableColumns.map(column => {
                    // Handle both new metadata format and old simple format
                    const columnName = typeof column === 'string' ? column : column.name;
                    const columnType = typeof column === 'object' ? column.type : 'text';
                    const sampleValues = typeof column === 'object' ? column.sample_values : [];
                    const isAdded = selectedColumns.find(col => col.name === columnName);
                    
                    // Debug logging
                    console.log(`Column ${columnName}: type=${columnType}, samples=`, sampleValues);
                    
                    return (
                      <button
                        key={columnName}
                        onClick={() => !isAdded && addColumn(columnName)}
                        disabled={isAdded}
                        className={`p-3 text-left rounded-lg border transition-colors ${
                          isAdded 
                            ? 'bg-gray-100 text-gray-500 cursor-not-allowed border-gray-200' 
                            : 'bg-white hover:bg-blue-50 border-gray-300 hover:border-blue-300'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex-1">
                            <span className="font-medium">{columnName}</span>
                            {sampleValues && sampleValues.length > 0 && (
                              <div className="text-xs text-gray-500 mt-1">
                                Sample: {sampleValues.slice(0, 2).join(', ')}
                                {sampleValues.length > 2 && '...'}
                              </div>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            <span className={`text-xs px-2 py-1 rounded ${
                              columnType === 'integer' 
                                ? 'bg-green-100 text-green-800' 
                                : columnType === 'decimal' 
                                ? 'bg-green-100 text-green-800'
                                : columnType === 'date'
                                ? 'bg-purple-100 text-purple-800'
                                : columnType === 'boolean'
                                ? 'bg-blue-100 text-blue-800'
                                : 'bg-gray-100 text-gray-800'
                            }`}>
                              {columnType}
                            </span>
                            {isAdded && (
                              <span className="text-xs text-gray-500">Added</span>
                            )}
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center text-gray-500 py-8">
                  {isLoading ? (
                    <div>
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-3"></div>
                      <p>Loading column metadata...</p>
                    </div>
                  ) : error ? (
                    <div className="text-red-600">
                      <p className="font-medium">Error loading columns</p>
                      <p className="text-sm mt-1">{error}</p>
                    </div>
                  ) : !group?.file_id ? (
                    <div>
                      <p className="font-medium">No file ID found</p>
                      <p className="text-sm mt-1">This saved group is missing file information</p>
                    </div>
                  ) : (
                    <div>
                      <p className="font-medium">No columns available</p>
                      <p className="text-sm mt-1">
                        {error ? 
                          'Failed to load column metadata - see error details above' : 
                          'Column metadata could not be processed. Try refreshing the page or contact support.'
                        }
                      </p>
                      {!error && (
                        <button
                          onClick={() => window.location.reload()}
                          className="mt-2 text-sm text-blue-600 hover:text-blue-800 underline"
                        >
                          Refresh Page
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Selected Columns */}
          <div className="bg-white rounded-lg shadow-sm border">
            <div className="p-6 border-b border-gray-200">
              <h3 className="text-lg font-medium text-gray-900">Selected Columns</h3>
              <p className="text-sm text-gray-600 mt-1">
                Configure aggregation type for each column
              </p>
            </div>
            <div className="p-6">
              {selectedColumns.length > 0 ? (
                <div className="space-y-4">
                  {selectedColumns.map(column => (
                    <div key={column.name} className="p-4 border rounded-lg">
                      <div className="flex items-center justify-between mb-3">
                        <span className="font-medium">{column.name}</span>
                        <button
                          onClick={() => removeColumn(column.name)}
                          className="text-red-600 hover:text-red-800"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                      <div className="space-y-2">
                        <label className="text-sm font-medium text-gray-700">
                          Aggregation Type:
                        </label>
                        <div className="space-y-2">
                          <label className="flex items-center">
                            <input
                              type="radio"
                              name={`agg_${column.name}`}
                              value="majority"
                              checked={column.aggregationType === 'majority'}
                              onChange={(e) => updateAggregationType(column.name, e.target.value)}
                              className="mr-2"
                            />
                            <span className="text-sm">Majority Value</span>
                            <span className="text-xs text-gray-500 ml-2">
                              (Most common value)
                            </span>
                          </label>
                          <label className="flex items-center">
                            <input
                              type="radio"
                              name={`agg_${column.name}`}
                              value="sum"
                              checked={column.aggregationType === 'sum'}
                              onChange={(e) => updateAggregationType(column.name, e.target.value)}
                              disabled={!column.canUseSum}
                              className="mr-2"
                            />
                            <span className={`text-sm ${!column.canUseSum ? 'text-gray-400' : ''}`}>
                              Sum Values
                            </span>
                            <span className="text-xs text-gray-500 ml-2">
                              (Add all values together)
                            </span>
                          </label>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center text-gray-500 py-8">
                  <Plus className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                  <p>No columns selected</p>
                  <p className="text-sm mt-1">Add columns from the left panel</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="mt-8 bg-white rounded-lg shadow-sm border p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => setPreviewVisible(!previewVisible)}
                className="inline-flex items-center px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              >
                {previewVisible ? <EyeOff className="w-4 h-4 mr-2" /> : <Eye className="w-4 h-4 mr-2" />}
                {previewVisible ? 'Hide Preview' : 'Show Preview'}
              </button>
              <span className="text-sm text-gray-500">
                {selectedColumns.length} column{selectedColumns.length !== 1 ? 's' : ''} selected
              </span>
            </div>
            <button
              onClick={exportCustomExcel}
              disabled={isExporting || selectedColumns.length === 0}
              className="inline-flex items-center px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Download className="w-4 h-4 mr-2" />
              {isExporting ? 'Exporting...' : 'Export to Excel'}
            </button>
          </div>
        </div>

        {/* Preview */}
        {previewVisible && previewData.length > 0 && (
          <div className="mt-6 bg-white rounded-lg shadow-sm border">
            <div className="p-6 border-b border-gray-200">
              <h3 className="text-lg font-medium text-gray-900">Export Preview</h3>
              <p className="text-sm text-gray-600 mt-1">
                Preview of the first few rows with realistic sample values based on your data
              </p>
            </div>
            <div className="p-6 overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    {Object.keys(previewData[0] || {}).map(header => (
                      <th key={header} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {previewData.slice(0, 5).map((row, index) => (
                    <tr key={index}>
                      {Object.values(row).map((cell, cellIndex) => (
                        <td key={cellIndex} className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {previewData.length > 5 && (
                <div className="text-center text-gray-500 text-sm mt-4">
                  ... and {previewData.length - 5} more rows
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default EditExports;
