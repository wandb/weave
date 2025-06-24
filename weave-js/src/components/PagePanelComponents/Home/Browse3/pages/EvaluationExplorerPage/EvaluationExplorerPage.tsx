import {Button} from '@wandb/weave/components/Button';
import {Select} from '@wandb/weave/components/Form/Select';
import {TextArea} from '@wandb/weave/components/Form/TextArea';
import {TextField} from '@wandb/weave/components/Form/TextField';
import React, {useCallback, useMemo, useState} from 'react';

import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {refStringToName} from './common';
import {BORDER_COLOR, SECONDARY_BACKGROUND_COLOR} from './constants';
import {
  EvaluationExplorerPageProvider,
  useEvaluationExplorerPageContext,
} from './context';
import {ExistingDatasetEditor, NewDatasetEditor} from './DatasetEditor';
import {clientBound, hookify} from './hooks';
import {Column, Header} from './layout';
import {ConfigSection, Footer, Row} from './layout';
import {getLatestDatasetRefs, getLatestEvaluationRefs} from './query';
import {ScorersConfigSection} from './ScorersConfigSection';

type EvaluationExplorerPageProps = {
  entity: string;
  project: string;
};

export const EvaluationExplorerPage = (props: EvaluationExplorerPageProps) => {
  return (
    <SimplePageLayoutWithHeader
      title="EvaluationExplorer"
      hideTabsIfSingle
      headerContent={null}
      tabs={[
        {
          label: 'main',
          content: (
            <EvaluationExplorerPageProvider>
              <EvaluationExplorerPageInner {...props} />
            </EvaluationExplorerPageProvider>
          ),
        },
      ]}
      headerExtra={null}
    />
  );
};

const EvaluationExplorerPageInner: React.FC<EvaluationExplorerPageProps> = ({
  entity,
  project,
}) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();
  const [newDatasetEditorMode, setNewDatasetEditorMode] = useState<
    'new-empty' | 'new-file'
  >('new-empty');
  const sourceRef =
    config.evaluationDefinition.properties.dataset.originalSourceRef;
  const datasetEditorMode = useMemo(() => {
    if (sourceRef == null) {
      return newDatasetEditorMode;
    }
    return 'existing';
  }, [newDatasetEditorMode, sourceRef]);

  const onNewDatasetSaveComplete = useCallback(
    (datasetRef?: string) => {
      editConfig(draft => {
        draft.evaluationDefinition.properties.dataset.originalSourceRef =
          datasetRef ?? null;
      });
    },
    [editConfig]
  );

  return (
    <Row>
      <ConfigPanel
        entity={entity}
        project={project}
        setNewDatasetEditorMode={setNewDatasetEditorMode}
      />
      <Column style={{flex: '1 1 600px', overflow: 'hidden'}}>
        <Header>Dataset</Header>
        {datasetEditorMode === 'new-empty' && (
          <NewDatasetEditor
            entity={entity}
            project={project}
            onSaveComplete={onNewDatasetSaveComplete}
          />
        )}
        {datasetEditorMode === 'new-file' && (
          <NewDatasetEditor
            entity={entity}
            project={project}
            useFilePicker
            onSaveComplete={onNewDatasetSaveComplete}
          />
        )}
        {datasetEditorMode === 'existing' && sourceRef && (
          <ExistingDatasetEditor datasetRef={sourceRef} />
        )}
      </Column>
    </Row>
  );
};

const ConfigPanel: React.FC<{
  entity: string;
  project: string;
  setNewDatasetEditorMode: (mode: 'new-empty' | 'new-file') => void;
}> = ({entity, project, setNewDatasetEditorMode}) => {
  return (
    <Column
      style={{
        maxWidth: '500px',
        minWidth: '300px',
        flex: '1 1 400px',
        borderRight: `1px solid ${BORDER_COLOR}`,
        backgroundColor: SECONDARY_BACKGROUND_COLOR,
      }}>
      <Header>
        <span>Configuration</span>
        <Button
          icon="settings-parameters"
          size="small"
          variant="secondary"
          onClick={() => {
            console.error('TODO: Implement me');
          }}
        />
      </Header>
      <Column style={{flex: 1, overflowY: 'auto'}}>
        <EvaluationConfigSection
          entity={entity}
          project={project}
          setNewDatasetEditorMode={setNewDatasetEditorMode}
        />
        <ModelsConfigSection entity={entity} project={project} />
      </Column>
      <Footer>
        {/* <Button
          icon="save"
          variant="secondary"
          onClick={() => {
            console.error('TODO: Implement me');
          }}>
          Save all
        </Button> */}
        <Button
          icon="play"
          variant="primary"
          onClick={() => {
            console.error('TODO: Implement me');
          }}>
          Run eval
        </Button>
      </Footer>
    </Column>
  );
};

