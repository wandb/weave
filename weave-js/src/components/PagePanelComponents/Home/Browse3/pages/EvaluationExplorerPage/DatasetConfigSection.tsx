import React, {useCallback} from 'react';

import {useEvaluationExplorerPageContext} from './context';
import {clientBound, hookify} from './hooks';
import {ConfigSection} from './layout';
import {getLatestDatasetRefs} from './query';
import {VersionedObjectPicker} from './VersionedObjectPicker';

/**
 * Dataset configuration section component.
 * Provides a picker for selecting existing datasets or creating new ones.
 */
export const DatasetConfigSection: React.FC<{
  entity: string;
  project: string;
  setNewDatasetEditorMode: (mode: 'new-empty' | 'new-file') => void;
  error?: string;
}> = ({entity, project, setNewDatasetEditorMode, error}) => {
  return (
    <ConfigSection title="Dataset" icon="table">
      <DatasetPicker
        entity={entity}
        project={project}
        setNewDatasetEditorMode={setNewDatasetEditorMode}
      />
    </ConfigSection>
  );
};

// Create the hook for fetching dataset refs
const useLatestDatasetRefs = clientBound(hookify(getLatestDatasetRefs));

/**
 * Dataset picker component that integrates with the VersionedObjectPicker.
 * Supports special "new" options for creating datasets from scratch or uploading files.
 */
const DatasetPicker: React.FC<{
  entity: string;
  project: string;
  setNewDatasetEditorMode: (mode: 'new-empty' | 'new-file') => void;
}> = ({entity, project, setNewDatasetEditorMode}) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();
  const refsQuery = useLatestDatasetRefs(entity, project);

  const setDatasetRef = useCallback(
    (datasetRef: string | null) => {
      // Don't update if the ref hasn't changed
      const currentRef =
        config.evaluationDefinition.properties.dataset.originalSourceRef;
      if (datasetRef === currentRef) {
        return;
      }

      if (datasetRef === 'new-empty' || datasetRef === 'new-file') {
        // Handle special new dataset modes - these trigger the dataset editor
        const mode = datasetRef as 'new-empty' | 'new-file';
        setNewDatasetEditorMode(mode);
        editConfig(draft => {
          if (
            draft.evaluationDefinition.properties.dataset.originalSourceRef !==
            null
          ) {
            draft.evaluationDefinition.properties.dataset.originalSourceRef =
              null;
          }
        });
      } else {
        // Set selected dataset ref for existing datasets
        editConfig(draft => {
          if (
            draft.evaluationDefinition.properties.dataset.originalSourceRef !==
            datasetRef
          ) {
            draft.evaluationDefinition.properties.dataset.originalSourceRef =
              datasetRef;
          }
        });
      }
    },
    [
      editConfig,
      setNewDatasetEditorMode,
      config.evaluationDefinition.properties.dataset.originalSourceRef,
    ]
  );

  const currentRef =
    config.evaluationDefinition.properties.dataset.originalSourceRef;

  // Dataset has two special "new" options for creating datasets
  const datasetNewOptions = [
    {
      label: 'Start from scratch',
      value: 'new-empty',
    },
    {
      label: 'Upload a file',
      value: 'new-file',
    },
  ];

  return (
    <VersionedObjectPicker
      entity={entity}
      project={project}
      objectType="dataset"
      selectedRef={currentRef}
      onRefChange={setDatasetRef}
      latestObjectRefs={refsQuery.data ?? []}
      loading={refsQuery.loading}
      newOptions={datasetNewOptions}
      allowNewOption={true}
    />
  );
};
