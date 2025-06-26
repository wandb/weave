import {Button} from '@wandb/weave/components/Button';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import React, {useCallback, useMemo, useState} from 'react';

import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {CompareEvaluationsPageContent} from '../CompareEvaluationsPage/CompareEvaluationsPage';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {refStringToName} from './common';
import {BORDER_COLOR, SECONDARY_BACKGROUND_COLOR} from './constants';
import {
  EvaluationExplorerPageProvider,
  useEvaluationExplorerPageContext,
} from './context';
import {ExistingDatasetEditor, NewDatasetEditor} from './DatasetEditor';
import {EvaluationConfigSection, EvaluationPicker} from './EvaluationConfigSection';
import {Column, Header} from './layout';
import {Footer, Row} from './layout';
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
        isRunning={isRunning}
        setIsRunning={setIsRunning}
        setEvaluationResults={setEvaluationResults}
      />
      <Column style={{flex: '1 1 600px', overflow: 'hidden'}}>
        {evaluationResults ? (
          // Show evaluation results
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
                // Handle updates if needed
                console.log('Evaluation call IDs updated:', newIds);
              }}
              selectedMetrics={selectedMetrics}
              setSelectedMetrics={setSelectedMetrics}
            />
          </>
        ) : (
          // Show dataset editor or loading state
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
}> = ({
  entity,
  project,
  setNewDatasetEditorMode,
  isRunning,
  setIsRunning,
  setEvaluationResults,
}) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();
  const getClient = useGetTraceServerClientContext();
  const [showEvaluationPicker, setShowEvaluationPicker] = useState(false);

  // Validation logic
  const isRunEvalEnabled = useMemo(() => {
    const {evaluationDefinition, models} = config;

    // Check name and description
    if (
      !evaluationDefinition.properties.name.trim() ||
      !evaluationDefinition.properties.description.trim()
    ) {
      return false;
    }

    // Check dataset is saved as a ref
    if (!evaluationDefinition.properties.dataset.originalSourceRef) {
      return false;
    }

    // Check there's at least 1 scorer
    const validScorers = evaluationDefinition.properties.scorers.filter(
      scorer => scorer.originalSourceRef !== null
    );
    if (validScorers.length === 0) {
      return false;
    }

    // Check there's at least 1 model
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
    setEvaluationResults(null); // Clear previous results to show loader

    try {
      const client = getClient();
      const {evaluationDefinition, models} = config;

      // Get valid scorers and models
      const scorerRefs = evaluationDefinition.properties.scorers
        .filter(scorer => scorer.originalSourceRef !== null)
        .map(scorer => scorer.originalSourceRef!);

      const modelRefs = models
        .filter(model => model.originalSourceRef !== null)
        .map(model => model.originalSourceRef!);

      // Create evaluation
      const evaluationRef = await createEvaluation(client, entity, project, {
        name: evaluationDefinition.properties.name,
        description: evaluationDefinition.properties.description,
        datasetRef: evaluationDefinition.properties.dataset.originalSourceRef!,
        scorerRefs,
      });

      // Update the config with the new evaluation ref
      editConfig(draft => {
        draft.evaluationDefinition.originalSourceRef = evaluationRef;
        draft.evaluationDefinition.dirtied = false;
      });

      // Run evaluation
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
      // TODO: Show error message to user
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
          {!showEvaluationPicker && config.evaluationDefinition.originalSourceRef && (
            <span style={{fontSize: '14px', color: '#666'}}>
              ({refStringToName(config.evaluationDefinition.originalSourceRef)})
            </span>
          )}
          <Button
            icon={showEvaluationPicker ? "chevron-up" : "chevron-down"}
            variant="ghost"
            tooltip={showEvaluationPicker ? "Hide evaluation picker" : "Load from a previous evaluation"}
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
        }}>
        {showEvaluationPicker && (
          <div style={{
            marginBottom: '16px',
            padding: '12px',
            backgroundColor: '#f5f5f5',
            borderRadius: '4px',
          }}>
            <div style={{
              fontSize: '12px',
              fontWeight: 600,
              color: '#666',
              marginBottom: '8px',
              textTransform: 'uppercase',
              letterSpacing: '0.5px'
            }}>
              Select Evaluation
            </div>
            <EvaluationPicker 
              entity={entity} 
              project={project}
            />
          </div>
        )}
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
          disabled={!isRunEvalEnabled || isRunning}
          onClick={handleRunEval}>
          {isRunning ? 'Running...' : 'Run eval'}
        </Button>
      </Footer>
    </Column>
  );
};
