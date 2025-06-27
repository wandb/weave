import {Select} from '@wandb/weave/components/Form/Select';
import {parseWeaveRef} from '@wandb/weave/react';
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';

import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {LoadingSelect} from './components';
import {getAllVersionsOfObject} from './query';

// Type definitions for Select component options
type SelectOption = {
  label: string;
  value: string;
};

type GroupedSelectOption = {
  label: string;
  options: SelectOption[];
};

export interface VersionedObjectPickerProps {
  entity: string;
  project: string;
  objectType: 'evaluation' | 'dataset' | 'scorer' | 'model';
  selectedRef: string | null;
  onRefChange: (ref: string | null) => void;
  latestObjectRefs: string[];
  loading?: boolean;
  newOptions?: SelectOption[];
  allowNewOption?: boolean;
}

/**
 * A unified picker component that handles two-level selection:
 * 1. Object selection (e.g., "my-dataset")
 * 2. Version selection (e.g., "v1", "v2", "v3")
 *
 * Supports creating new objects and selecting specific versions of existing objects.
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
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [objectVersions, setObjectVersions] = useState<string[]>([]);
  const [pendingObjectId, setPendingObjectId] = useState<string | null>(null);
  const hasSetDefaultRef = useRef(false);

  // Default new options if not provided
  const effectiveNewOptions = useMemo(() => {
    if (newOptions && newOptions.length > 0) {
      return newOptions;
    }
    // Default single new option
    return [
      {
        label: `New ${
          objectType.charAt(0).toUpperCase() + objectType.slice(1)
        }`,
        value: `new-${objectType}`,
      },
    ];
  }, [newOptions, objectType]);

  // Auto-select the default option when mounting with null ref
  useEffect(() => {
    if (
      !hasSetDefaultRef.current &&
      selectedRef === null &&
      allowNewOption &&
      effectiveNewOptions.length > 0
    ) {
      // Propagate the default selection to parent
      hasSetDefaultRef.current = true;
      onRefChange(effectiveNewOptions[0].value);
    } else if (selectedRef !== null) {
      // Reset the flag when user makes an explicit selection
      hasSetDefaultRef.current = true;
    }
  }, [selectedRef, allowNewOption, effectiveNewOptions, onRefChange]);

  // Check if current value is a "new" option
  const isNewOption = useMemo(() => {
    return effectiveNewOptions.some(opt => opt.value === selectedRef);
  }, [effectiveNewOptions, selectedRef]);

  // When there's no selection, we want to show the first new option as placeholder
  // but NOT actually select it (which would put us in new option mode)
  const displayValue = useMemo(() => {
    if (
      selectedRef === null &&
      allowNewOption &&
      effectiveNewOptions.length > 0
    ) {
      // Return the first new option for display only
      return effectiveNewOptions[0];
    }
    // For actual selections, find the matching option
    if (selectedRef && isNewOption) {
      return effectiveNewOptions.find(opt => opt.value === selectedRef);
    }
    return null;
  }, [selectedRef, allowNewOption, effectiveNewOptions, isNewOption]);

  // Extract object ID from the selected ref
  const selectedObjectId = useMemo(() => {
    // If we have a pending selection, use that
    if (pendingObjectId) {
      return pendingObjectId;
    }
    // Otherwise extract from ref - use actual selectedRef, not display value
    if (selectedRef && !isNewOption) {
      const parsedRef = parseWeaveRef(selectedRef);
      return parsedRef.artifactName;
    }
    return null;
  }, [selectedRef, isNewOption, pendingObjectId]);

  // Load versions when object is selected
  useEffect(() => {
    if (selectedObjectId && !isNewOption) {
      setVersionsLoading(true);
      const client = getClient();
      getAllVersionsOfObject(client, entity, project, selectedObjectId)
        .then(versions => {
          setObjectVersions(versions);
          setVersionsLoading(false);

          // Auto-select latest if this was a pending selection
          if (versions.length > 0 && pendingObjectId) {
            const needsAutoSelect =
              !selectedRef ||
              (selectedRef &&
                parseWeaveRef(selectedRef).artifactName !== pendingObjectId);

            if (needsAutoSelect) {
              onRefChange(versions[0]);
              setPendingObjectId(null);
            }
          }
        })
        .catch(error => {
          console.error('Failed to load versions:', error);
          setVersionsLoading(false);
        });
    } else {
      setObjectVersions([]);
    }
  }, [
    selectedObjectId,
    entity,
    project,
    getClient,
    isNewOption,
    selectedRef,
    pendingObjectId,
    onRefChange,
  ]);

  // Clear pending when ref changes externally
  useEffect(() => {
    if (selectedRef && pendingObjectId) {
      // Only clear if we have a ref and it matches what we were pending
      const parsedRef = parseWeaveRef(selectedRef);
      if (parsedRef.artifactName === pendingObjectId) {
        setPendingObjectId(null);
      }
    }
  }, [selectedRef, pendingObjectId]);

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
  const objectOptions = useMemo((): (SelectOption | GroupedSelectOption)[] => {
    const options: (SelectOption | GroupedSelectOption)[] = [];

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
      const versionLabel =
        index === 0 ? 'latest' : `v${objectVersions.length - index}`;

      return {
        label: `${versionLabel} (${parsedRef.artifactVersion.slice(0, 6)})`,
        value: ref,
      };
    });
  }, [objectVersions, selectedObjectId, isNewOption]);

  // Handle object selection
  const handleObjectChange = useCallback(
    (option: SelectOption | null) => {
      const value = option?.value;

      if (!value) {
        onRefChange(null);
        setPendingObjectId(null);
        return;
      }

      // Check if it's a new option
      if (effectiveNewOptions.some(opt => opt.value === value)) {
        onRefChange(value);
        setPendingObjectId(null);
        return;
      }

      // User is selecting a new object - we should auto-select latest
      setPendingObjectId(value);
    },
    [onRefChange, effectiveNewOptions]
  );

  // Handle version selection
  const handleVersionChange = useCallback(
    (option: SelectOption | null) => {
      const ref = option?.value;
      onRefChange(ref || null);
    },
    [onRefChange]
  );

  // If we're in new object mode, just show a single select
  if (isNewOption) {
    const selectedNewOption = effectiveNewOptions.find(
      opt => opt.value === selectedRef
    );
    return (
      <Select
        value={selectedNewOption}
        options={objectOptions}
        onChange={handleObjectChange}
        isDisabled={loading}
      />
    );
  }

  // Determine selected values for the two-dropdown mode
  let selectedObjectOption: SelectOption | null = null;

  if (pendingObjectId) {
    // When we have a pending object selection, show that
    selectedObjectOption = {
      label: pendingObjectId,
      value: pendingObjectId,
    };
  } else if (selectedRef === null && displayValue) {
    // When nothing is selected, use the display value (e.g., "Start from scratch")
    selectedObjectOption = displayValue;
  } else if (isNewOption && selectedRef) {
    // If a new option is actually selected, find it
    selectedObjectOption =
      effectiveNewOptions.find(opt => opt.value === selectedRef) || null;
  } else if (selectedObjectId) {
    // Otherwise use the object ID
    selectedObjectOption = {
      label: selectedObjectId,
      value: selectedObjectId,
    };
  }

  const selectedVersionOption =
    selectedRef && selectedObjectId && !isNewOption
      ? versionOptions.find(opt => opt.value === selectedRef) || null
      : null;

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

      {(selectedObjectId || pendingObjectId) && !isNewOption && (
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
