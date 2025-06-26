import {Button} from '@wandb/weave/components/Button';
import {TextArea} from '@wandb/weave/components/Form/TextArea';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import React, {useCallback, useMemo, useState} from 'react';

import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {CompareEvaluationsPageContent} from '../CompareEvaluationsPage/CompareEvaluationsPage';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {refStringToName} from './common';
import {LoadingSelect} from './components';
import {LabeledTextArea, LabeledTextField} from './components';
import {BORDER_COLOR, SECONDARY_BACKGROUND_COLOR} from './constants';
import {
  EvaluationExplorerPageProvider,
  useEvaluationExplorerPageContext,
} from './context';
import {DatasetConfigSection} from './DatasetConfigSection';
import {ExistingDatasetEditor, NewDatasetEditor} from './DatasetEditor';
import {EvaluationPicker} from './EvaluationConfigSection';
import {Column, ConfigSection, Header, Row} from './layout';
import {Footer} from './layout';
import {ModelsConfigSection} from './ModelsConfigSection';
import {createEvaluation, runEvaluation} from './query';
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
  const getClient = useGetTraceServerClientContext();
  const [newDatasetEditorMode, setNewDatasetEditorMode] = useState<
    'new-empty' | 'new-file' | null
  >(null);
  const [evaluationResults, setEvaluationResults] = useState<string[] | null>(
    null
  );
  const [isRunning, setIsRunning] = useState(false);
  const [selectedMetrics, setSelectedMetrics] = useState<Record<
    string,
    boolean
  > | null>(null);
  const [touchedFields, setTouchedFields] = useState<{
    name: boolean;
    description: boolean;
  }>({
    name: false,
    description: false,
  });

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

  const markFieldTouched = useCallback((field: 'name' | 'description') => {
    setTouchedFields(prev => ({...prev, [field]: true}));
  }, []);

  const isRunEvalEnabled = useMemo(() => {
    const {evaluationDefinition, models} = config;

    if (
      !evaluationDefinition.properties.name.trim() ||
      !evaluationDefinition.properties.description.trim()
    ) {
      return false;
    }

    if (!evaluationDefinition.properties.dataset.originalSourceRef) {
      return false;
    }

    const validScorers = evaluationDefinition.properties.scorers.filter(
      scorer => scorer.originalSourceRef !== null
    );
    if (validScorers.length === 0) {
      return false;
    }

    const validModels = models.filter(
      model => model.originalSourceRef !== null
    );
    if (validModels.length === 0) {
      return false;
    }

    return true;
  }, [config]);

  const handleRunEval = useCallback(async () => {
    if (!isRunEvalEnabled || isRunning) {
      return;
    }

    setIsRunning(true);
    setEvaluationResults(null);

    try {
      const client = getClient();
      const {evaluationDefinition, models} = config;

      const scorerRefs = evaluationDefinition.properties.scorers
        .filter(scorer => scorer.originalSourceRef !== null)
        .map(scorer => scorer.originalSourceRef!);

      const modelRefs = models
        .filter(model => model.originalSourceRef !== null)
        .map(model => model.originalSourceRef!);

      const evaluationRef = await createEvaluation(client, entity, project, {
        name: evaluationDefinition.properties.name,
        description: evaluationDefinition.properties.description,
        datasetRef: evaluationDefinition.properties.dataset.originalSourceRef!,
        scorerRefs,
      });

      editConfig(draft => {
        draft.evaluationDefinition.originalSourceRef = evaluationRef;
        draft.evaluationDefinition.dirtied = false;
      });

      const results = await runEvaluation(
        client,
        entity,
        project,
        evaluationRef,
        modelRefs
      );

      console.log('Evaluation completed:', results);
      setEvaluationResults(results);
    } catch (error) {
      console.error('Failed to run evaluation:', error);
    } finally {
      setIsRunning(false);
    }
  }, [
    config,
    entity,
    project,
    isRunEvalEnabled,
    isRunning,
    getClient,
    editConfig,
    setEvaluationResults,
  ]);

  return (
    <Row>
      <ConfigPanel
        entity={entity}
        project={project}
        setNewDatasetEditorMode={setNewDatasetEditorMode}
        isRunning={isRunning}
        setIsRunning={setIsRunning}
        setEvaluationResults={setEvaluationResults}
        touchedFields={touchedFields}
        markFieldTouched={markFieldTouched}
        isRunEvalEnabled={isRunEvalEnabled}
        handleRunEval={handleRunEval}
      />
      <Column style={{flex: '1 1 600px', overflow: 'hidden'}}>
        {evaluationResults ? (
          <>
            <Header>
              <span>Results</span>
              <Button
                icon="back"
                size="small"
                variant="secondary"
                onClick={() => setEvaluationResults(null)}>
                Back to Dataset
              </Button>
            </Header>
            <CompareEvaluationsPageContent
              entity={entity}
              project={project}
              evaluationCallIds={evaluationResults}
              onEvaluationCallIdsUpdate={newIds => {
                console.log('Evaluation call IDs updated:', newIds);
              }}
              selectedMetrics={selectedMetrics}
              setSelectedMetrics={setSelectedMetrics}
            />
          </>
        ) : (
          <>
            <Header>Dataset</Header>
            {isRunning ? (
              <Column
                style={{
                  flex: 1,
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '48px',
                }}>
                <WaveLoader size="small" />
                <p style={{marginTop: '16px', color: '#666'}}>
                  Running evaluation...
                </p>
              </Column>
            ) : (
              <>
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
              </>
            )}
          </>
        )}
      </Column>
    </Row>
  );
};

