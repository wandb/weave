import {Button} from '@wandb/weave/components/Button';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import React, {useCallback, useMemo, useRef, useState} from 'react';

import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {CompareEvaluationsPageContent} from '../CompareEvaluationsPage/CompareEvaluationsPage';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {sanitizeObjectId} from '../wfReactInterface/traceServerDirectClient';
import {refStringToName} from './common';
import {LabeledTextArea, LabeledTextField} from './components';
import {BORDER_COLOR, SECONDARY_BACKGROUND_COLOR} from './constants';
import {
  EvaluationExplorerPageProvider,
  useEvaluationExplorerPageContext,
} from './context';
import {DatasetConfigSection} from './DatasetConfigSection';
import {
  DatasetEditorRef,
  ExistingDatasetEditor,
  NewDatasetEditor,
} from './DatasetEditor';
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

/**
 * Main entry point for the Evaluation Explorer page.
 * Wraps the inner component with necessary providers and layout.
 */
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

// Helper functions to reduce repetition
const getValidRefs = <T extends {originalSourceRef: string | null}>(
  items: T[]
): string[] => {
  return items
    .filter(item => item.originalSourceRef !== null)
    .map(item => item.originalSourceRef!);
};

/**
 * Core component that manages the evaluation configuration and execution flow.
 * Split into three main states:
 * 1. Configuration - Setting up the evaluation parameters
 * 2. Running - Executing the evaluation
 * 3. Results - Viewing the evaluation results
 */
