import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

function GroupConfigurationPreview() {
  const { fileId } = useParams();
  const navigate = useNavigate();
  
  // Data states
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  
  // Configuration states
  const [useMainGroups, setUseMainGroups] = useState(true);
  const [mainGroupColumn, setMainGroupColumn] = useState('');
  const [subGroupColumn, setSubGroupColumn] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  
  // UI states
  const [currentStep, setCurrentStep] = useState(1); // 1: Preview, 2: Main Groups, 3: Sub Groups, 4: Processing

  useEffect(() => {
    fetchDataPreview();
  }, [fileId]);

  // Scroll to top when component mounts
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  const fetchDataPreview = async () => {
    setIsLoading(true);
    try {
      // Fetch file info
      const fileResponse = await fetch(`${API_BASE_URL}/api/files`);
      if (!fileResponse.ok) throw new Error('Failed to fetch file info');
      
      const filesData = await fileResponse.json();
      const currentFile = filesData.find(f => f.file_id === fileId);
      
      if (!currentFile) {
        throw new Error('File not found');
      }
      
      setSelectedFile(currentFile);
      
      // Fetch preview data
      const previewResponse = await fetch(`${API_BASE_URL}/api/file-preview/${fileId}?rows=20`);
      if (!previewResponse.ok) throw new Error('Failed to fetch preview data');
      
      const preview = await previewResponse.json();
      setPreviewData(preview);
      
    } catch (error) {
      console.error('Error fetching preview:', error);
      alert('Error loading file preview');
      navigate('/');
    } finally {
      setIsLoading(false);
    }
  };

  const handleNextStep = () => {
    if (currentStep === 1) {
      setCurrentStep(useMainGroups ? 2 : 3);
    } else if (currentStep === 2) {
      setCurrentStep(3);
    } else if (currentStep === 3) {
      startProcessing();
    }
  };

  const handlePreviousStep = () => {
    if (currentStep === 3) {
      setCurrentStep(useMainGroups ? 2 : 1);
    } else if (currentStep === 2) {
      setCurrentStep(1);
    }
  };

  const startProcessing = async () => {
    setCurrentStep(4);
    setIsProcessing(true);
    
    try {
      const configData = {
        use_main_groups: useMainGroups,
        main_group_column: useMainGroups ? mainGroupColumn : null,
        sub_group_column: subGroupColumn,
        processing_method: 'user_configured'
      };
      
      const response = await fetch(`${API_BASE_URL}/api/group-management/generate-configured/${fileId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(configData),
      });
      
      if (response.ok) {
        // Redirect to group management with success
        navigate(`/group-management/${fileId}?configured=true`);
      } else {
        const error = await response.json();
        alert(`Error processing groups: ${error.detail || error.error}`);
        setCurrentStep(3);
      }
    } catch (error) {
      console.error('Error processing groups:', error);
      alert('Error processing groups');
      setCurrentStep(3);
    } finally {
      setIsProcessing(false);
    }
  };

  const canProceedToNext = () => {
    if (currentStep === 1) return true;
    if (currentStep === 2) return mainGroupColumn !== '';
    if (currentStep === 3) return subGroupColumn !== '';
    return false;
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading preview...</p>
        </div>
      </div>
    );
  }

  if (!selectedFile || !previewData) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Preview Not Available</h2>
          <p className="text-gray-600 mb-6">Unable to load file preview.</p>
          <button 
            onClick={() => navigate('/')} 
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pt-16">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Configure AI Group Processing</h1>
              <p className="text-gray-600">{selectedFile.filename}</p>
            </div>
            <button
              onClick={() => navigate('/')}
              className="bg-gray-500 text-white px-4 py-2 rounded hover:bg-gray-600"
            >
              Cancel
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Progress Steps */}
        <div className="mb-8">
          <div className="flex items-center justify-center space-x-8">
            {[
              { step: 1, label: 'Preview Data', icon: '👁️' },
              { step: 2, label: 'Main Groups', icon: '📂', skip: !useMainGroups },
              { step: 3, label: 'Sub Groups', icon: '📁' },
              { step: 4, label: 'Processing', icon: '⚙️' }
            ].filter(item => !item.skip).map((item, index, arr) => (
              <div key={item.step} className="flex items-center">
                <div className={`flex items-center justify-center w-10 h-10 rounded-full ${
                  currentStep >= item.step ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-600'
                }`}>
                  {currentStep > item.step ? '✓' : item.icon}
                </div>
                <span className={`ml-2 text-sm font-medium ${
                  currentStep >= item.step ? 'text-blue-600' : 'text-gray-500'
                }`}>
                  {item.label}
                </span>
                {index < arr.length - 1 && (
                  <div className="w-16 h-px bg-gray-300 mx-4"></div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Step Content */}
        <div className="bg-white rounded-lg shadow-sm border">
          {/* Step 1: Preview Data */}
          {currentStep === 1 && (
            <div className="p-6">
              <h2 className="text-lg font-medium mb-4">Data Preview</h2>
              <p className="text-gray-600 mb-6">
                Here are the first 20 rows of your dataset. Review the data and choose how you want to configure AI grouping.
              </p>
              
              {/* Data Table */}
              <div className="overflow-x-auto mb-6">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      {previewData.columns.map((column, index) => (
                        <th key={index} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          {column}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {previewData.data.slice(0, 20).map((row, rowIndex) => (
                      <tr key={rowIndex} className={rowIndex % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                        {previewData.columns.map((column, colIndex) => (
                          <td key={colIndex} className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {String(row[column] || '')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Main Groups Configuration */}
              <div className="bg-blue-50 rounded-lg p-4 mb-6">
                <h3 className="text-lg font-medium text-blue-900 mb-3">Main Groups Configuration</h3>
                <div className="space-y-4">
                  <div>
                    <label className="flex items-center">
                      <input
                        type="radio"
                        name="mainGroupOption"
                        checked={useMainGroups}
                        onChange={() => setUseMainGroups(true)}
                        className="mr-3"
                      />
                      <span className="text-blue-800 font-medium">Use Main Groups</span>
                    </label>
                    <p className="text-sm text-blue-700 ml-6">
                      Create main category groups (e.g., Electronics, Furniture, Food) based on a specific column, 
                      then create sub-groups within each main group.
                    </p>
                  </div>
                  
                  <div>
                    <label className="flex items-center">
                      <input
                        type="radio"
                        name="mainGroupOption"
                        checked={!useMainGroups}
                        onChange={() => setUseMainGroups(false)}
                        className="mr-3"
                      />
                      <span className="text-blue-800 font-medium">Skip Main Groups</span>
                    </label>
                    <p className="text-sm text-blue-700 ml-6">
                      Create groups directly based on similarity and patterns without main categories.
                    </p>
                  </div>
                </div>
              </div>

              {/* Dataset Info */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="font-medium text-gray-900 mb-2">Dataset Information</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <span className="text-gray-600">Total Records:</span>
                    <span className="ml-2 font-medium">{selectedFile.total_rows}</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Columns:</span>
                    <span className="ml-2 font-medium">{previewData.columns.length}</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Showing:</span>
                    <span className="ml-2 font-medium">First 20 rows</span>
                  </div>
                  <div>
                    <span className="text-gray-600">Processing:</span>
                    <span className="ml-2 font-medium text-green-600">ALL {selectedFile.total_rows} records</span>
                  </div>
                </div>
                <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded">
                  <p className="text-sm text-green-800">
                    ✅ <strong>Full Dataset Processing:</strong> Every unique value in your selected columns will create a main group. All {selectedFile.total_rows} records will be processed and grouped.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Main Groups Column Selection */}
          {currentStep === 2 && useMainGroups && (
            <div className="p-6">
              <h2 className="text-lg font-medium mb-4">Select Main Groups Column</h2>
              <p className="text-gray-600 mb-6">
                Choose which column AI should use to create main product categories. This will be the primary way to group your products.
              </p>

              <div className="space-y-4 mb-6">
                {previewData.columns.map((column, index) => {
                  const uniqueValues = [...new Set(previewData.data.map(row => row[column]).filter(val => val && val.toString().trim() !== ''))];
                  const sampleValues = uniqueValues.slice(0, 3);
                  return (
                    <div key={index} className="border rounded-lg p-4 hover:bg-gray-50">
                      <label className="flex items-start cursor-pointer">
                        <input
                          type="radio"
                          name="mainGroupColumn"
                          value={column}
                          checked={mainGroupColumn === column}
                          onChange={(e) => setMainGroupColumn(e.target.value)}
                          className="mt-1 mr-3"
                        />
                        <div className="flex-1">
                          <div className="font-medium text-gray-900">{column}</div>
                          <div className="text-sm text-gray-600 mt-1">
                            Sample values: {sampleValues.join(', ')}
                            {uniqueValues.length > 3 && ` +${uniqueValues.length - 3} more`}
                          </div>
                          <div className="text-xs text-blue-600 mt-1">
                            📊 Will create ~{uniqueValues.length} main groups from preview data
                          </div>
                        </div>
                      </label>
                    </div>
                  );
                })}
              </div>

              <div className="bg-yellow-50 rounded-lg p-4">
                <h4 className="font-medium text-yellow-900 mb-2">💡 Important</h4>
                <p className="text-sm text-yellow-800">
                  <strong>Every unique value</strong> in this column will become a separate main group. Choose a column that contains broad category information like "Product Type", "Category", or "Department". 
                  All {selectedFile.total_rows} records will be processed and grouped.
                </p>
              </div>
            </div>
          )}

          {/* Step 3: Sub Groups Column Selection */}
          {currentStep === 3 && (
            <div className="p-6">
              <h2 className="text-lg font-medium mb-4">Select Sub Groups Column</h2>
              <p className="text-gray-600 mb-6">
                Choose which column contains the product names or item identifiers. Each unique value in this column will become a product item within the sub-groups. 
                {useMainGroups ? 'Sub-groups will be created within each main category.' : 'This will organize products into groups.'}
              </p>

              <div className="space-y-4 mb-6">
                {previewData.columns.map((column, index) => {
                  const uniqueValues = [...new Set(previewData.data.map(row => row[column]).filter(val => val && val.toString().trim() !== ''))];
                  const sampleValues = uniqueValues.slice(0, 3);
                  return (
                    <div key={index} className="border rounded-lg p-4 hover:bg-gray-50">
                      <label className="flex items-start cursor-pointer">
                        <input
                          type="radio"
                          name="subGroupColumn"
                          value={column}
                          checked={subGroupColumn === column}
                          onChange={(e) => setSubGroupColumn(e.target.value)}
                          className="mt-1 mr-3"
                        />
                        <div className="flex-1">
                          <div className="font-medium text-gray-900">{column}</div>
                          <div className="text-sm text-gray-600 mt-1">
                            Sample values: {sampleValues.join(', ')}
                            {uniqueValues.length > 3 && ` +${uniqueValues.length - 3} more`}
                          </div>
                          <div className="text-xs text-green-600 mt-1">
                            📋 Will create sub-groups with product names from this column
                          </div>
                        </div>
                      </label>
                    </div>
                  );
                })}
              </div>

              <div className="bg-blue-50 rounded-lg p-4">
                <h4 className="font-medium text-blue-900 mb-2">ℹ️ Configuration Summary</h4>
                <div className="text-sm text-blue-800 space-y-1">
                  {useMainGroups && (
                    <div>📂 Main Groups: <span className="font-medium">{mainGroupColumn}</span> (every unique value becomes a main group)</div>
                  )}
                  <div>📁 Sub Groups: <span className="font-medium">{subGroupColumn || 'Not selected'}</span> (product item names from this column)</div>
                  <div>📊 Processing: <span className="font-medium">ALL {selectedFile.total_rows} records</span> (no sampling)</div>
                  <div>🎯 Result: Each main group will show record count and contain sub-groups with individual product items</div>
                </div>
              </div>
            </div>
          )}

          {/* Step 4: Processing */}
          {currentStep === 4 && (
            <div className="p-6 text-center">
              <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <h2 className="text-lg font-medium mb-2">Processing AI Groups</h2>
              <p className="text-gray-600 mb-4">
                AI is analyzing your data using the selected columns. This may take a few minutes for large datasets.
              </p>
              <div className="bg-gray-50 rounded-lg p-4 max-w-md mx-auto">
                <div className="text-sm text-gray-600 space-y-1">
                  {useMainGroups && (
                    <div>📂 Main Groups Column: <span className="font-medium">{mainGroupColumn}</span></div>
                  )}
                  <div>📁 Sub Groups Column: <span className="font-medium">{subGroupColumn}</span></div>
                  <div>📊 Total Rows: <span className="font-medium">{selectedFile.total_rows}</span></div>
                </div>
              </div>
            </div>
          )}

          {/* Navigation */}
          {currentStep < 4 && (
            <div className="px-6 py-4 bg-gray-50 border-t flex justify-between">
              <button
                onClick={handlePreviousStep}
                disabled={currentStep === 1}
                className={`px-4 py-2 rounded ${
                  currentStep === 1 
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed' 
                    : 'bg-gray-500 text-white hover:bg-gray-600'
                }`}
              >
                Previous
              </button>
              
              <button
                onClick={handleNextStep}
                disabled={!canProceedToNext()}
                className={`px-4 py-2 rounded ${
                  !canProceedToNext() 
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed' 
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}
              >
                {currentStep === 3 ? 'Start Processing' : 'Next'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default GroupConfigurationPreview; 