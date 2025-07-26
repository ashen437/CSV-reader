import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

function Groups() {
  const navigate = useNavigate();
  const [savedGroups, setSavedGroups] = useState([]);
  const [selectedGroup, setSelectedGroup] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  
  // Collapsible bars state
  const [isSummaryCollapsed, setIsSummaryCollapsed] = useState(false);
  const [collapsedMainGroups, setCollapsedMainGroups] = useState({});
  
  // Export dropdown state
  const [isExportDropdownOpen, setIsExportDropdownOpen] = useState(false);

  // Fetch saved groups on component mount
  useEffect(() => {
    fetchSavedGroups();
  }, []);

  // Close export dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (isExportDropdownOpen && !event.target.closest('.export-dropdown-container')) {
        setIsExportDropdownOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isExportDropdownOpen]);

  const fetchSavedGroups = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/saved-groups`);
      if (response.ok) {
        const data = await response.json();
        setSavedGroups(data.saved_groups || []);
      } else {
        setError('Failed to fetch saved groups');
      }
    } catch (error) {
      console.error('Error fetching saved groups:', error);
      setError('Error fetching saved groups');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGroupSelect = (group) => {
    setSelectedGroup(group);
    // Reset collapsed state when selecting a new group
    setCollapsedMainGroups({});
  };

  const toggleMainGroup = (mainIndex) => {
    setCollapsedMainGroups(prev => ({
      ...prev,
      [mainIndex]: !prev[mainIndex]
    }));
  };

  const handleDeleteGroup = async (groupId, groupName) => {
    if (!window.confirm(`Are you sure you want to delete "${groupName}"?`)) {
      return;
    }

    setIsDeleting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/saved-groups/${groupId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        // Remove from local state
        setSavedGroups(prev => prev.filter(g => g._id !== groupId));
        
        // Clear selection if deleted group was selected
        if (selectedGroup && selectedGroup._id === groupId) {
          setSelectedGroup(null);
        }
        
        alert('Group deleted successfully');
      } else {
        const error = await response.json();
        alert(`Error deleting group: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error deleting group:', error);
      alert('Error deleting group');
    } finally {
      setIsDeleting(false);
    }
  };

  const formatDate = (dateString) => {
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return 'Unknown date';
    }
  };

  const copyToClipboard = (group) => {
    const structuredResults = group.structured_results;
    let text = `${group.name.toUpperCase()}\n`;
    text += `Created: ${formatDate(group.created_at)}\n\n`;
    text += `SUMMARY:\n`;
    text += `- Total Items: ${structuredResults.total_items}\n`;
    text += `- Main Groups: ${structuredResults.total_groups}\n`;
    text += `- Sub Groups: ${structuredResults.total_sub_groups}\n\n`;
    
    structuredResults.main_groups?.forEach((mainGroup) => {
      text += `Main Group: ${mainGroup.name}\n`;
      text += `  (${mainGroup.total_items} items)\n\n`;
      
      mainGroup.sub_groups?.forEach((subGroup) => {
        text += `  Sub Group: ${subGroup.name}\n`;
        text += `    (${subGroup.total_items} items)\n`;
        
        subGroup.items?.forEach((item) => {
          text += `    - ${item.name} (${item.count})\n`;
        });
        text += `\n`;
      });
      text += `\n`;
    });
    
    if (structuredResults.ungrouped_items_count > 0) {
      text += `Ungrouped Items: ${structuredResults.ungrouped_items_count}\n`;
      text += `These items couldn't be automatically grouped and may need manual review.\n`;
    }
    
    navigator.clipboard.writeText(text).then(() => {
      alert('Group data copied to clipboard!');
    });
  };

  const exportToExcel = async (group) => {
    try {
      console.log('Starting Excel export for group:', group.name);
      
      const response = await fetch(`${API_BASE_URL}/api/saved-groups/${group._id}/export-excel`, {
        method: 'GET',
        headers: {
          'Accept': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        },
      });

      console.log('Export response status:', response.status);

      if (!response.ok) {
        let errorMessage = 'Failed to export to Excel';
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch (e) {
          console.log('Could not parse error response as JSON');
        }
        throw new Error(errorMessage);
      }

      // Check if response is actually an Excel file
      const contentType = response.headers.get('content-type');
      console.log('Response content type:', contentType);
      
      if (!contentType || !contentType.includes('spreadsheet')) {
        throw new Error('Server did not return an Excel file');
      }

      // Create a blob from the response
      const blob = await response.blob();
      console.log('Blob size:', blob.size, 'bytes');
      
      if (blob.size === 0) {
        throw new Error('Received empty file from server');
      }
      
      // Create a temporary URL for the blob
      const url = window.URL.createObjectURL(blob);
      
      // Create a temporary anchor element and trigger download
      const a = document.createElement('a');
      a.href = url;
      a.download = `${group.name.replace(/[^a-zA-Z0-9]/g, '_')}_export.xlsx`;
      document.body.appendChild(a);
      a.click();
      
      // Clean up
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      console.log('Excel export completed successfully');
      alert('Excel file downloaded successfully!');
    } catch (error) {
      console.error('Error exporting to Excel:', error);
      console.error('Error details:', {
        message: error.message,
        stack: error.stack
      });
      alert(`Error exporting to Excel: ${error.message}`);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 pt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex items-center justify-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            <span className="ml-4 text-gray-600">Loading saved groups...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pt-16">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex gap-6 h-[calc(100vh-120px)]">
          {/* Left Sidebar - Saved Groups List */}
          <div className="w-1/3 bg-white rounded-lg shadow-sm border overflow-hidden">
            <div className="p-4 border-b bg-gray-50">
              <h3 className="font-medium text-gray-900">Saved Groups ({savedGroups.length})</h3>
            </div>
            
            <div className="overflow-y-auto h-full">
              {error && (
                <div className="p-4 text-red-600 text-sm">
                  {error}
                </div>
              )}
              
              {savedGroups.length === 0 ? (
                <div className="p-6 text-center text-gray-500">
                  <div className="mb-4">
                    <svg className="mx-auto h-12 w-12 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                    </svg>
                  </div>
                  <p className="text-sm">No saved groups yet</p>
                  <p className="text-xs text-gray-400 mt-1">
                    Create groups in Group Management and save them to see them here
                  </p>
                </div>
              ) : (
                <div className="space-y-1 p-2">
                  {savedGroups.map((group) => (
                    <div
                      key={group._id}
                      className={`p-3 rounded-lg cursor-pointer transition-colors ${
                        selectedGroup?._id === group._id
                          ? 'bg-blue-50 border-2 border-blue-200'
                          : 'hover:bg-gray-50 border border-transparent'
                      }`}
                      onClick={() => handleGroupSelect(group)}
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex-1 min-w-0">
                          <h4 className="font-medium text-gray-900 truncate">
                            {group.name}
                          </h4>
                          <div className="flex items-center mt-2 text-xs text-gray-500">
                            <span>{formatDate(group.created_at)}</span>
                            <span className="mx-2">•</span>
                            <span>{group.structured_results?.total_items || 0} items</span>
                            <span className="mx-2">•</span>
                            <span>{group.structured_results?.total_groups || 0} groups</span>
                          </div>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteGroup(group._id, group.name);
                          }}
                          disabled={isDeleting}
                          className="ml-2 text-red-500 hover:text-red-700 p-1"
                          title="Delete group"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Content - Selected Group Details */}
          <div className="flex-1 bg-white rounded-lg shadow-sm border overflow-hidden">
            {selectedGroup ? (
              <div className="h-full flex flex-col">
                {/* Collapsible Group Summary */}
                <div className="border-b bg-gray-50">
                  {/* Summary Toggle Bar */}
                  <div 
                    className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-100 transition-colors"
                    onClick={() => setIsSummaryCollapsed(!isSummaryCollapsed)}
                  >
                    <h3 className="font-medium text-gray-900">{selectedGroup.name}</h3>
                    <div className="flex items-center gap-3">
                      {/* Edit Button */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/edit-groups/${selectedGroup._id}`);
                        }}
                        className="px-3 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
                      >
                        <svg className="w-4 h-4 mr-2 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                        Edit
                      </button>
                      
                      {/* Export Dropdown */}
                      <div className="relative export-dropdown-container">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setIsExportDropdownOpen(!isExportDropdownOpen);
                          }}
                          className="btn-primary flex items-center"
                        >
                          Export
                          <svg 
                            className={`ml-2 w-4 h-4 transition-transform ${isExportDropdownOpen ? 'rotate-180' : ''}`}
                            fill="none" 
                            stroke="currentColor" 
                            viewBox="0 0 24 24"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </button>
                        
                        {/* Dropdown Menu */}
                        {isExportDropdownOpen && (
                          <div className="absolute right-0 mt-2 w-56 bg-white rounded-md shadow-lg border z-10">
                            <div className="py-1">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  exportToExcel(selectedGroup);
                                  setIsExportDropdownOpen(false);
                                }}
                                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center"
                              >
                                <svg className="w-4 h-4 mr-3 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                </svg>
                                Export as Excel
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  copyToClipboard(selectedGroup);
                                  setIsExportDropdownOpen(false);
                                }}
                                className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center"
                              >
                                <svg className="w-4 h-4 mr-3 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V9a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                                </svg>
                                Copy to Clipboard
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                      
                      <svg 
                        className={`w-5 h-5 text-gray-500 transition-transform ${isSummaryCollapsed ? 'rotate-180' : ''}`}
                        fill="none" 
                        stroke="currentColor" 
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </div>
                  
                  {/* Collapsible Summary Content */}
                  {!isSummaryCollapsed && (
                    <div className="px-6 py-6">
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                        <div>
                          <span className="font-medium">Total Items:</span> {selectedGroup.structured_results?.total_items || 0}
                        </div>
                        <div>
                          <span className="font-medium">Main Groups:</span> {selectedGroup.structured_results?.total_groups || 0}
                        </div>
                        <div>
                          <span className="font-medium">Sub Groups:</span> {selectedGroup.structured_results?.total_sub_groups || 0}
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Group Content */}
                <div className="flex-1 overflow-y-auto p-6">
                  <div className="space-y-6">
                    {selectedGroup.structured_results?.main_groups?.map((mainGroup, mainIndex) => (
                      <div key={mainIndex} className="border rounded-lg overflow-hidden">
                        {/* Main Group Header - Collapsible */}
                        <div 
                          className="bg-gray-50 border-b cursor-pointer hover:bg-gray-100 transition-colors"
                          onClick={() => toggleMainGroup(mainIndex)}
                        >
                          <div className="flex items-center justify-between p-4">
                            <h4 className="text-lg font-semibold text-gray-900">
                              Main Group: {mainGroup.name}
                              <span className="text-sm font-normal text-gray-600 ml-2">
                                ({mainGroup.total_items} items)
                              </span>
                            </h4>
                            <svg 
                              className={`w-5 h-5 text-gray-500 transition-transform ${collapsedMainGroups[mainIndex] ? 'rotate-180' : ''}`}
                              fill="none" 
                              stroke="currentColor" 
                              viewBox="0 0 24 24"
                            >
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                          </div>
                        </div>
                        
                        {/* Collapsible Sub Groups Content */}
                        {!collapsedMainGroups[mainIndex] && (
                          <div className="p-4">
                            {/* Sub Groups */}
                            <div className="space-y-4">
                              {mainGroup.sub_groups?.map((subGroup, subIndex) => (
                                <div key={subIndex} className="bg-gray-50 rounded-lg p-4">
                                  <h5 className="text-md font-medium text-gray-800 mb-3">
                                    Sub Group: {subGroup.name}
                                    <span className="text-sm font-normal text-gray-600 ml-2">
                                      ({subGroup.total_items} items)
                                    </span>
                                  </h5>
                                  
                                  {/* Items */}
                                  <div className="space-y-2 ml-4">
                                    {subGroup.items?.map((item, itemIndex) => (
                                      <div key={itemIndex} className="flex justify-between items-center py-1 border-b border-gray-200 last:border-b-0">
                                        <span className="text-gray-700">- {item.name}</span>
                                        <span className="text-sm font-medium text-blue-600">({item.count})</span>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                    
                    {selectedGroup.structured_results?.ungrouped_items_count > 0 && (
                      <div className="border border-orange-200 rounded-lg p-4 bg-orange-50">
                        <h4 className="text-lg font-semibold text-orange-900 mb-2">
                          Ungrouped Items: {selectedGroup.structured_results.ungrouped_items_count}
                        </h4>
                        <p className="text-sm text-orange-700">
                          These items couldn't be automatically grouped and may need manual review.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-gray-500">
                <div className="text-center">
                  <svg className="mx-auto h-12 w-12 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p className="mt-4">Select a saved group to view details</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Groups;