const EvaluationExplorerPageInner: React.FC<EvaluationExplorerPageProps> = ({
  entity,
  project,
}) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();
  const getClient = useGetTraceServerClientContext();

  // Dataset editor refs
  const datasetEditorRef = useRef<DatasetEditorRef | null>(null);

  // Dataset editor state management
  const [newDatasetEditorMode, setNewDatasetEditorMode] = useState<
    'new-empty' | 'new-file' | null
  >(null);

  // Evaluation execution state
  const [evaluationResults, setEvaluationResults] = useState<string[] | null>(
    null
  );
  const [isRunning, setIsRunning] = useState(false);

  // Results view state
  const [selectedMetrics, setSelectedMetrics] = useState<Record<
    string,
    boolean
  > | null>(null);

  // Form validation state
  const [touchedFields, setTouchedFields] = useState<{
    name: boolean;
    description: boolean;
  }>({
    name: false,
    description: false,
  });

  // Determine which dataset editor mode to use based on current state
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

  // Validation logic for enabling the "Run eval" button
  const isRunEvalEnabled = useMemo(() => {
    return true;
    // const {evaluationDefinition, models} = config;

    // // Check required text fields
    // if (!evaluationDefinition.properties.name.trim()) {
    //   return false;
    // }

    // // Check dataset is selected
    // if (!evaluationDefinition.properties.dataset.originalSourceRef) {
    //   return false;
    // }

    // // Check at least one scorer is configured
    // const validScorers = getValidRefs(evaluationDefinition.properties.scorers);
    // if (validScorers.length === 0) {
    //   return false;
    // }

    // // Check at least one model is configured
    // const validModels = getValidRefs(models);
    // if (validModels.length === 0) {
    //   return false;
    // }

    // return true;
  }, []);

  /**
   * Main evaluation execution handler.
   * Creates the evaluation object and runs it with the configured models.
   */
  const handleRunEval = useCallback(
    async (
      scorerRefs?: string[],
      modelRefs?: string[],
      datasetRef?: string
    ) => {
      if (!isRunEvalEnabled || isRunning) {
        return;
      }

      setIsRunning(true);
      setEvaluationResults(null); // Clear any previous results

      try {
        const client = getClient();
        const {evaluationDefinition, models} = config;

        // Use provided refs or extract from current configuration
        const finalScorerRefs =
          scorerRefs ?? getValidRefs(evaluationDefinition.properties.scorers);
        const finalModelRefs = modelRefs ?? getValidRefs(models);
        const finalDatasetRef =
          datasetRef ??
          evaluationDefinition.properties.dataset.originalSourceRef;

        if (!finalDatasetRef) {
          throw new Error('Dataset ref is required but was not found');
        }

        // Create the evaluation object
        const evaluationRef = await createEvaluation(client, entity, project, {
          name: sanitizeObjectId(evaluationDefinition.properties.name),
          description: evaluationDefinition.properties.description,
          datasetRef: finalDatasetRef,
          scorerRefs: finalScorerRefs,
        });

        // Update the config with the created evaluation ref
        await editConfig(draft => {
          draft.evaluationDefinition.originalSourceRef = evaluationRef;
        });

        // Execute the evaluation
        const results = await runEvaluation(
          client,
          entity,
          project,
          evaluationRef,
          finalModelRefs
        );

        setEvaluationResults(results);
      } catch (error) {
        console.error('Failed to run evaluation:', error);
        // TODO: Add proper error handling/display
      } finally {
        setIsRunning(false);
      }
    },
    [
      config,
      entity,
      project,
      isRunEvalEnabled,
      isRunning,
      getClient,
      editConfig,
    ]
  );

  return (
    <Row>
      <ConfigPanel
        entity={entity}
        project={project}
        setNewDatasetEditorMode={setNewDatasetEditorMode}
        isRunning={isRunning}
        touchedFields={touchedFields}
        markFieldTouched={markFieldTouched}
        isRunEvalEnabled={isRunEvalEnabled}
        handleRunEval={handleRunEval}
        datasetEditorRef={datasetEditorRef}
      />
      <Column style={{flex: '1 1 600px', overflow: 'hidden'}}>
        {evaluationResults ? (
          // Results view
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
                // Pass - remove?
              }}
              selectedMetrics={selectedMetrics}
              setSelectedMetrics={setSelectedMetrics}
              initialTabValue="results"
              hideEvalPicker
            />
          </>
        ) : (
          // Dataset editor view
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
                    ref={datasetEditorRef}
                    entity={entity}
                    project={project}
                    onSaveComplete={onNewDatasetSaveComplete}
                  />
                )}
                {datasetEditorMode === 'new-file' && (
                  <NewDatasetEditor
                    ref={datasetEditorRef}
                    entity={entity}
                    project={project}
                    useFilePicker
                    onSaveComplete={onNewDatasetSaveComplete}
                  />
                )}
                {datasetEditorMode === 'existing' && sourceRef && (
                  <ExistingDatasetEditor
                    ref={datasetEditorRef}
                    datasetRef={sourceRef}
                    onSaveComplete={onNewDatasetSaveComplete}
                  />
                )}
              </>
            )}
          </>
        )}
      </Column>
    </Row>
  );
};

/**
 * Configuration panel component that contains all the evaluation setup forms.
 * Manages the evaluation, dataset, scorers, and models configuration.
 */
