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
import {SimplifiedLLMStructuredCompletionModel} from './types';
import {VersionedObjectPicker} from './VersionedObjectPicker';

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
  onSaveModel: (
    modelNdx: number,
    simplifiedConfig: SimplifiedLLMStructuredCompletionModel
  ) => Promise<string | null>;
  onOpenAdvancedSettings: (
    modelNdx: number,
    simplifiedConfig: SimplifiedLLMStructuredCompletionModel
  ) => void;
  onRegisterSave?: (modelNdx: number, saveMethod: () => Promise<void>) => void;
  onUnregisterSave?: (modelNdx: number) => void;
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
  onSaveModel,
  onOpenAdvancedSettings,
  onRegisterSave,
  onUnregisterSave,
}) => {
  // Local state for the simplified form
  const [config, setConfig] = useState<SimplifiedLLMStructuredCompletionModel>({
    name: '',
    llmModelId: '',
    systemPrompt: '',
  });

  const [isSaving, setIsSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  const simplifiedModelQuery = useSimplifiedModel(
    entity,
    project,
    modelRef ?? ''
  );

  // Load existing model configuration when ref changes
  useEffect(() => {
    if (modelRef && simplifiedModelQuery.data !== null) {
      setConfig(simplifiedModelQuery.data);
      setHasUnsavedChanges(false);
    }
  }, [modelRef, simplifiedModelQuery.data]);

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
    if (!isValid || isSaving || !hasUnsavedChanges) return;

    setIsSaving(true);
    try {
      // Save the model with current config
      const newRef = await onSaveModel(modelNdx, config);
      if (newRef) {
        setHasUnsavedChanges(false);
        // TODO: Show success message
        console.log('Model saved with ref:', newRef);
      }
    } finally {
      setIsSaving(false);
    }
  }, [isValid, isSaving, hasUnsavedChanges, onSaveModel, modelNdx, config]);

  // Register save method when this is a new model or has unsaved changes
  useEffect(() => {
    if (!modelRef && onRegisterSave && hasUnsavedChanges && isValid) {
      onRegisterSave(modelNdx, handleSave);
      return () => {
        onUnregisterSave?.(modelNdx);
      };
    }
  }, [
    modelNdx,
    modelRef,
    hasUnsavedChanges,
    isValid,
    handleSave,
    onRegisterSave,
    onUnregisterSave,
  ]);

  // Check if this model qualifies for simplified config
  const qualifies = !modelRef || simplifiedModelQuery.data !== null;

  // Show advanced configuration notice for complex models
  if (!qualifies) {
    return (
      <div
        style={{
          padding: '12px',
          backgroundColor: '#f5f5f5',
          borderRadius: '4px',
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
        backgroundColor: '#f5f5f5',
        borderRadius: '4px',
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
        <div style={{flex: '0 0 140px'}}>
          <LLMDropdownLoaded
            className="w-full"
            hideSavedModels
            value={config.llmModelId || ''}
            isTeamAdmin={false}
            direction={{horizontal: 'left'}}
            onChange={(modelValue: string) => {
              updateConfig({llmModelId: modelValue});
            }}
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
      <Row style={{justifyContent: 'flex-end', gap: '8px'}}>
        <Button
          variant="primary"
          size="small"
          onClick={handleSave}
          icon={isSaving ? undefined : 'save'}
          disabled={!isValid || isSaving}>
          {isSaving ? 'Saving...' : 'Save'}
        </Button>
      </Row>
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
  onSaveModel: (
    modelNdx: number,
    simplifiedConfig: SimplifiedLLMStructuredCompletionModel
  ) => Promise<string | null>;
  onRegisterSave: (modelNdx: number, saveMethod: () => Promise<void>) => void;
  onUnregisterSave: (modelNdx: number) => void;
}> = ({
  entity,
  project,
  model,
  modelNdx,
  updateModelRef,
  deleteModel,
  setCurrentlyEditingModelNdx,
  modelRefsQuery,
  onSaveModel,
  onRegisterSave,
  onUnregisterSave,
}) => {
  const handleRefChange = useCallback(
    (ref: string | null) => {
      updateModelRef(modelNdx, ref);
    },
    [modelNdx, updateModelRef]
  );

  const handleDelete = useCallback(() => {
    deleteModel(modelNdx);
  }, [modelNdx, deleteModel]);

  // Show loading state for individual dropdowns if query is loading
  if (modelRefsQuery.loading) {
    return (
      <Row style={{alignItems: 'center', gap: '8px'}}>
        <div style={{flex: 1}}>
          <LoadingSelect />
        </div>
        <Button icon="delete" variant="ghost" disabled />
      </Row>
    );
  }

  return (
    <Column style={{gap: '8px'}}>
      <Row style={{alignItems: 'center', gap: '8px'}}>
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
        <Button icon="delete" variant="ghost" onClick={handleDelete} />
      </Row>
      <SimplifiedModelConfig
        entity={entity}
        project={project}
        modelRef={model.originalSourceRef}
        modelNdx={modelNdx}
        onSaveModel={onSaveModel}
        onOpenAdvancedSettings={setCurrentlyEditingModelNdx}
        onRegisterSave={onRegisterSave}
        onUnregisterSave={onUnregisterSave}
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

  const models = useMemo(() => {
    return config.models;
  }, [config]);

  const client = useGetTraceServerClientContext()();

  // Keep track of simplified config forms
  const simplifiedConfigRefs = useRef<Map<number, {save: () => Promise<void>}>>(
    new Map()
  );

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
      // Clean up ref
      simplifiedConfigRefs.current.delete(modelNdx);
    },
    [editConfig]
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

  // Save model handler for simplified config
  const saveModel = useCallback(
    async (
      modelNdx: number,
      simplifiedConfig: SimplifiedLLMStructuredCompletionModel
    ): Promise<string | null> => {
      const modelRef = await publishSimplifiedLLMStructuredCompletionModel(
        client,
        entity,
        project,
        simplifiedConfig
      );
      updateModelRef(modelNdx, modelRef);
      return modelRef;
    },
    [client, entity, project, updateModelRef]
  );

  // Handle opening advanced settings
  const handleOpenAdvancedSettings = useCallback(
    (
      modelNdx: number | null,
      simplifiedConfig?: SimplifiedLLMStructuredCompletionModel
    ) => {
      // TODO: In the future, we could pass simplifiedConfig to the drawer
      // to pre-populate the advanced form with current values
      setCurrentlyEditingModelNdx(modelNdx);
    },
    []
  );

  // Expose save all method via ref
  useImperativeHandle(
    ref,
    () => ({
      saveAllUnsaved: async () => {
        const savePromises: Promise<void>[] = [];

        // Save all unsaved simplified configs
        simplifiedConfigRefs.current.forEach(configRef => {
          if (configRef.save) {
            savePromises.push(configRef.save());
          }
        });

        await Promise.all(savePromises);
      },
    }),
    []
  );

  const registerSimplifiedConfigRef = useCallback(
    (modelNdx: number, saveMethod: () => Promise<void>) => {
      simplifiedConfigRefs.current.set(modelNdx, {save: saveMethod});
    },
    []
  );

  const unregisterSimplifiedConfigRef = useCallback((modelNdx: number) => {
    simplifiedConfigRefs.current.delete(modelNdx);
  }, []);

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
              onSaveModel={saveModel}
              onRegisterSave={registerSimplifiedConfigRef}
              onUnregisterSave={unregisterSimplifiedConfigRef}
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
