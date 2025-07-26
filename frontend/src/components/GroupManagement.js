import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import ItemDetailsPopup from './ItemDetailsPopup';
import { useColumnSelection } from '../contexts/ColumnSelectionContext';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

function GroupManagement() {
  const { fileId } = useParams();
  const navigate = useNavigate();
  const [selectedFile, setSelectedFile] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  
  // Group Management States
  const [groupManagementData, setGroupManagementData] = useState(null);
  const [isGeneratingGroups, setIsGeneratingGroups] = useState(false);
  const [structuredPlans, setStructuredPlans] = useState([]);
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [groupManagementMode, setGroupManagementMode] = useState(null); // 'fresh' or 'plan'
  const [isLoadingPlans, setIsLoadingPlans] = useState(false);
  const [isSavingPlan, setIsSavingPlan] = useState(false);
  const [validationResults, setValidationResults] = useState(null);

  // Final Results States
  const [finalResults, setFinalResults] = useState(null);
  const [isSavingFinalResults, setIsSavingFinalResults] = useState(false);
  const [isLoadingFinalResults, setIsLoadingFinalResults] = useState(false);
  const [showSaveGroupModal, setShowSaveGroupModal] = useState(false);
  const [groupName, setGroupName] = useState('');

  // UI States
  const [selectedItems, setSelectedItems] = useState(new Set());
  const [editingGroup, setEditingGroup] = useState(null);
  const [editingSubGroup, setEditingSubGroup] = useState(null);
  const [showAddGroupModal, setShowAddGroupModal] = useState(false);
  const [showAddSubGroupModal, setShowAddSubGroupModal] = useState(false);
  const [showSavePlanModal, setShowSavePlanModal] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState(new Set());
  const [selectedGroupForMove, setSelectedGroupForMove] = useState(null);
  const [selectedSubGroupForMove, setSelectedSubGroupForMove] = useState(null);

  // Item Details Popup States
  const [showItemDetails, setShowItemDetails] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [selectedSubGroupItems, setSelectedSubGroupItems] = useState([]);
  
  // Column Selection Context
  const { 
    availableColumns, 
    selectedColumns, 
    updateAvailableColumns, 
    updateSelectedColumns 
  } = useColumnSelection();

  // Fetch file data and structured plans on component mount
  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        // Fetch file data
        const fileResponse = await fetch(`${API_BASE_URL}/api/files`);
        if (!fileResponse.ok) {
          throw new Error('Files not found');
        }
        const filesData = await fileResponse.json();
        const currentFile = filesData.find(f => f.file_id === fileId);
        
        if (!currentFile) {
          throw new Error('File not found');
        }
        
        setSelectedFile(currentFile);
        
        // Load structured plans
        await loadStructuredPlans();
        
        // Check if groups already exist for this file
        try {
          const groupResponse = await fetch(`${API_BASE_URL}/api/group-management/${fileId}`);
          if (groupResponse.ok) {
            const groupData = await groupResponse.json();

            setGroupManagementData(groupData.groups_data);
            setValidationResults(groupData.groups_data?.validation);
            setGroupManagementMode('fresh');
            // Expand all groups by default
            if (groupData.groups_data?.groups) {
              setExpandedGroups(new Set(groupData.groups_data.groups.map((g, i) => g.id || i)));
            }
          } else {
            // No existing groups, auto-generate them
            await autoGenerateGroups();
          }
        } catch (error) {
          // No existing groups, auto-generate them
          await autoGenerateGroups();
        }
        
      } catch (error) {
        console.error('Error fetching data:', error);
        navigate('/'); // Redirect back to main dashboard if file not found
      } finally {
        setIsLoading(false);
      }
    };

    const autoGenerateGroups = async () => {
      setIsGeneratingGroups(true);
      try {
        const response = await fetch(`${API_BASE_URL}/api/group-management/generate/${fileId}`, {
          method: 'POST',
        });
        
        if (response.ok) {
          const data = await response.json();

          setGroupManagementData(data);
          setValidationResults(data.validation);
          setGroupManagementMode('fresh');
          // Expand all groups by default
          if (data?.groups) {
            setExpandedGroups(new Set(data.groups.map((g, i) => g.id || i)));
          }
        } else {
          const error = await response.json();
          console.error('Error auto-generating groups:', error.detail);
        }
      } catch (error) {
        console.error('Error auto-generating groups:', error);
      } finally {
        setIsGeneratingGroups(false);
      }
    };
    
    if (fileId) {
      fetchData();
    }
  }, [fileId, navigate]);

  const loadStructuredPlans = async () => {
    setIsLoadingPlans(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/structured-plans`);
      if (response.ok) {
        const data = await response.json();
        setStructuredPlans(data.plans || []);
      }
    } catch (error) {
      console.error('Error loading structured plans:', error);
    } finally {
      setIsLoadingPlans(false);
    }
  };

  const applyStructuredPlan = async (planId) => {
    if (!selectedFile) return;
    
    setIsGeneratingGroups(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/structured-plans/apply/${fileId}/${planId}`, {
        method: 'POST',
      });
      
      if (response.ok) {
        const data = await response.json();
        setGroupManagementData(data);
        setValidationResults(data.validation);
        setGroupManagementMode('plan');
        // Expand all groups by default
        if (data?.groups) {
          setExpandedGroups(new Set(data.groups.map((g, i) => g.id || i)));
        }
        setSelectedItems(new Set());
      } else {
        const error = await response.json();
        alert(`Error applying plan: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error applying plan:', error);
      alert('Error applying structured plan');
    } finally {
      setIsGeneratingGroups(false);
    }
  };

  const updateGroupManagement = async (updateRequest) => {
    if (!selectedFile) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/group-management/update/${fileId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updateRequest),
      });
      
      if (response.ok) {
        const data = await response.json();
        setGroupManagementData(data);
        // Update validation results if available
        if (data.validation) {
          setValidationResults(data.validation);
        }
      } else {
        const error = await response.json();
        alert(`Error updating groups: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error updating groups:', error);
      alert('Error updating group management');
    }
  };

  const handleAddMainGroup = async (groupName) => {
    await updateGroupManagement({
      action: "add_main_group",
      data: { name: groupName }
    });
    setShowAddGroupModal(false);
  };

  const handleDeleteMainGroup = async (groupId) => {
    if (window.confirm('Are you sure you want to delete this group? All items will be moved to ungrouped.')) {
      await updateGroupManagement({
        action: "delete_main_group",
        group_id: groupId
      });
    }
  };

  const handleAddSubGroup = async (groupId, subGroupName) => {
    await updateGroupManagement({
      action: "add_sub_group",
      group_id: groupId,
      data: { name: subGroupName }
    });
    setShowAddSubGroupModal(false);
  };

  const handleDeleteSubGroup = async (groupId, subGroupId) => {
    if (window.confirm('Are you sure you want to delete this sub-group? All items will be moved to ungrouped.')) {
      await updateGroupManagement({
        action: "delete_sub_group",
        group_id: groupId,
        sub_group_id: subGroupId
      });
    }
  };

  const handleToggleGroup = async (groupId) => {
    await updateGroupManagement({
      action: "toggle_group",
      group_id: groupId
    });
  };

  const handleMoveSelectedItems = async () => {
    if (selectedItems.size === 0 || !selectedGroupForMove) {
      alert('Please select items and a target group');
      return;
    }

    await updateGroupManagement({
      action: "move_multiple_items",
      target_group_id: selectedGroupForMove,
      target_sub_group_id: selectedSubGroupForMove,
      data: { item_ids: Array.from(selectedItems) }
    });

    setSelectedItems(new Set());
    setSelectedGroupForMove(null);
    setSelectedSubGroupForMove(null);
  };

  const handleItemSelection = (itemId) => {
    const newSelection = new Set(selectedItems);
    if (newSelection.has(itemId)) {
      newSelection.delete(itemId);
    } else {
      newSelection.add(itemId);
    }
    setSelectedItems(newSelection);
  };

  const handleSelectAllUngrouped = () => {
    if (!groupManagementData?.ungrouped_items) return;
    
    const allUngroupedIds = new Set(groupManagementData.ungrouped_items.map(item => item.id));
    setSelectedItems(allUngroupedIds);
  };

  const handleUpdateGroupName = async (groupId, newName) => {
    await updateGroupManagement({
      action: "update_group_name",
      group_id: groupId,
      data: { name: newName }
    });
    setEditingGroup(null);
  };

  const handleUpdateSubGroupName = async (groupId, subGroupId, newName) => {
    await updateGroupManagement({
      action: "update_sub_group_name",
      group_id: groupId,
      sub_group_id: subGroupId,
      data: { name: newName }
    });
    setEditingSubGroup(null);
  };

  const handleRemoveFromSubGroup = async (groupId, subGroupId, itemId) => {
    await updateGroupManagement({
      action: "remove_from_sub_group",
      group_id: groupId,
      sub_group_id: subGroupId,
      item_id: itemId
    });
  };

  const handleMoveToMainGroupUngrouped = async (itemId, mainGroupId) => {
    await updateGroupManagement({
      action: "move_item",
      item_id: itemId,
      target_group_id: "main_group_ungrouped",
      data: { main_group_id: mainGroupId }
    });
  };

  // Extract columns from items data as fallback
  const extractAndSetColumns = (items) => {
    if (items && items.length > 0) {
      const allColumns = new Set();
      items.forEach(item => {
        if (item && typeof item === 'object') {
          Object.keys(item).forEach(key => {
            allColumns.add(key);
          });
        }
      });
      updateAvailableColumns(fileId, Array.from(allColumns));
    }
  };

  // Item Details Popup Handlers
  const handleItemClick = async (item, subGroupItems = []) => {
    setSelectedItem(item);
    setSelectedSubGroupItems(subGroupItems);
    setShowItemDetails(true);
    
    // Try to get columns from backend first, fallback to extracting from items
    try {
      const response = await fetch(`${API_BASE_URL}/api/file-columns/${fileId}`);
      if (response.ok) {
        const data = await response.json();
        updateAvailableColumns(fileId, data.columns);
      } else {
        // Fallback: extract columns from items
        const allItems = [item, ...subGroupItems];
        extractAndSetColumns(allItems);
      }
    } catch (error) {
      console.error('Error fetching columns:', error);
      // Fallback: extract columns from items
      const allItems = [item, ...subGroupItems];
      extractAndSetColumns(allItems);
    }
  };

  const handleCloseItemDetails = () => {
    setShowItemDetails(false);
    setSelectedItem(null);
    setSelectedSubGroupItems([]);
  };

  const saveStructuredPlan = async (planName, description) => {
    if (!selectedFile || !groupManagementData) return;
    
    setIsSavingPlan(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/structured-plans/save/${fileId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name: planName, description: description }),
      });
      
      if (response.ok) {
        const result = await response.json();
        alert('Structured plan saved successfully!');
        loadStructuredPlans(); // Refresh plans list
        setShowSavePlanModal(false);
        return result.plan_id;
      } else {
        const error = await response.json();
        alert(`Error saving plan: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error saving plan:', error);
      alert('Error saving structured plan');
    } finally {
      setIsSavingPlan(false);
    }
  };

  // Final Results Functions
  const saveGroupWithName = async () => {
    if (!groupName.trim()) {
      alert('Please enter a group name');
      return;
    }

    if (!finalResults) {
      alert('No final results available to save');
      return;
    }

    setIsSavingFinalResults(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/saved-groups`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: groupName.trim(),
          description: `AI-grouped results for ${selectedFile?.filename || 'file'}`,
          structured_results: finalResults.structured_results || finalResults,
          file_id: fileId,
          created_at: new Date().toISOString()
        }),
      });
      
      if (response.ok) {
        const result = await response.json();
        alert('Final results saved successfully! You can view it in the Saved Groups tab.');
        setShowSaveGroupModal(false);
        setGroupName('');
      } else {
        console.error('Save failed with status:', response.status);
        try {
          const errorData = await response.json();
          console.error('Error details:', errorData);
          alert(`Error saving group: ${errorData.detail || JSON.stringify(errorData)}`);
        } catch (parseError) {
          console.error('Could not parse error response:', parseError);
          const errorText = await response.text();
          console.error('Raw error response:', errorText);
          alert(`Error saving group: ${response.status} - ${errorText}`);
        }
      }
    } catch (error) {
      console.error('Error saving group:', error);
      alert(`Error saving group: ${error.message}`);
    } finally {
      setIsSavingFinalResults(false);
    }
  };

  const loadFinalResults = async () => {
    setIsLoadingFinalResults(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/final-results/structured/${fileId}`);
      
      if (response.ok) {
        const result = await response.json();
        setFinalResults(result.structured_results);
        return result.structured_results;
      } else {
        const error = await response.json();
        throw new Error(error.detail);
      }
    } catch (error) {
      console.error('Error loading final results:', error);
      throw error;
    } finally {
      setIsLoadingFinalResults(false);
    }
  };

  const handleShowFinalResults = async () => {
    try {
      setIsLoadingFinalResults(true);
      
      // First generate final results from current group data
      const response = await fetch(`${API_BASE_URL}/api/final-results/save/${fileId}`, {
        method: 'POST',
      });
      
      if (response.ok) {
        const result = await response.json();
        setFinalResults(result);
        // Show the save modal to get name and description
        setShowSaveGroupModal(true);
      } else {
        const error = await response.json();
        alert(`Error generating final results: ${error.detail}`);
      }
    } catch (error) {
      console.error('Error generating final results:', error);
      alert('Error generating final results');
    } finally {
      setIsLoadingFinalResults(false);
    }
  };

  const handleSaveGroup = () => {
    setShowSaveGroupModal(true);
  };

  const handleBackToDashboard = () => {
    navigate('/');
  };

  const handleReconfigureGroups = () => {
    navigate(`/configure-groups/${fileId}`);
    setTimeout(() => window.scrollTo(0, 0), 100);
  };

  const toggleGroupExpansion = (groupId) => {
    const newExpanded = new Set(expandedGroups);
    if (newExpanded.has(groupId)) {
      newExpanded.delete(groupId);
    } else {
      newExpanded.add(groupId);
    }
    setExpandedGroups(newExpanded);
  };

  if (isLoading || isGeneratingGroups) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md mx-auto p-6">
          <div className="inline-flex items-center px-6 py-3 bg-purple-100 text-purple-800 rounded-lg mb-4">
            <svg className="animate-spin -ml-1 mr-3 h-6 w-6 text-purple-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {isGeneratingGroups ? 'Processing AI Groups...' : 'Loading...'}
          </div>
          {isGeneratingGroups && (
            <div className="text-center">
              <h3 className="text-lg font-medium text-gray-900 mb-2">AI is analyzing your data</h3>
              <p className="text-sm text-gray-600 mb-4">
                Our intelligent grouping system is processing your CSV file to create optimized procurement groups.
              </p>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (!selectedFile) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-xl font-bold text-gray-900 mb-4">File Not Found</h2>
          <p className="text-gray-600 mb-6">The requested file could not be found or hasn't been processed yet.</p>
          <button
            onClick={handleBackToDashboard}
            className="btn-primary"
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
              <h1 className="text-2xl font-bold text-gray-900">Group Management</h1>
              <p className="text-gray-600">Manage procurement groups for {selectedFile.filename}</p>
            </div>
            <div className="flex space-x-3">
              <button
                onClick={handleReconfigureGroups}
                className="bg-purple-600 text-white px-4 py-2 rounded-lg hover:bg-purple-700 transition-colors"
              >
                Reconfigure Groups
              </button>
            <button
              onClick={handleBackToDashboard}
                className="bg-gray-500 text-white px-4 py-2 rounded-lg hover:bg-gray-600 transition-colors"
            >
              Back to Dashboard
            </button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* File Info */}
        <div className="bg-white rounded-lg shadow-sm border mb-6">
          <div className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">{selectedFile.filename}</h2>
                <p className="text-sm text-gray-600">
                  {selectedFile.total_rows} rows • {selectedFile.columns?.length} columns
                </p>
              </div>
              <div className="flex space-x-4">
                <button
                  onClick={handleShowFinalResults}
                  disabled={!groupManagementData || isSavingFinalResults || isLoadingFinalResults}
                  className="btn-success"
                >
                  {isSavingFinalResults || isLoadingFinalResults ? 'Loading...' : 'Save Final Results'}
                </button>
                  </div>
            </div>
          </div>
            </div>
            
        {/* Validation Summary */}
        {validationResults && (
          <div className={`bg-white rounded-lg shadow-sm border mb-6 ${validationResults.is_valid ? 'border-green-200' : 'border-red-200'}`}>
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium">Data Validation</h3>
                <div className={`px-3 py-1 rounded-full text-sm ${validationResults.is_valid ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                  {validationResults.is_valid ? '✅ Valid' : '❌ Issues Found'}
                </div>
              </div>
              
              {/* Debug Info */}
              <div className="bg-yellow-50 border border-yellow-200 rounded p-3 mb-4 text-xs">
                <strong>Debug - Validation Data:</strong><br/>
                {JSON.stringify(validationResults, null, 2)}
              </div>
              
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-gray-900">{validationResults.counts?.total_rows || 0}</div>
                  <div className="text-sm text-gray-600">Total Rows</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">{validationResults.counts?.grouped_records || 0}</div>
                  <div className="text-sm text-gray-600">Grouped Items</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-600">{validationResults.counts?.main_groups || 0}</div>
                  <div className="text-sm text-gray-600">Main Groups</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-purple-600">{validationResults.counts?.total_sub_groups || 0}</div>
                  <div className="text-sm text-gray-600">Sub Groups</div>
                </div>
              </div>
              
              {validationResults.errors && validationResults.errors.length > 0 && (
                <div className="bg-red-50 border border-red-200 rounded p-3 mb-4">
                  <h4 className="font-medium text-red-800 mb-2">Validation Errors:</h4>
                  <ul className="text-sm text-red-700 space-y-1">
                    {validationResults.errors.map((error, index) => (
                      <li key={index}>• {error}</li>
                    ))}
                  </ul>
                </div>
              )}
              
              {validationResults.warnings && validationResults.warnings.length > 0 && (
                <div className="bg-yellow-50 border border-yellow-200 rounded p-3">
                  <h4 className="font-medium text-yellow-800 mb-2">Warnings:</h4>
                  <ul className="text-sm text-yellow-700 space-y-1">
                    {validationResults.warnings.map((warning, index) => (
                      <li key={index}>• {warning}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Group Management Interface */}
          {groupManagementData && (
          <div className="space-y-6">
            
            {/* Debug Info */}
            <div className="bg-blue-50 border border-blue-200 rounded p-3 mb-4 text-xs">
              <strong>Debug - Group Management Data:</strong><br/>
              Keys: {Object.keys(groupManagementData).join(', ')}<br/>
              Groups count: {(groupManagementData.groups || []).length}<br/>
              Ungrouped count: {(groupManagementData.ungrouped_items || []).length}<br/>
              Validation exists: {groupManagementData.validation ? 'Yes' : 'No'}
            </div>

            
            {/* Controls */}
            <div className="bg-white rounded-lg shadow-sm border">
              <div className="p-6">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div className="flex flex-wrap items-center gap-4">
                    <button
                      onClick={() => setShowAddGroupModal(true)}
                      className="btn-primary"
                    >
                      Add Main Group
                    </button>
                    
                    {selectedItems.size > 0 && (
                      <div className="flex items-center space-x-4">
                        <span className="text-sm text-gray-600">
                          {selectedItems.size} items selected
                        </span>
                        <select
                          value={selectedGroupForMove || ''}
                          onChange={(e) => {
                            setSelectedGroupForMove(e.target.value);
                            setSelectedSubGroupForMove(null);
                          }}
                          className="text-sm border rounded px-2 py-1"
                        >
                          <option value="">Select target group...</option>
                          {(groupManagementData.groups || []).map((group) => (
                            <option key={group.id} value={group.id}>
                              {group.name}
                            </option>
                          ))}
                        </select>
                        
                        {selectedGroupForMove && (
                          <select
                            value={selectedSubGroupForMove || ''}
                            onChange={(e) => setSelectedSubGroupForMove(e.target.value)}
                            className="text-sm border rounded px-2 py-1"
                          >
                            <option value="">Select target sub-group...</option>
                            {(() => {
                              const selectedGroup = (groupManagementData.groups || []).find(g => g.id === selectedGroupForMove);
                              return (selectedGroup?.sub_groups || []).map((subGroup) => (
                                <option key={subGroup.id} value={subGroup.id}>
                                  {subGroup.name}
                                </option>
                              ));
                            })()}
                          </select>
                        )}
                        
                        <button
                          onClick={handleMoveSelectedItems}
                          disabled={!selectedGroupForMove}
                          className="btn-primary text-sm"
                        >
                          Move Items
                        </button>
                      </div>
                    )}
                  </div>
                  
                  <div className="text-sm text-gray-600">
                    {(groupManagementData.groups || []).length} groups • {groupManagementData.ungrouped_items?.length || 0} ungrouped items
                  </div>
                </div>
              </div>
            </div>

            {/* Main Groups */}
            <div className="space-y-4">
              {(groupManagementData.groups || []).map((group) => (
                <div key={group.id} className={`bg-white rounded-lg shadow-sm border ${!group.enabled ? 'opacity-60' : ''}`}>
                  <div className="p-4 border-b">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-4">
                        <button
                          onClick={() => toggleGroupExpansion(group.id)}
                          className="text-gray-500 hover:text-gray-700"
                        >
                          {expandedGroups.has(group.id) ? '▼' : '▶'}
                        </button>
                        
                        <div className="flex items-center space-x-2">
                          <input
                            type="checkbox"
                            checked={group.enabled}
                            onChange={() => handleToggleGroup(group.id)}
                            className="rounded"
                          />
                          
                          {editingGroup === group.id ? (
                            <input
                              type="text"
                              defaultValue={group.name}
                              onBlur={(e) => handleUpdateGroupName(group.id, e.target.value)}
                              onKeyPress={(e) => e.key === 'Enter' && handleUpdateGroupName(group.id, e.target.value)}
                              className="font-medium text-lg border rounded px-2 py-1"
                              autoFocus
                            />
                          ) : (
                            <h3
                              className="text-lg font-medium cursor-pointer hover:text-blue-600"
                              onClick={() => setEditingGroup(group.id)}
                            >
                              {group.name}
                            </h3>
                          )}
                        </div>
                        
                        <div className="flex space-x-2">
                                                  <div className="flex items-center space-x-2 mt-2">
                          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            {group.count || group.item_count || 0} records
                          </span>
                          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                            {(group.sub_groups || []).length} sub-groups
                          </span>
                        </div>
                        </div>
                      </div>
                      
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => setShowAddSubGroupModal(group.id)}
                          className="text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 py-1 px-3 rounded"
                        >
                          Add Sub Group
                        </button>
                        <button
                          onClick={() => handleDeleteMainGroup(group.id)}
                          className="text-sm bg-red-100 hover:bg-red-200 text-red-700 py-1 px-3 rounded"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                  
                  {expandedGroups.has(group.id) && (
                    <div className="p-4 space-y-4">
                      {(group.sub_groups || []).map((subGroup) => (
                        <div key={subGroup.id} className={`border rounded-lg p-4 ${subGroup.is_ungrouped_subgroup ? 'bg-yellow-50 border-yellow-200' : 'bg-gray-50'}`}>
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center space-x-2">
                              {editingSubGroup === `${group.id}-${subGroup.id}` ? (
                                <input
                                  type="text"
                                  defaultValue={subGroup.name}
                                  onBlur={(e) => handleUpdateSubGroupName(group.id, subGroup.id, e.target.value)}
                                  onKeyPress={(e) => e.key === 'Enter' && handleUpdateSubGroupName(group.id, subGroup.id, e.target.value)}
                                  className="font-medium border rounded px-2 py-1"
                                  autoFocus
                                />
                              ) : (
                                <h4
                                  className="font-medium cursor-pointer hover:text-blue-600"
                                  onClick={() => setEditingSubGroup(`${group.id}-${subGroup.id}`)}
                                >
                                  {subGroup.name}
                                </h4>
                              )}
                              {subGroup.is_ungrouped_subgroup && (
                                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                                  Ungrouped Items
                                </span>
                              )}
                    </div>
                    
                            <div className="flex items-center space-x-2">
                              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                {subGroup.count || subGroup.items?.length || 0} records
                            </span>
                              {!subGroup.is_ungrouped_subgroup && (
                                <button
                                  onClick={() => handleDeleteSubGroup(group.id, subGroup.id)}
                                  className="text-sm bg-red-100 hover:bg-red-200 text-red-700 py-1 px-2 rounded"
                                >
                                  Delete
                                </button>
                              )}
                            </div>
                          </div>
                          
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                            {(subGroup.items || []).map((item) => (
                              <div 
                                key={item.id} 
                                className="p-2 bg-white rounded border text-sm group hover:bg-gray-50 cursor-pointer"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleItemClick(item, subGroup.items || []);
                                }}
                              >
                                <div className="flex items-start justify-between">
                                  <div className="flex-1 min-w-0">
                                    <div className="font-medium truncate">{item.name}</div>
                                    {item.price && (
                                      <div className="text-gray-600">${item.price}</div>
                                    )}
                                    {item.count && item.count > 1 && (
                                      <div className="text-xs text-blue-600">Qty: {item.count}</div>
                                    )}
                                  </div>
                                  {!subGroup.is_ungrouped_subgroup && (
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleRemoveFromSubGroup(group.id, subGroup.id, item.id);
                                      }}
                                      className="ml-2 opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-700 text-xs p-1"
                                      title="Remove from sub-group"
                                    >
                                      ✕
                                    </button>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                      </div>
                    )}
                  </div>
                ))}
            </div>

            {/* Ungrouped Items */}
            {groupManagementData.ungrouped_items && groupManagementData.ungrouped_items.length > 0 && (
              <div className="bg-white rounded-lg shadow-sm border">
                <div className="p-4 border-b">
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-medium">Ungrouped Items ({groupManagementData.ungrouped_items.length})</h3>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={handleSelectAllUngrouped}
                        className="text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 py-1 px-3 rounded"
                      >
                        Select All
                      </button>
                      <button
                        onClick={() => setSelectedItems(new Set())}
                        className="text-sm bg-gray-100 hover:bg-gray-200 text-gray-700 py-1 px-3 rounded"
                      >
                        Clear Selection
                      </button>
                    </div>
                  </div>
                </div>
                
                <div className="p-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                    {groupManagementData.ungrouped_items.map((item) => (
                      <div
                        key={item.id}
                        className={`p-3 border rounded cursor-pointer hover:bg-gray-50 ${
                          selectedItems.has(item.id) ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                        }`}
                        onClick={(e) => {
                          if (e.target.type === 'checkbox') {
                            return; // Let checkbox handle its own click
                          }
                          
                          if (e.shiftKey || e.ctrlKey || e.metaKey) {
                            // If modifier keys are held, do selection instead of popup
                            handleItemSelection(item.id);
                          } else {
                            // Regular click shows popup
                            handleItemClick(item, groupManagementData.ungrouped_items);
                          }
                        }}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="font-medium text-sm truncate">{item.name}</div>
                            {item.category && item.category !== 'Unknown' && (
                              <div className="text-xs text-gray-600 mt-1">{item.category}</div>
                            )}
                            {item.price && (
                              <div className="text-xs text-green-600 mt-1">${item.price}</div>
                            )}
                            {item.count && item.count > 1 && (
                              <div className="text-xs text-blue-600 mt-1">Qty: {item.count}</div>
                            )}
                          </div>
                          <input
                            type="checkbox"
                            checked={selectedItems.has(item.id)}
                            onChange={(e) => {
                              e.stopPropagation();
                              handleItemSelection(item.id);
                            }}
                            className="ml-2 rounded"
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Add Group Modal */}
      {showAddGroupModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-medium mb-4">Add New Main Group</h3>
            <input
              type="text"
              placeholder="Group name"
              className="w-full border rounded px-3 py-2 mb-4"
              onKeyPress={(e) => {
                if (e.key === 'Enter' && e.target.value.trim()) {
                  handleAddMainGroup(e.target.value.trim());
                }
              }}
              autoFocus
            />
            <div className="flex justify-end space-x-2">
              <button
                onClick={() => setShowAddGroupModal(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={(e) => {
                  const input = e.target.parentElement.parentElement.querySelector('input');
                  if (input.value.trim()) {
                    handleAddMainGroup(input.value.trim());
                  }
                }}
                className="btn-primary"
              >
                Add Group
              </button>
            </div>
              </div>
            </div>
          )}

      {/* Add Sub Group Modal */}
      {showAddSubGroupModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-medium mb-4">Add New Sub Group</h3>
            <input
              type="text"
              placeholder="Sub group name"
              className="w-full border rounded px-3 py-2 mb-4"
              onKeyPress={(e) => {
                if (e.key === 'Enter' && e.target.value.trim()) {
                  handleAddSubGroup(showAddSubGroupModal, e.target.value.trim());
                }
              }}
              autoFocus
            />
            <div className="flex justify-end space-x-2">
              <button
                onClick={() => setShowAddSubGroupModal(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={(e) => {
                  const input = e.target.parentElement.parentElement.querySelector('input');
                  if (input.value.trim()) {
                    handleAddSubGroup(showAddSubGroupModal, input.value.trim());
                  }
                }}
                className="btn-primary"
              >
                Add Sub Group
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Save Final Results Modal */}
      {showSaveGroupModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-medium mb-4">Save Final Results</h3>
            <p className="text-sm text-gray-600 mb-4">
              Save your grouped results to view later in the Saved Groups tab.
            </p>
            <input
              type="text"
              placeholder="Group name (required)"
              value={groupName}
              onChange={(e) => setGroupName(e.target.value)}
              className="w-full border rounded px-3 py-2 mb-4"
            />
            <div className="flex justify-end space-x-2">
              <button
                onClick={() => {
                  setShowSaveGroupModal(false);
                  setGroupName('');
                }}
                className="btn-secondary"
                disabled={isSavingFinalResults}
              >
                Cancel
              </button>
              <button
                onClick={saveGroupWithName}
                className="btn-success"
                disabled={isSavingFinalResults || !groupName.trim()}
              >
                {isSavingFinalResults ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Item Details Popup */}
      <ItemDetailsPopup
        item={selectedItem}
        subGroupItems={selectedSubGroupItems}
        availableColumns={availableColumns}
        selectedColumns={selectedColumns}
        onColumnsChange={updateSelectedColumns}
        onClose={handleCloseItemDetails}
        isOpen={showItemDetails}
      />
    </div>
  );
}

export default GroupManagement; 