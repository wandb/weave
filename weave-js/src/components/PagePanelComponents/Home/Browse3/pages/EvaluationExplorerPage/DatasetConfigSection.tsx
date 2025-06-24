import {Select} from '@wandb/weave/components/Form/Select';
import React, {useCallback, useMemo, useState} from 'react';

import {refStringToName} from './common';
import {LoadingSelect} from './components';
import {useEvaluationExplorerPageContext} from './context';
import {clientBound, hookify} from './hooks';
import {ConfigSection} from './layout';
import {getLatestDatasetRefs} from './query';

export const DatasetConfigSection: React.FC<{
  entity: string;
  project: string;
  setNewDatasetEditorMode: (mode: 'new-empty' | 'new-file') => void;
}> = ({entity, project, setNewDatasetEditorMode}) => {
  return (
    <ConfigSection
      title="Dataset"
      icon="table"
      style={{
        paddingTop: '0px',
        paddingRight: '0px',
      }}>
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
  const [newDatasetEditorMode, setNewDatasetEditorModeInternal] = useState<
    'new-empty' | 'new-file'
  >('new-empty');

  const newDatasetOptions = useMemo(() => {
    return [
      {
        label: 'Start from scratch',
        value: 'new-empty',
      },
      {
        label: 'Upload a file',
        value: 'new-file',
      },
    ];
  }, []);

  const selectOptions = useMemo(() => {
    return [
      {
        label: 'Create new dataset',
        options: newDatasetOptions,
      },
      {
        label: 'Load existing dataset',
        options:
          refsQuery.data?.map(ref => ({
            label: refStringToName(ref),
            value: ref,
          })) ?? [],
      },
    ];
  }, [refsQuery.data, newDatasetOptions]);

  const selectedOption = useMemo(() => {
    if (config.evaluationDefinition.properties.dataset.originalSourceRef) {
      return {
        label: refStringToName(
          config.evaluationDefinition.properties.dataset.originalSourceRef
        ),
        value: config.evaluationDefinition.properties.dataset.originalSourceRef,
      };
    }
    if (newDatasetEditorMode === 'new-empty') {
      return selectOptions[0].options[0];
    }
    if (newDatasetEditorMode === 'new-file') {
      return selectOptions[0].options[1];
    }
    return null;
  }, [
    config.evaluationDefinition.properties.dataset.originalSourceRef,
    newDatasetEditorMode,
    selectOptions,
  ]);

  const setDatasetRef = useCallback(
    (datasetRef: string | null) => {
      editConfig(draft => {
        draft.evaluationDefinition.properties.dataset.originalSourceRef =
          datasetRef;
      });
    },
    [editConfig]
  );

  if (refsQuery.loading) {
    return <LoadingSelect />;
  }

  return (
    <Select
      blurInputOnSelect
      options={selectOptions}
      value={selectedOption}
      onChange={option => {
        // TODO: clean this up - this is super messy and needs to be refactored
        if (option?.value === 'new-empty') {
          setNewDatasetEditorMode('new-empty');
          setNewDatasetEditorModeInternal('new-empty');

          setDatasetRef(null);
        } else if (option?.value === 'new-file') {
          setNewDatasetEditorMode('new-file');
          setNewDatasetEditorModeInternal('new-file');

          setDatasetRef(null);
        } else if (option) {
          setDatasetRef(option.value);
        } else {
          setDatasetRef(null);
        }
      }}
    />
  );
};