const ConfigPanel: React.FC<{
  entity: string;
  project: string;
  setNewDatasetEditorMode: (mode: 'new-empty' | 'new-file' | null) => void;
  isRunning: boolean;
  touchedFields: {name: boolean; description: boolean};
  markFieldTouched: (field: 'name' | 'description') => void;
  isRunEvalEnabled: boolean;
  handleRunEval: (
    scorerRefs?: string[],
    modelRefs?: string[],
    datasetRef?: string
  ) => Promise<void>;
  datasetEditorRef: React.MutableRefObject<DatasetEditorRef | null>;
}> = ({
  entity,
  project,
  setNewDatasetEditorMode,
  isRunning,
  touchedFields,
  markFieldTouched,
  isRunEvalEnabled,
  handleRunEval,
  datasetEditorRef,
}) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();
  const [showEvaluationPicker, setShowEvaluationPicker] = useState(false);

  // Refs for config sections to save unsaved changes
  const scorersConfigRef = useRef<{
    saveAllUnsaved: () => Promise<void>;
    saveAllUnsavedAndGetRefs: () => Promise<string[]>;
  } | null>(null);
  const modelsConfigRef = useRef<{
    saveAllUnsaved: () => Promise<void>;
    saveAllUnsavedAndGetRefs: () => Promise<string[]>;
  } | null>(null);

  // Wrap handleRunEval to save all unsaved changes first
  const handleRunEvalWithSave = useCallback(async () => {
    // Save dataset first if there's one being edited
    let freshDatasetRef: string | undefined;
    if (datasetEditorRef.current) {
      const savedDatasetRef = await datasetEditorRef.current.save();
      if (savedDatasetRef) {
        freshDatasetRef = savedDatasetRef;
        // Update the config with the saved dataset ref
        editConfig(draft => {
          draft.evaluationDefinition.properties.dataset.originalSourceRef =
            savedDatasetRef;
        });
      }
    }

    // Save all unsaved changes and get fresh refs
    const promises: {
      scorerRefs?: Promise<string[]>;
      modelRefs?: Promise<string[]>;
    } = {};

    if (scorersConfigRef.current?.saveAllUnsavedAndGetRefs) {
      promises.scorerRefs = scorersConfigRef.current.saveAllUnsavedAndGetRefs();
    }

    if (modelsConfigRef.current?.saveAllUnsavedAndGetRefs) {
      promises.modelRefs = modelsConfigRef.current.saveAllUnsavedAndGetRefs();
    }

    // Wait for all saves to complete and get the fresh refs
    const [freshScorerRefs, freshModelRefs] = await Promise.all([
      promises.scorerRefs || Promise.resolve(undefined),
      promises.modelRefs || Promise.resolve(undefined),
    ]);

    // Run the evaluation with the fresh refs
    await handleRunEval(freshScorerRefs, freshModelRefs, freshDatasetRef);
  }, [handleRunEval, datasetEditorRef, editConfig]);

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
          {config.evaluationDefinition.originalSourceRef && (
            <span style={{fontSize: '14px', color: '#666'}}>
              ({refStringToName(config.evaluationDefinition.originalSourceRef)})
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
            }}></Button>
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
          <ConfigSection
            title="Load existing evaluation"
            icon="baseline-alt"
            style={{
              borderBottom: `1px solid ${BORDER_COLOR}`,
              paddingBottom: '16px',
            }}>
            <EvaluationPicker entity={entity} project={project} />
          </ConfigSection>
        )}
        <LabeledTextField
          label="Title"
          value={config.evaluationDefinition.properties.name}
          onChange={value => {
            editConfig(draft => {
              draft.evaluationDefinition.properties.name = value;
            });
          }}
          placeholder="Enter evaluation name"
          required
          onBlur={() => markFieldTouched('name')}
        />

        <LabeledTextArea
          label="Description"
          value={config.evaluationDefinition.properties.description}
          onChange={e => {
            editConfig(draft => {
              draft.evaluationDefinition.properties.description =
                e.target.value;
            });
          }}
          placeholder="Enter evaluation description"
          rows={3}
          onBlur={() => markFieldTouched('description')}
        />

        <DatasetConfigSection
          entity={entity}
          project={project}
          setNewDatasetEditorMode={setNewDatasetEditorMode}
        />

        <ScorersConfigSection
          entity={entity}
          project={project}
          ref={scorersConfigRef}
        />

        <ModelsConfigSection
          entity={entity}
          project={project}
          ref={modelsConfigRef}
        />
      </Column>
      <Footer>
        <Button
          icon="play"
          variant="primary"
          disabled={!isRunEvalEnabled || isRunning}
          onClick={handleRunEvalWithSave}
          tooltip={
            isRunEvalEnabled && !isRunning
              ? 'Saves all unsaved changes before running'
              : undefined
          }>
          {isRunning ? 'Running...' : 'Run eval'}
        </Button>
      </Footer>
    </Column>
  );
};