const LoadingSelect: typeof Select = props => {
  return <Select isDisabled placeholder="Loading..." {...props} />;
};

// Specialized Components

const EvaluationConfigSection: React.FC<{
  entity: string;
  project: string;
  setNewDatasetEditorMode: (mode: 'new-empty' | 'new-file') => void;
}> = ({entity, project, setNewDatasetEditorMode}) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();
  return (
    <ConfigSection title="Evaluation" icon="baseline-alt">
      <EvaluationPicker entity={entity} project={project} />
      <Column
        style={{
          flex: 0,
          borderLeft: `1px solid ${BORDER_COLOR}`,
          marginTop: '16px',
        }}>
        <Row style={{padding: '8px 0px 8px 16px'}}>
          <TextField
            value={config.evaluationDefinition.properties.name}
            placeholder="Evaluation Name"
            onChange={value => {
              editConfig(draft => {
                draft.evaluationDefinition.properties.name = value;
              });
            }}
          />
        </Row>
        <Row style={{padding: '8px 0px 16px 16px'}}>
          <TextArea
            value={config.evaluationDefinition.properties.description}
            placeholder="Evaluation Description"
            onChange={e => {
              editConfig(draft => {
                draft.evaluationDefinition.properties.description =
                  e.target.value;
              });
            }}
          />
        </Row>
        <DatasetConfigSection
          entity={entity}
          project={project}
          setNewDatasetEditorMode={setNewDatasetEditorMode}
        />
        <ScorersConfigSection entity={entity} project={project} />
      </Column>
    </ConfigSection>
  );
};

const useLatestEvaluationRefs = clientBound(hookify(getLatestEvaluationRefs));
const EvaluationPicker: React.FC<{entity: string; project: string}> = ({
  entity,
  project,
}) => {
  const refsQuery = useLatestEvaluationRefs(entity, project);
  const newEvaluationOption = useMemo(() => {
    return {
      label: 'New Evaluation',
      value: 'new-evaluation',
    };
  }, []);
  const selectOptions = useMemo(() => {
    return [
      newEvaluationOption,
      ...(refsQuery.data?.map(ref => ({
        label: ref,
      })) ?? []),
    ];
  }, [refsQuery.data, newEvaluationOption]);
  const selectedValue = useMemo(() => {
    return selectOptions[0];
  }, [selectOptions]);

  if (refsQuery.loading) {
    return <LoadingSelect />;
  }

  return (
    <Select
      options={selectOptions}
      value={selectedValue}
      onChange={option => {
        console.log(option);
        console.error('TODO: Implement me');
      }}
    />
  );
};

const DatasetConfigSection: React.FC<{
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

const ModelsConfigSection: React.FC<{entity: string; project: string}> = ({
  entity,
  project,
}) => {
  return (
    <ConfigSection title="Models" icon="model">
      <Column style={{gap: '8px'}}>
        <Row style={{alignItems: 'center', gap: '8px'}}>
          <div style={{flex: 1}}>
            <Select
              options={[]}
              value={''}
              onChange={option => {
                console.log(option);
                console.error('TODO: Implement me');
              }}
            />
          </div>
          <Button
            icon="settings"
            variant="ghost"
            onClick={() => {
              console.error('TODO: Implement me');
            }}
          />
          <Button
            icon="copy"
            variant="ghost"
            onClick={() => {
              console.error('TODO: Implement me');
            }}
          />
          <Button
            icon="remove"
            variant="ghost"
            onClick={() => {
              console.error('TODO: Implement me');
            }}
          />
        </Row>
        <Row>
          <Button
            icon="add-new"
            variant="ghost"
            onClick={() => {
              console.error('TODO: Implement me');
            }}
          />
        </Row>
      </Column>
    </ConfigSection>
  );
};
