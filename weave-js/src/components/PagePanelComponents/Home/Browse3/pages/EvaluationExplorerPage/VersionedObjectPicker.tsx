import {Select} from '@wandb/weave/components/Form/Select';
import React, {useCallback, useEffect, useMemo, useState} from 'react';

import {parseWeaveRef} from '@wandb/weave/react';
import {refStringToName} from './common';
import {LoadingSelect} from './components';
import {clientBound, hookify} from './hooks';
import {getAllVersionsOfObject} from './query';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';

const useObjectVersions = clientBound(hookify(getAllVersionsOfObject));

export interface VersionedObjectPickerProps {
  entity: string;
  project: string;
  objectType: 'evaluation' | 'dataset' | 'scorer' | 'model';
  selectedRef: string | null;
  onRefChange: (ref: string | null) => void;
  latestObjectRefs: string[];
  loading?: boolean;
  newOptions?: Array<{label: string; value: string}>;
  allowNewOption?: boolean;
}

/**
 * A unified picker component that handles two-level selection:
 * 1. Object selection (e.g., "my-dataset")
 * 2. Version selection (e.g., "v1", "v2", "v3")
 * 
 * This bad boy replaces all our individual pickers with a single, powerful interface!
 */
export const VersionedObjectPicker: React.FC<VersionedObjectPickerProps> = ({
  entity,
  project,
  objectType,
  selectedRef,
  onRefChange,
  latestObjectRefs,
  loading = false,
  newOptions,
  allowNewOption = true,
}) => {
  const getClient = useGetTraceServerClientContext();
  const [selectedObjectId, setSelectedObjectId] = useState<string | null>(null);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [objectVersions, setObjectVersions] = useState<string[]>([]);
  const [shouldAutoSelectLatest, setShouldAutoSelectLatest] = useState(false);

  // Default new options if not provided
  const effectiveNewOptions = useMemo(() => {
    if (newOptions && newOptions.length > 0) {
      return newOptions;
    }
    // Default single new option
    return [{
      label: `New ${objectType.charAt(0).toUpperCase() + objectType.slice(1)}`,
      value: `new-${objectType}`,
    }];
  }, [newOptions, objectType]);

  // Check if current value is a "new" option
  const isNewOption = useMemo(() => {
    return effectiveNewOptions.some(opt => opt.value === selectedRef);
  }, [effectiveNewOptions, selectedRef]);

  // Extract object ID from the selected ref
  useEffect(() => {
    if (selectedRef && !isNewOption) {
      const parsedRef = parseWeaveRef(selectedRef);
      const newObjectId = parsedRef.artifactName;
      
      // Only update if the object ID actually changed
      if (newObjectId !== selectedObjectId) {
        setSelectedObjectId(newObjectId);
        // Don't auto-select when loading an existing ref
        setShouldAutoSelectLatest(false);
      }
    } else if (!selectedRef) {
      setSelectedObjectId(null);
      setObjectVersions([]);
      setShouldAutoSelectLatest(false);
    }
  }, [selectedRef, isNewOption, selectedObjectId]);

  // Load versions when object is selected
  useEffect(() => {
    if (selectedObjectId && !isNewOption) {
      console.log(`[VersionedObjectPicker ${objectType}] Loading versions for`, selectedObjectId);
      setVersionsLoading(true);
      const client = getClient();
      getAllVersionsOfObject(client, entity, project, selectedObjectId)
        .then(versions => {
          console.log(`[VersionedObjectPicker ${objectType}] Loaded ${versions.length} versions`);
          setObjectVersions(versions);
          setVersionsLoading(false);
          
          // Only auto-select if we explicitly want to (user just selected an object)
          if (versions.length > 0 && shouldAutoSelectLatest) {
            console.log(`[VersionedObjectPicker ${objectType}] Auto-selecting latest version`);
            onRefChange(versions[0]);
            setShouldAutoSelectLatest(false);
          } else if (selectedRef && versions.length > 0) {
            // Check if the current ref is in the versions list
            const refInVersions = versions.includes(selectedRef);
            console.log(`[VersionedObjectPicker ${objectType}] Current ref ${selectedRef} is ${refInVersions ? 'in' : 'NOT in'} versions list`);
          }
        })
        .catch(error => {
          console.error('Failed to load versions:', error);
          setVersionsLoading(false);
        });
    }
  }, [selectedObjectId, entity, project, getClient, isNewOption, onRefChange, shouldAutoSelectLatest, selectedRef, objectType]);

  // Group objects by their ID (name)
  const objectGroups = useMemo(() => {
    const groups: Record<string, string[]> = {};
    
    latestObjectRefs.forEach(ref => {
      const parsedRef = parseWeaveRef(ref);
      const objectId = parsedRef.artifactName;
      
      if (!groups[objectId]) {
        groups[objectId] = [];
      }
      groups[objectId].push(ref);
    });
    
    return groups;
  }, [latestObjectRefs]);

  // First level options: object names
  const objectOptions = useMemo(() => {
    const options: any[] = [];
    
    if (allowNewOption) {
      options.push({
        label: 'Create new',
        options: effectiveNewOptions,
      });
    }
    
    const existingOptions = Object.keys(objectGroups).map(objectId => ({
      label: objectId,
      value: objectId,
    }));
    
    if (existingOptions.length > 0) {
      options.push({
        label: `Existing ${objectType}s`,
        options: existingOptions,
      });
    }
    
    return options;
  }, [objectGroups, allowNewOption, effectiveNewOptions, objectType]);

  // Second level options: versions
  const versionOptions = useMemo(() => {
    if (!selectedObjectId || isNewOption) {
      return [];
    }
    
    return objectVersions.map((ref, index) => {
      const parsedRef = parseWeaveRef(ref);
      const versionLabel = index === 0 ? 'latest' : `v${objectVersions.length - index}`;
      
      return {
        label: `${versionLabel} (${parsedRef.artifactVersion.slice(0, 6)})`,
        value: ref,
      };
    });
  }, [objectVersions, selectedObjectId, isNewOption]);

  // Handle object selection
  const handleObjectChange = useCallback((option: any) => {
    const value = option?.value;
    console.log(`[VersionedObjectPicker ${objectType}] handleObjectChange:`, value);
    
    if (!value) {
      onRefChange(null);
      setShouldAutoSelectLatest(false);
      return;
    }
    
    // Check if it's a new option
    if (effectiveNewOptions.some(opt => opt.value === value)) {
      onRefChange(value);
      setSelectedObjectId(null);
      setObjectVersions([]);
      setShouldAutoSelectLatest(false);
      return;
    }
    
    // User is selecting a new object - we should auto-select latest
    setSelectedObjectId(value);
    setShouldAutoSelectLatest(true);
  }, [onRefChange, effectiveNewOptions, objectType]);

  // Handle version selection
  const handleVersionChange = useCallback((option: any) => {
    const ref = option?.value;
    console.log(`[VersionedObjectPicker ${objectType}] handleVersionChange:`, ref);
    onRefChange(ref || null);
  }, [onRefChange, objectType]);

  // If we're in new object mode, just show a single select
  if (isNewOption) {
    const selectedNewOption = effectiveNewOptions.find(opt => opt.value === selectedRef);
    return (
      <Select
        value={selectedNewOption}
        options={objectOptions}
        onChange={handleObjectChange}
        isDisabled={loading}
      />
    );
  }

  // Determine selected values
  const selectedObjectOption = selectedObjectId ? {
    label: selectedObjectId,
    value: selectedObjectId,
  } : null;

  const selectedVersionOption = selectedRef && selectedObjectId && !isNewOption ? 
    versionOptions.find(opt => opt.value === selectedRef) : null;

  if (loading) {
    return <LoadingSelect />;
  }

  return (
    <div style={{display: 'flex', gap: '8px', alignItems: 'center'}}>
      <div style={{flex: '1 1 60%'}}>
        <Select
          placeholder={`Select ${objectType}`}
          value={selectedObjectOption}
          options={objectOptions}
          onChange={handleObjectChange}
        />
      </div>
      
      {selectedObjectId && !isNewOption && (
        <>
          <span style={{color: '#666', flex: '0 0 auto'}}>→</span>
          <div style={{flex: '0 0 40%'}}>
            {versionsLoading ? (
              <LoadingSelect />
            ) : (
              <Select
                placeholder="Select version"
                value={selectedVersionOption}
                options={versionOptions}
                onChange={handleVersionChange}
              />
            )}
          </div>
        </>
      )}
    </div>
  );
}; 