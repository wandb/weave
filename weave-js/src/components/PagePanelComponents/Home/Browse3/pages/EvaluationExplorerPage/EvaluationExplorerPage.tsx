import {Button} from '@wandb/weave/components/Button';
import React, {useCallback, useMemo, useState} from 'react';

import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {BORDER_COLOR, SECONDARY_BACKGROUND_COLOR} from './constants';
import {
  EvaluationExplorerPageProvider,
  useEvaluationExplorerPageContext,
} from './context';
import {ExistingDatasetEditor, NewDatasetEditor} from './DatasetEditor';
import {EvaluationConfigSection} from './EvaluationConfigSection';
import {Column, Header} from './layout';
import {Footer, Row} from './layout';
import {ModelsConfigSection} from './ModelsConfigSection';

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
  const {config} = useEvaluationExplorerPageContext();
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
        <Button
          icon="play"
          variant="primary"
          onClick={() => {
            console.log(config);
            console.error('TODO: Implement me');
          }}>
          Run eval
        </Button>
      </Footer>
    </Column>
  );
};