const ConfigPanel: React.FC<{
  entity: string;
  project: string;
  setNewDatasetEditorMode: (mode: 'new-empty' | 'new-file' | null) => void;
  isRunning: boolean;
  setIsRunning: (running: boolean) => void;
  setEvaluationResults: (results: string[] | null) => void;
  touchedFields: {name: boolean; description: boolean};
  markFieldTouched: (field: 'name' | 'description') => void;
  isRunEvalEnabled: boolean;
  handleRunEval: () => Promise<void>;
}> = ({
  entity,
  project,
  setNewDatasetEditorMode,
  isRunning,
  setIsRunning,
  setEvaluationResults,
  touchedFields,
  markFieldTouched,
  isRunEvalEnabled,
  handleRunEval,
}) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();
  const [showEvaluationPicker, setShowEvaluationPicker] = useState(false);

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
        <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
          {!showEvaluationPicker &&
            config.evaluationDefinition.originalSourceRef && (
              <span style={{fontSize: '14px', color: '#666'}}>
                (
                {refStringToName(config.evaluationDefinition.originalSourceRef)}
                )
              </span>
            )}
          <Button
            icon={showEvaluationPicker ? 'chevron-up' : 'chevron-down'}
            variant="ghost"
            tooltip={
              showEvaluationPicker
                ? 'Hide evaluation picker'
                : 'Load from a previous evaluation'
            }
            onClick={() => {
              setShowEvaluationPicker(!showEvaluationPicker);
            }}>
            {showEvaluationPicker ? 'Hide' : 'Load'}
          </Button>
        </div>
      </Header>
      <Column
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '16px',
          backgroundColor: SECONDARY_BACKGROUND_COLOR,
          gap: '16px',
        }}>
        {showEvaluationPicker && (
          <div
            style={{
              padding: '12px',
              backgroundColor: '#f5f5f5',
              borderRadius: '4px',
            }}>
            <div
              style={{
                fontSize: '12px',
                fontWeight: 600,
                color: '#666',
                marginBottom: '8px',
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
              }}>
              Select Evaluation
            </div>
            <EvaluationPicker entity={entity} project={project} />
          </div>
        )}

        <LabeledTextField
          label="Evaluation Name"
          value={config.evaluationDefinition.properties.name}
          onChange={value => {
            editConfig(draft => {
              draft.evaluationDefinition.properties.name = value;
              draft.evaluationDefinition.dirtied = true;
            });
          }}
          placeholder="Enter evaluation name"
          required
          error={
            touchedFields.name &&
            config.evaluationDefinition.properties.name === ''
              ? 'Evaluation name is required'
              : undefined
          }
          instructions="A unique name to identify this evaluation"
          onBlur={() => markFieldTouched('name')}
        />

        <LabeledTextArea
          label="Description"
          value={config.evaluationDefinition.properties.description}
          onChange={e => {
            editConfig(draft => {
              draft.evaluationDefinition.properties.description =
                e.target.value;
              draft.evaluationDefinition.dirtied = true;
            });
          }}
          placeholder="Enter evaluation description"
          required
          error={
            touchedFields.description &&
            config.evaluationDefinition.properties.description === ''
              ? 'Description is required'
              : undefined
          }
          instructions="Describe what this evaluation is testing"
          rows={3}
          onBlur={() => markFieldTouched('description')}
        />

        <DatasetConfigSection
          entity={entity}
          project={project}
          setNewDatasetEditorMode={setNewDatasetEditorMode}
          error={
            !config.evaluationDefinition.properties.dataset.originalSourceRef
              ? 'Please select or create a dataset'
              : undefined
          }
        />

        <ScorersConfigSection
          entity={entity}
          project={project}
          error={
            config.evaluationDefinition.properties.scorers.filter(
              scorer => scorer.originalSourceRef !== null
            ).length === 0
              ? 'Please add at least one scorer'
              : undefined
          }
        />

        <ModelsConfigSection
          entity={entity}
          project={project}
          error={
            config.models.filter(model => model.originalSourceRef !== null)
              .length === 0
              ? 'Please add at least one model to evaluate'
              : undefined
          }
        />
      </Column>
      <Footer>
        <Button
          icon="play"
          variant="primary"
          disabled={!isRunEvalEnabled || isRunning}
          onClick={handleRunEval}>
          {isRunning ? 'Running...' : 'Run eval'}
        </Button>
      </Footer>
    </Column>
  );
};
