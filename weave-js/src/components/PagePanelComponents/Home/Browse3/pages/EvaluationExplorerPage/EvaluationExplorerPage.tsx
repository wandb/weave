import {Button} from '@wandb/weave/components/Button';
import {WaveLoader} from '@wandb/weave/components/Loaders/WaveLoader';
import React, {useCallback, useMemo, useState} from 'react';

import {SimplePageLayoutWithHeader} from '../common/SimplePageLayout';
import {CompareEvaluationsPageContent} from '../CompareEvaluationsPage/CompareEvaluationsPage';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {refStringToName} from './common';
import {LabeledTextArea, LabeledTextField, PickerContainer} from './components';
import {BORDER_COLOR, SECONDARY_BACKGROUND_COLOR} from './constants';
import {
  EvaluationExplorerPageProvider,
  useEvaluationExplorerPageContext,
} from './context';
import {DatasetConfigSection} from './DatasetConfigSection';
import {ExistingDatasetEditor, NewDatasetEditor} from './DatasetEditor';
import {EvaluationPicker} from './EvaluationConfigSection';
import {Column, Header, Row} from './layout';
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
    const {evaluationDefinition, models} = config;

    // Check required text fields
    if (
      !evaluationDefinition.properties.name.trim() ||
      !evaluationDefinition.properties.description.trim()
    ) {
      return false;
    }

    // Check dataset is selected
    if (!evaluationDefinition.properties.dataset.originalSourceRef) {
      return false;
    }

    // Check at least one scorer is configured
    const validScorers = getValidRefs(evaluationDefinition.properties.scorers);
    if (validScorers.length === 0) {
      return false;
    }

    // Check at least one model is configured
    const validModels = getValidRefs(models);
    if (validModels.length === 0) {
      return false;
    }

    return true;
  }, [config]);

  /**
   * Main evaluation execution handler.
   * Creates the evaluation object and runs it with the configured models.
   */
  const handleRunEval = useCallback(async () => {
    if (!isRunEvalEnabled || isRunning) {
      return;
    }

    setIsRunning(true);
    setEvaluationResults(null); // Clear any previous results

    try {
      const client = getClient();
      const {evaluationDefinition, models} = config;

      // Extract valid refs from configuration
      const scorerRefs = getValidRefs(evaluationDefinition.properties.scorers);
      const modelRefs = getValidRefs(models);

      // Create the evaluation object
      const evaluationRef = await createEvaluation(client, entity, project, {
        name: evaluationDefinition.properties.name,
        description: evaluationDefinition.properties.description,
        datasetRef: evaluationDefinition.properties.dataset.originalSourceRef!,
        scorerRefs,
      });

      // Update the config with the created evaluation ref
      editConfig(draft => {
        draft.evaluationDefinition.originalSourceRef = evaluationRef;
        draft.evaluationDefinition.dirtied = false;
      });

      // Execute the evaluation
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
      // TODO: Add proper error handling/display
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
  ]);

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
                console.log('Evaluation call IDs updated:', newIds);
              }}
              selectedMetrics={selectedMetrics}
              setSelectedMetrics={setSelectedMetrics}
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
  handleRunEval: () => Promise<void>;
}> = ({
  entity,
  project,
  setNewDatasetEditorMode,
  isRunning,
  touchedFields,
  markFieldTouched,
  isRunEvalEnabled,
  handleRunEval,
}) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();
  const [showEvaluationPicker, setShowEvaluationPicker] = useState(false);

  // Helper to get validation error messages
  const getValidationErrors = useMemo(() => {
    const errors = {
      name:
        touchedFields.name && config.evaluationDefinition.properties.name === ''
          ? 'Evaluation name is required'
          : undefined,
      dataset: !config.evaluationDefinition.properties.dataset.originalSourceRef
        ? 'Please select or create a dataset'
        : undefined,
      scorers:
        getValidRefs(config.evaluationDefinition.properties.scorers).length ===
        0
          ? 'Please add at least one scorer'
          : undefined,
      models:
        getValidRefs(config.models).length === 0
          ? 'Please add at least one model to evaluate'
          : undefined,
    };
    return errors;
  }, [config, touchedFields]);

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
          <PickerContainer
            title="Select Evaluation"
            style={{marginBottom: '16px'}}>
            <EvaluationPicker entity={entity} project={project} />
          </PickerContainer>
        )}

        <LabeledTextField
          label="Title"
          value={config.evaluationDefinition.properties.name}
          onChange={value => {
            editConfig(draft => {
              draft.evaluationDefinition.properties.name = value;
              draft.evaluationDefinition.dirtied = true;
            });
          }}
          placeholder="Enter evaluation name"
          required
          error={getValidationErrors.name}
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
          rows={3}
          onBlur={() => markFieldTouched('description')}
        />

        <DatasetConfigSection
          entity={entity}
          project={project}
          setNewDatasetEditorMode={setNewDatasetEditorMode}
          error={getValidationErrors.dataset}
        />

        <ScorersConfigSection
          entity={entity}
          project={project}
          error={getValidationErrors.scorers}
        />

        <ModelsConfigSection
          entity={entity}
          project={project}
          error={getValidationErrors.models}
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
