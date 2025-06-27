import {MOON_100, MOON_200} from '@wandb/weave/common/css/color.styles';
import {Button} from '@wandb/weave/components/Button';
import {TextArea} from '@wandb/weave/components/Form/TextArea';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react';

import {ReusableDrawer} from '../../ReusableDrawer';
import {
  ModelConfigurationForm,
  ModelConfigurationFormRef,
} from '../MonitorsPage/ScorerForms/ModelConfigurationForm';
import {LLMDropdownLoaded} from '../PlaygroundPage/PlaygroundChat/LLMDropdown';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {refStringToName} from './common';
import {LoadingSelect} from './components';
import {useEvaluationExplorerPageContext} from './context';
import {clientBound, hookify} from './hooks';
import {Column, ConfigSection, Row} from './layout';
import {
  getLatestModelRefs,
  getSimplifiedLLMStructuredCompletionModel,
  publishSimplifiedLLMStructuredCompletionModel,
} from './query';
import {defaultModelConfigPayload} from './state';
import {SimplifiedLLMStructuredCompletionModel} from './types';
import {VersionedObjectPicker} from './VersionedObjectPicker';

// Helper to get valid refs from items
const getValidRefs = <T extends {originalSourceRef: string | null}>(
  items: T[]
): string[] => {
  return items
    .filter(item => item.originalSourceRef !== null)
    .map(item => item.originalSourceRef!);
};

// Default option for creating a new model from scratch
const newModelOption = {
  label: 'New Model',
  value: 'new-model',
};

// Create the hook for fetching model refs
// This wraps the async query function in a React hook that manages loading/error states
const useLatestModelRefs = clientBound(hookify(getLatestModelRefs));
const useSimplifiedModel = clientBound(
  hookify(getSimplifiedLLMStructuredCompletionModel)
);

interface SimplifiedModelConfigProps {
  entity: string;
  project: string;
  modelRef: string | null;
  modelNdx: number;
  onModelSaved: (modelNdx: number, newRef: string) => void;
  onOpenAdvancedSettings: (
    modelNdx: number,
    simplifiedConfig: SimplifiedLLMStructuredCompletionModel
  ) => void;
  onSaveStateChange: (
    canSave: boolean,
    saveHandler: () => Promise<string>
  ) => void;
}

/**
 * Simplified model configuration form for basic LLM models.
 * Provides an inline form for models that don't require advanced configuration.
 */
