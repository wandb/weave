import React, {useCallback} from 'react';

import {useEvaluationExplorerPageContext} from './context';
import {clientBound, hookify} from './hooks';
import {ConfigSection} from './layout';
import {getLatestDatasetRefs} from './query';
import {VersionedObjectPicker} from './VersionedObjectPicker';

export const DatasetConfigSection: React.FC<{
  entity: string;
  project: string;
  setNewDatasetEditorMode: (mode: 'new-empty' | 'new-file') => void;
  error?: string;
}> = ({entity, project, setNewDatasetEditorMode, error}) => {
  return (
    <ConfigSection title="Dataset" icon="table" error={error}>
      <DatasetPicker
        entity={entity}
        project={project}
        setNewDatasetEditorMode={setNewDatasetEditorMode}
      />
    </ConfigSection>
  );
};

const useLatestDatasetRefs = clientBound(hookify(getLatestDatasetRefs));
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
        // Handle special new dataset modes
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
        // Set selected dataset ref
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

  // Dataset has two special "new" options
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
