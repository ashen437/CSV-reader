import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ChevronDown, ChevronRight, Save, ArrowLeft, FileText, Folder } from 'lucide-react';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

function EditGroups() {
  const { groupId } = useParams();
  const navigate = useNavigate();
  
  const [originalGroup, setOriginalGroup] = useState(null);
  const [editedGroup, setEditedGroup] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [newGroupName, setNewGroupName] = useState('');
  
  // Sidebar state
  const [sidebarType, setSidebarType] = useState(null); // 'subgroup' or 'item'
  const [selectedItem, setSelectedItem] = useState(null);
  const [selectedMainGroupForMove, setSelectedMainGroupForMove] = useState(null); // For item moving - step 1
  const [collapsedMainGroups, setCollapsedMainGroups] = useState({});
  const [collapsedSidebarGroups, setCollapsedSidebarGroups] = useState({});

  useEffect(() => {
    if (groupId) {
      fetchGroupData();
    }
  }, [groupId]);

  const fetchGroupData = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/saved-groups`);
      if (response.ok) {
        const data = await response.json();
        const group = data.saved_groups?.find(g => g._id === groupId);
        if (group) {
          setOriginalGroup(group);
          // Create a deep copy for editing
          setEditedGroup(JSON.parse(JSON.stringify(group)));
          setNewGroupName(`${group.name} (Edited)`);
        } else {
          setError('Group not found');
        }
      } else {
        setError('Failed to fetch group data');
      }
    } catch (error) {
      console.error('Error fetching group data:', error);
      setError('Error fetching group data');
    } finally {
      setIsLoading(false);
    }
  };

  // Handle sub-group selection
  const handleSubGroupClick = (subGroup, mainGroupIndex, subGroupIndex) => {
    setSidebarType('subgroup');
    setSelectedItem({
      type: 'subgroup',
      data: subGroup,
      mainGroupIndex,
      subGroupIndex,
      currentMainGroup: editedGroup.structured_results.main_groups[mainGroupIndex].name
    });
  };

  // Handle item selection
  const handleItemClick = (item, mainGroupIndex, subGroupIndex, itemIndex) => {
    setSidebarType('item');
    setSelectedMainGroupForMove(null); // Reset main group selection
    setSelectedItem({
      type: 'item',
      data: item,
      mainGroupIndex,
      subGroupIndex,
      itemIndex,
      currentMainGroup: editedGroup.structured_results.main_groups[mainGroupIndex].name,
      currentSubGroup: editedGroup.structured_results.main_groups[mainGroupIndex].sub_groups[subGroupIndex].name
    });
  };

  // Move sub-group to different main group
  const moveSubGroupToMainGroup = (targetMainGroupIndex) => {
    if (!selectedItem || selectedItem.type !== 'subgroup') return;

    const newEditedGroup = JSON.parse(JSON.stringify(editedGroup));
    const { mainGroupIndex, subGroupIndex, data: subGroup } = selectedItem;

    // Remove from source
    newEditedGroup.structured_results.main_groups[mainGroupIndex].sub_groups.splice(subGroupIndex, 1);
    
    // Add to target
    newEditedGroup.structured_results.main_groups[targetMainGroupIndex].sub_groups.push(subGroup);
    
    // Update counts
    updateItemCounts(newEditedGroup);
    setEditedGroup(newEditedGroup);
    setSidebarType(null);
    setSelectedItem(null);
  };

  // Move item to different sub-group
  const moveItemToSubGroup = (targetMainGroupIndex, targetSubGroupIndex) => {
    if (!selectedItem || selectedItem.type !== 'item') return;

    const newEditedGroup = JSON.parse(JSON.stringify(editedGroup));
    const { mainGroupIndex, subGroupIndex, itemIndex, data: item } = selectedItem;

    // Remove from source
    newEditedGroup.structured_results.main_groups[mainGroupIndex]
      .sub_groups[subGroupIndex].items.splice(itemIndex, 1);
    
    // Add to target
    if (!newEditedGroup.structured_results.main_groups[targetMainGroupIndex]
        .sub_groups[targetSubGroupIndex].items) {
      newEditedGroup.structured_results.main_groups[targetMainGroupIndex]
        .sub_groups[targetSubGroupIndex].items = [];
    }
    newEditedGroup.structured_results.main_groups[targetMainGroupIndex]
      .sub_groups[targetSubGroupIndex].items.push(item);
    
    // Update counts
    updateItemCounts(newEditedGroup);
    setEditedGroup(newEditedGroup);
    setSidebarType(null);
    setSelectedItem(null);
  };

  const toggleMainGroupCollapse = (index) => {
    setCollapsedMainGroups(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const toggleSidebarGroupCollapse = (index) => {
    setCollapsedSidebarGroups(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const updateItemCounts = (group) => {
    group.structured_results.main_groups.forEach(mainGroup => {
      let mainGroupTotal = 0;
      mainGroup.sub_groups.forEach(subGroup => {
        subGroup.total_items = subGroup.items?.length || 0;
        mainGroupTotal += subGroup.total_items;
      });
      mainGroup.total_items = mainGroupTotal;
    });
    
    group.structured_results.total_items = group.structured_results.main_groups
      .reduce((total, mg) => total + mg.total_items, 0);
    group.structured_results.total_groups = group.structured_results.main_groups.length;
    group.structured_results.total_sub_groups = group.structured_results.main_groups
      .reduce((total, mg) => total + mg.sub_groups.length, 0);
  };

  const handleSaveAsNew = async () => {
    if (!newGroupName.trim()) {
      alert('Please enter a name for the new group');
      return;
    }

    setIsSaving(true);
    try {
      const saveData = {
        name: newGroupName.trim(),
        description: `Edited version of ${originalGroup.name}`,
        structured_results: editedGroup.structured_results,
        file_id: editedGroup.file_id || editedGroup.file_name || 'unknown',
        created_at: new Date().toISOString()
      };

      const response = await fetch(`${API_BASE_URL}/api/saved-groups`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(saveData),
      });

      if (response.ok) {
        alert('Group saved successfully!');
        navigate('/groups');
      } else {
        const errorData = await response.json();
        alert(`Error saving group: ${errorData.detail}`);
      }
    } catch (error) {
      console.error('Error saving group:', error);
      alert('Error saving group');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 pt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex items-center justify-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            <span className="ml-4 text-gray-600">Loading group data...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 pt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center">
            <div className="text-red-600 mb-4">{error}</div>
            <button
              onClick={() => navigate('/groups')}
              className="btn-primary"
            >
              Back to Groups
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Render sidebar for sub-group configuration
  const renderSubGroupConfiguration = () => {
    if (!selectedItem || selectedItem.type !== 'subgroup') return null;

    const sortedMainGroups = [...editedGroup.structured_results.main_groups]
      .sort((a, b) => a.name.localeCompare(b.name));

    return (
      <div className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Sub Group Configuration</h3>
          <button
            onClick={() => {
              setSidebarType(null);
              setSelectedItem(null);
            }}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Clear Selection
          </button>
        </div>
        
        <div className="mb-4 p-3 bg-blue-50 rounded-lg">
          <p className="text-sm text-gray-700">
            <strong>Selected:</strong> {selectedItem.data.name}
          </p>
          <p className="text-sm text-gray-600">
            Currently in: {selectedItem.currentMainGroup}
          </p>
        </div>

        <h4 className="text-md font-medium text-gray-800 mb-3">Move to Main Group:</h4>
        
        <div className="space-y-2">
          {sortedMainGroups.map((mainGroup, index) => (
            <div key={index} className="border rounded-lg">
              <div className="flex items-center justify-between p-3 hover:bg-gray-50">
                <div className="flex items-center flex-1 min-w-0">
                  <input
                    type="radio"
                    name="mainGroup"
                    checked={mainGroup.name === selectedItem.currentMainGroup}
                    onChange={() => {}}
                    className="mr-3 flex-shrink-0"
                  />
                  <Folder className="w-4 h-4 mr-2 text-blue-600 flex-shrink-0" />
                  <span className="font-medium truncate">{mainGroup.name}</span>
                  <span className="text-sm text-gray-500 ml-2 flex-shrink-0">({mainGroup.total_items} items)</span>
                </div>
                {mainGroup.name !== selectedItem.currentMainGroup && (
                  <button
                    onClick={() => moveSubGroupToMainGroup(editedGroup.structured_results.main_groups.findIndex(mg => mg.name === mainGroup.name))}
                    className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 w-24 flex-shrink-0 ml-3"
                  >
                    Move Here
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  // Render sidebar for item configuration
  const renderItemConfiguration = () => {
    if (!selectedItem || selectedItem.type !== 'item') return null;

    const sortedMainGroups = [...editedGroup.structured_results.main_groups]
      .sort((a, b) => a.name.localeCompare(b.name));

    return (
      <div className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Sub Item Configuration</h3>
          <button
            onClick={() => {
              setSidebarType(null);
              setSelectedItem(null);
              setSelectedMainGroupForMove(null);
            }}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            Clear Selection
          </button>
        </div>
        
        <div className="mb-4 p-3 bg-green-50 rounded-lg">
          <p className="text-sm text-gray-700">
            <strong>Selected:</strong> {selectedItem.data.name}
          </p>
          <p className="text-sm text-gray-600">
            Main Group: {selectedItem.currentMainGroup}
          </p>
          <p className="text-sm text-gray-600">
            Sub Group: {selectedItem.currentSubGroup}
          </p>
        </div>

        {!selectedMainGroupForMove ? (
          // Step 1: Choose Main Group
          <>
            <h4 className="text-md font-medium text-gray-800 mb-3">Step 1: Choose Main Group:</h4>
            <div className="space-y-2">
              {sortedMainGroups.map((mainGroup, mainIndex) => (
                <div key={mainIndex} className="border rounded-lg">
                  <div className="flex items-center justify-between p-3 hover:bg-gray-50 cursor-pointer"
                       onClick={() => setSelectedMainGroupForMove({ group: mainGroup, index: mainIndex })}>
                    <div className="flex items-center flex-1 min-w-0">
                      <input
                        type="radio"
                        name="targetMainGroup"
                        checked={mainGroup.name === selectedItem.currentMainGroup}
                        onChange={() => {}}
                        className="mr-3 flex-shrink-0"
                      />
                      <Folder className="w-4 h-4 mr-2 text-blue-600 flex-shrink-0" />
                      <span className="font-medium truncate">{mainGroup.name}</span>
                      <span className="text-sm text-gray-500 ml-2 flex-shrink-0">({mainGroup.total_items} items)</span>
                    </div>
                    <span className="text-xs text-blue-600 flex-shrink-0 ml-3">Click to select</span>
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : (
          // Step 2: Choose Sub Group within selected Main Group
          <>
            <div className="mb-4">
              <button
                onClick={() => setSelectedMainGroupForMove(null)}
                className="text-sm text-blue-600 hover:text-blue-800 mb-2"
              >
                ← Back to Main Groups
              </button>
              <h4 className="text-md font-medium text-gray-800 mb-3">
                Step 2: Choose Sub Group in "{selectedMainGroupForMove.group.name}":
              </h4>
            </div>
            
            <div className="space-y-2">
              {selectedMainGroupForMove.group.sub_groups
                .sort((a, b) => a.name.localeCompare(b.name))
                .map((subGroup, subIndex) => {
                  const actualSubIndex = selectedMainGroupForMove.group.sub_groups.findIndex(sg => sg.name === subGroup.name);
                  const isCurrentLocation = selectedMainGroupForMove.group.name === selectedItem.currentMainGroup && 
                                          subGroup.name === selectedItem.currentSubGroup;
                  
                  return (
                    <div key={subIndex} className="border rounded-lg">
                      <div className="flex items-center justify-between p-3 hover:bg-gray-50">
                        <div className="flex items-center flex-1 min-w-0">
                          <input
                            type="radio"
                            name="targetSubGroup"
                            checked={isCurrentLocation}
                            onChange={() => {}}
                            className="mr-3 flex-shrink-0"
                          />
                          <Folder className="w-4 h-4 mr-2 text-green-600 flex-shrink-0" />
                          <span className="font-medium truncate">{subGroup.name}</span>
                          <span className="text-sm text-gray-500 ml-2 flex-shrink-0">({subGroup.total_items} items)</span>
                        </div>
                        {!isCurrentLocation && (
                          <button
                            onClick={() => moveItemToSubGroup(selectedMainGroupForMove.index, actualSubIndex)}
                            className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 w-24 flex-shrink-0 ml-3"
                          >
                            Move Here
                          </button>
                        )}
                        {isCurrentLocation && (
                          <span className="text-xs text-gray-500 flex-shrink-0 ml-3">Current location</span>
                        )}
                      </div>
                    </div>
                  );
                })}
            </div>
          </>
        )}
      </div>
    );
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 pt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex items-center justify-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            <span className="ml-4 text-gray-600">Loading group data...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 pt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center">
            <div className="text-red-600 mb-4">{error}</div>
            <button
              onClick={() => navigate('/groups')}
              className="btn-primary"
            >
              Back to Groups
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pt-16">
      <div className="flex">
        {/* Sidebar - Always displayed and wider */}
        <div className="w-[480px] bg-white border-r border-gray-200 flex flex-col">
          {/* Save Section - Always at top */}
          <div className="p-6 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Save Edited Group</h3>
            <div className="space-y-4">
              <div>
                <label htmlFor="sidebarGroupName" className="block text-sm font-medium text-gray-700 mb-2">
                  New Group Name
                </label>
                <input
                  type="text"
                  id="sidebarGroupName"
                  value={newGroupName}
                  onChange={(e) => setNewGroupName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Enter a name for the edited group"
                />
              </div>
              <button
                onClick={handleSaveAsNew}
                disabled={isSaving || !newGroupName.trim()}
                className="w-full inline-flex items-center justify-center btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Save className="w-4 h-4 mr-2" />
                {isSaving ? 'Saving...' : 'Save as New Group'}
              </button>
            </div>
          </div>

          {/* Configuration Section */}
          <div className="flex-1 overflow-y-auto">
            {sidebarType === 'subgroup' && renderSubGroupConfiguration()}
            {sidebarType === 'item' && renderItemConfiguration()}
            
            {!sidebarType && (
              <div className="p-6 text-center">
                <div className="text-gray-500 mb-4">
                  <Folder className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                  <h4 className="text-lg font-medium text-gray-700 mb-2">Configuration Panel</h4>
                  <p className="text-sm text-gray-600">
                    Click on a sub-group or item in the main area to configure its location.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 px-4 sm:px-6 lg:px-8 py-8">
          {/* Header */}
          <div className="mb-6">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Edit Group</h1>
                <p className="text-gray-600 mt-1">
                  Editing: {originalGroup?.name}
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

          {/* Instructions */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
            <h3 className="text-sm font-medium text-blue-900 mb-2">How to Edit:</h3>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>• Click on sub-groups to configure which main group they belong to</li>
              <li>• Click on items to move them between sub-groups</li>
              <li>• Use the sidebar to select new locations and save your changes</li>
              <li>• Changes don't affect the original list</li>
              <li>• Save as a new list when you're done editing</li>
            </ul>
          </div>

          {/* Group Structure */}
          {editedGroup && (
            <div className="bg-white rounded-lg shadow-sm border overflow-hidden">
              <div className="p-6">
                <h3 className="text-lg font-medium text-gray-900 mb-4">
                  Group Structure
                </h3>
                
                <div className="space-y-4">
                  {editedGroup.structured_results?.main_groups?.map((mainGroup, mainIndex) => (
                    <div key={mainIndex} className="border rounded-lg">
                      <div className="flex items-center justify-between p-4 bg-gray-50">
                        <div className="flex items-center">
                          <button
                            onClick={() => toggleMainGroupCollapse(mainIndex)}
                            className="mr-3 p-1 hover:bg-gray-200 rounded"
                          >
                            {collapsedMainGroups[mainIndex] ? 
                              <ChevronRight className="w-5 h-5" /> : 
                              <ChevronDown className="w-5 h-5" />
                            }
                          </button>
                          <Folder className="w-5 h-5 mr-3 text-blue-600" />
                          <h4 className="text-lg font-semibold text-gray-900">
                            {mainGroup.name}
                          </h4>
                          <span className="text-sm text-gray-600 ml-2">
                            ({mainGroup.total_items} items)
                          </span>
                        </div>
                      </div>
                      
                      {!collapsedMainGroups[mainIndex] && (
                        <div className="p-4 space-y-3">
                          {mainGroup.sub_groups?.map((subGroup, subIndex) => (
                            <div key={subIndex} className="bg-gray-50 rounded-lg border">
                              <div 
                                className="p-3 cursor-pointer hover:bg-gray-100 transition-colors"
                                onClick={() => handleSubGroupClick(subGroup, mainIndex, subIndex)}
                              >
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center">
                                    <Folder className="w-4 h-4 mr-2 text-green-600" />
                                    <h5 className="text-md font-medium text-gray-800">
                                      {subGroup.name}
                                    </h5>
                                    <span className="text-sm text-gray-600 ml-2">
                                      ({subGroup.total_items} items)
                                    </span>
                                  </div>
                                  <span className="text-xs text-blue-600">Click to configure</span>
                                </div>
                              </div>
                              
                              <div className="px-6 pb-3 space-y-2">
                                {subGroup.items?.map((item, itemIndex) => (
                                  <div
                                    key={itemIndex}
                                    className="flex justify-between items-center py-2 px-3 bg-white rounded border cursor-pointer hover:bg-blue-50 transition-colors"
                                    onClick={() => handleItemClick(item, mainIndex, subIndex, itemIndex)}
                                  >
                                    <div className="flex items-center">
                                      <FileText className="w-3 h-3 mr-2 text-gray-500" />
                                      <span className="text-gray-700">{item.name}</span>
                                    </div>
                                    <div className="flex items-center">
                                      <span className="text-sm font-medium text-blue-600 mr-2">({item.count})</span>
                                      <span className="text-xs text-blue-600">Click to move</span>
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
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default EditGroups;