const SimplifiedModelConfig: React.FC<SimplifiedModelConfigProps> = ({
  entity,
  project,
  modelRef,
  modelNdx,
  onModelSaved,
  onOpenAdvancedSettings,
  onSaveStateChange,
}) => {
  const client = useGetTraceServerClientContext()();
  // Local state for the simplified form
  const [config, setConfig] = useState<SimplifiedLLMStructuredCompletionModel>(
    defaultModelConfigPayload
  );

  const [isSaving, setIsSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(!modelRef); // New models start with unsaved changes
  const [initialLoadComplete, setInitialLoadComplete] = useState(false);

  const simplifiedModelQuery = useSimplifiedModel(
    entity,
    project,
    modelRef ?? ''
  );

  // Load existing model configuration when ref changes
  useEffect(() => {
    if (
      modelRef &&
      simplifiedModelQuery.data !== null &&
      !simplifiedModelQuery.loading
    ) {
      setConfig(simplifiedModelQuery.data);
      setHasUnsavedChanges(false);
      setInitialLoadComplete(true);
    } else if (!modelRef) {
      // For new models, mark as loaded immediately
      setInitialLoadComplete(true);
    }
  }, [modelRef, simplifiedModelQuery.data, simplifiedModelQuery.loading]);

  // Track unsaved changes
  const updateConfig = useCallback(
    (updates: Partial<SimplifiedLLMStructuredCompletionModel>) => {
      setConfig(prev => ({...prev, ...updates}));
      setHasUnsavedChanges(true);
    },
    []
  );

  // Validation: all fields are required
  const isValid =
    config.name.trim() !== '' &&
    config.systemPrompt.trim() !== '' &&
    config.llmModelId.trim() !== '';

  const handleSave = useCallback(async () => {
    if (!isValid || isSaving) return '';

    setIsSaving(true);
    try {
      // Save the model directly
      const modelRef = await publishSimplifiedLLMStructuredCompletionModel(
        client,
        entity,
        project,
        config
      );

      if (modelRef) {
        setHasUnsavedChanges(false);
        onModelSaved(modelNdx, modelRef);
        return modelRef; // Return the ref for the save-all handler
      }
      return '';
    } catch (error) {
      console.error('Failed to save model:', error);
      // TODO: Add proper error handling
      return '';
    } finally {
      setIsSaving(false);
    }
  }, [
    isValid,
    isSaving,
    client,
    entity,
    project,
    config,
    modelNdx,
    onModelSaved,
  ]);

  // Check if this model qualifies for simplified config
  const qualifies = !modelRef || simplifiedModelQuery.data !== null;
  const isLoading = modelRef && simplifiedModelQuery.loading;

  // Notify parent about save state changes
  useEffect(() => {
    const canSave = hasUnsavedChanges && isValid && !isSaving;
    onSaveStateChange(canSave, canSave ? handleSave : (null as any));
  }, [hasUnsavedChanges, isValid, isSaving, handleSave, onSaveStateChange]);

  // For new models, if LLM is auto-selected, mark as having unsaved changes
  useEffect(() => {
    if (!modelRef && config.llmModelId && initialLoadComplete) {
      setHasUnsavedChanges(true);
    }
  }, [modelRef, config.llmModelId, initialLoadComplete]);

  // Show loading state while checking if model qualifies
  if (isLoading || !initialLoadComplete) {
    return (
      <div
        style={{
          padding: '12px',
          backgroundColor: MOON_100,
          borderBottomLeftRadius: '4px',
          borderBottomRightRadius: '4px',
          fontSize: '14px',
          color: '#666',
          textAlign: 'center',
        }}>
        Loading model configuration...
      </div>
    );
  }

  // Show advanced configuration notice for complex models
  if (!qualifies) {
    return (
      <div
        style={{
          padding: '12px',
          backgroundColor: MOON_100,
          borderBottomLeftRadius: '4px',
          borderBottomRightRadius: '4px',
          fontSize: '14px',
          color: '#666',
          fontStyle: 'italic',
        }}>
        This model uses advanced configuration.{' '}
        <Button
          variant="ghost"
          size="small"
          onClick={() => onOpenAdvancedSettings(modelNdx, config)}
          style={{padding: '2px 8px', fontSize: '14px'}}>
          Edit settings →
        </Button>
      </div>
    );
  }

  return (
    <Column
      style={{
        padding: '12px',
        backgroundColor: MOON_100,
        borderBottomLeftRadius: '4px',
        borderBottomRightRadius: '4px',
        gap: '8px',
      }}>
      <Row style={{gap: '8px'}}>
        <div style={{flex: '1 1 1px'}}>
          <TextField
            placeholder="Model name"
            value={config.name}
            onChange={value => updateConfig({name: value})}
          />
        </div>
      </Row>
      <Row>
        <TextArea
          placeholder="Enter the system prompt (e.g., 'You are a helpful assistant that...')"
          value={config.systemPrompt}
          onChange={e => updateConfig({systemPrompt: e.target.value})}
          rows={3}
          style={{width: '100%'}}
        />
      </Row>
      <LLMDropdownLoaded
        className="w-full"
        hideSavedModels
        value={config.llmModelId || ''}
        isTeamAdmin={false}
        direction={{horizontal: 'right'}}
        selectFirstAvailable={true}
        onChange={(modelValue: string) => {
          updateConfig({llmModelId: modelValue});
        }}
      />
    </Column>
  );
};

/**
 * Drawer component for configuring model details.
 * Provides a form interface for editing model properties like name, prompts, and output schema.
 *
 * @param entity - The Weave entity (organization/user)
 * @param project - The Weave project
 * @param open - Whether the drawer is open
 * @param onClose - Callback when drawer closes, receives new model ref if saved
 * @param initialModel - Existing model data to edit (optional)
 */
const ModelDrawer: React.FC<{
  entity: string;
  project: string;
  open: boolean;
  onClose: (newModelRef?: string) => void;
  initialModelRef?: string;
}> = ({entity, project, open, onClose, initialModelRef}) => {
  const modelFormRef = useRef<ModelConfigurationFormRef | null>(null);

  const onSave = useCallback(async () => {
    const newModelRef = await modelFormRef.current?.saveModel();
    onClose(newModelRef);
  }, [onClose]);

  return (
    <ReusableDrawer
      open={open}
      onClose={() => onClose()}
      title="Model Configuration"
      onSave={onSave}>
      <Tailwind>
        <ModelConfigurationForm
          key={initialModelRef ?? 'new-model'}
          ref={modelFormRef}
          initialModelRef={initialModelRef ?? undefined}
          onValidationChange={() => {
            // Pass - validation is handled internally by the form
          }}
        />
      </Tailwind>
    </ReusableDrawer>
  );
};

/**
 * Individual model row component with object picker and simplified configuration.
 * Handles both simple and advanced model configurations.
 */
const ModelRow: React.FC<{
  entity: string;
  project: string;
  model: {originalSourceRef: string | null};
  modelNdx: number;
  updateModelRef: (modelNdx: number, ref: string | null) => void;
  deleteModel: (modelNdx: number) => void;
  setCurrentlyEditingModelNdx: (
    ndx: number,
    simplifiedConfig?: SimplifiedLLMStructuredCompletionModel
  ) => void;
  modelRefsQuery: ReturnType<typeof useLatestModelRefs>;
  onRegisterSaveHandler: (
    modelNdx: number,
    handler: (() => Promise<string>) | null
  ) => void;
}> = ({
  entity,
  project,
  model,
  modelNdx,
  updateModelRef,
  deleteModel,
  setCurrentlyEditingModelNdx,
  modelRefsQuery,
  onRegisterSaveHandler,
}) => {
  const [canSave, setCanSave] = useState(false);
  const [saveHandler, setSaveHandler] = useState<
    (() => Promise<string>) | null
  >(null);

  const handleRefChange = useCallback(
    (ref: string | null) => {
      updateModelRef(modelNdx, ref);
    },
    [modelNdx, updateModelRef]
  );

  const handleDelete = useCallback(() => {
    deleteModel(modelNdx);
  }, [modelNdx, deleteModel]);

  const handleSaveStateChange = useCallback(
    (canSave: boolean, handler: () => Promise<string>) => {
      setCanSave(canSave);
      setSaveHandler(() => handler);
      // Register/unregister with parent
      onRegisterSaveHandler(modelNdx, canSave ? handler : null);
    },
    [modelNdx, onRegisterSaveHandler]
  );

  // Show loading state for individual dropdowns if query is loading
  if (modelRefsQuery.loading) {
    return (
      <Row style={{alignItems: 'center', gap: '8px'}}>
        <div style={{flex: 1}}>
          <LoadingSelect />
        </div>
        <Button icon="save" variant="primary" size="small" disabled />
        <Button icon="delete" variant="ghost" disabled />
      </Row>
    );
  }

  return (
    <Column
      style={
        {
          // gap: '8px'
        }
      }>
      <Row
        style={{
          alignItems: 'center',
          gap: '8px',
          borderTop: '2px solid ' + MOON_100,
          borderLeft: '2px solid ' + MOON_100,
          borderRight: '2px solid ' + MOON_100,
          borderTopLeftRadius: '4px',
          borderTopRightRadius: '4px',
          padding: '8px',
        }}>
        <div style={{flex: 1}}>
          <VersionedObjectPicker
            entity={entity}
            project={project}
            objectType="model"
            selectedRef={model.originalSourceRef}
            onRefChange={handleRefChange}
            latestObjectRefs={modelRefsQuery.data ?? []}
            loading={modelRefsQuery.loading}
            newOptions={[{label: 'New Model', value: 'new-model'}]}
            allowNewOption={true}
          />
        </div>
        <Button
          icon="save"
          variant="primary"
          size="small"
          onClick={() => saveHandler?.()}
          tooltip="Save model configuration"
          disabled={!(canSave && saveHandler)}
        />
        <Button icon="delete" variant="ghost" onClick={handleDelete} />
      </Row>
      <SimplifiedModelConfig
        entity={entity}
        project={project}
        modelRef={model.originalSourceRef}
        modelNdx={modelNdx}
        onModelSaved={updateModelRef}
        onOpenAdvancedSettings={setCurrentlyEditingModelNdx}
        onSaveStateChange={handleSaveStateChange}
      />
    </Column>
  );
};

/**
 * Configuration section for managing models in the evaluation.
 * Allows users to add, edit, and remove models that will be evaluated.
 */
export interface ModelsConfigSectionRef {
  saveAllUnsaved: () => Promise<void>;
  saveAllUnsavedAndGetRefs: () => Promise<string[]>;
}

export const ModelsConfigSection = React.forwardRef<
  ModelsConfigSectionRef,
  {
    entity: string;
    project: string;
    error?: string;
  }
>(({entity, project, error}, ref) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();
  const modelRefsQuery = useLatestModelRefs(entity, project);

  const [currentlyEditingModelNdx, setCurrentlyEditingModelNdx] = useState<
    number | null
  >(null);

  // Keep track of save handlers for each model
  const saveHandlersRef = useRef<Map<number, () => Promise<string>>>(new Map());

  // Keep track of newly saved refs to avoid stale closure issue
  const newlySavedRefsRef = useRef<Map<number, string>>(new Map());

  const models = useMemo(() => {
    return config.models;
  }, [config]);

  const addModel = useCallback(() => {
    editConfig(draft => {
      draft.models.push({
        originalSourceRef: null,
      });
    });
  }, [editConfig]);

  const modelOptions = useMemo(() => {
    return [
      {
        label: 'Create new model',
        options: [newModelOption],
      },
      {
        label: 'Load existing model',
        options:
          modelRefsQuery.data?.map(ref => ({
            label: refStringToName(ref),
            value: ref,
          })) ?? [],
      },
    ];
  }, [modelRefsQuery.data]);

  const deleteModel = useCallback(
    (modelNdx: number) => {
      editConfig(draft => {
        draft.models.splice(modelNdx, 1);
      });
      // Clean up save handler when deleting
      saveHandlersRef.current.delete(modelNdx);
    },
    [editConfig]
  );

  const registerSaveHandler = useCallback(
    (modelNdx: number, handler: (() => Promise<string>) | null) => {
      if (handler) {
        saveHandlersRef.current.set(modelNdx, handler);
      } else {
        saveHandlersRef.current.delete(modelNdx);
      }
    },
    []
  );

  const updateModelRef = useCallback(
    (modelNdx: number, ref: string | null) => {
      editConfig(draft => {
        if (ref === 'new-model' || ref === null) {
          // Reset to empty model
          draft.models[modelNdx].originalSourceRef = null;
        } else {
          // Set the selected model ref
          draft.models[modelNdx].originalSourceRef = ref;
        }
      });
    },
    [editConfig]
  );

  // Handle opening advanced settings
  const handleOpenAdvancedSettings = useCallback(
    (
      modelNdx: number | null,
      simplifiedConfig?: SimplifiedLLMStructuredCompletionModel
    ) => {
      setCurrentlyEditingModelNdx(modelNdx);
    },
    []
  );

  // Expose method via ref to get current model refs for evaluation
  useImperativeHandle(
    ref,
    () => ({
      saveAllUnsaved: async () => {
        // Save all models that have save handlers
        const savePromises = Array.from(saveHandlersRef.current.entries()).map(
          async ([idx, handler]) => {
            const ref = await handler();
            if (ref) {
              newlySavedRefsRef.current.set(idx, ref);
            }
          }
        );
        await Promise.all(savePromises);
      },
      saveAllUnsavedAndGetRefs: async () => {
        // Clear previous saves
        newlySavedRefsRef.current.clear();

        // Save all unsaved models and capture their refs
        const savePromises = Array.from(saveHandlersRef.current.entries()).map(
          async ([idx, handler]) => {
            const ref = await handler();
            if (ref) {
              newlySavedRefsRef.current.set(idx, ref);
            }
          }
        );
        await Promise.all(savePromises);

        // Build the list of all refs, using newly saved ones where available
        const allRefs: string[] = [];
        models.forEach((model, idx) => {
          const newRef = newlySavedRefsRef.current.get(idx);
          const ref = newRef || model.originalSourceRef;
          if (ref) {
            allRefs.push(ref);
          }
        });

        return allRefs;
      },
    }),
    [models]
  );

  return (
    <ConfigSection
      title="Models"
      icon="model"
      headerAction={
        <Button
          icon="add-new"
          variant="ghost"
          size="small"
          onClick={() => {
            addModel();
          }}>
          Add Model
        </Button>
      }>
      <Column style={{gap: '8px'}}>
        {models.map((model, modelNdx) => {
          let selectedOption = newModelOption;
          const options = [...modelOptions];
          if (model.originalSourceRef) {
            const name = refStringToName(model.originalSourceRef);
            selectedOption = {
              label: name,
              value: model.originalSourceRef,
            };
            // Add current selection if it's not in the list (e.g., from another project)
            const allOptions = options.flatMap(group => group.options);
            if (
              !allOptions.find(opt => opt.value === model.originalSourceRef)
            ) {
              // Add to the existing models group
              options[1].options.unshift(selectedOption);
            }
          }

          return (
            <ModelRow
              key={modelNdx}
              entity={entity}
              project={project}
              model={model}
              modelNdx={modelNdx}
              updateModelRef={updateModelRef}
              deleteModel={deleteModel}
              setCurrentlyEditingModelNdx={handleOpenAdvancedSettings}
              modelRefsQuery={modelRefsQuery}
              onRegisterSaveHandler={registerSaveHandler}
            />
          );
        })}
        <ModelDrawer
          entity={entity}
          project={project}
          open={currentlyEditingModelNdx !== null}
          onClose={newModelRef => {
            if (newModelRef && currentlyEditingModelNdx !== null) {
              editConfig(draft => {
                // Update the model with the new reference
                draft.models[currentlyEditingModelNdx].originalSourceRef =
                  newModelRef;
              });
            }
            setCurrentlyEditingModelNdx(null);
          }}
          initialModelRef={
            currentlyEditingModelNdx !== null
              ? models[currentlyEditingModelNdx].originalSourceRef ?? undefined
              : undefined
          }
        />
      </Column>
    </ConfigSection>
  );
});
