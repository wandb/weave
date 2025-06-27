import {Button} from '@wandb/weave/components/Button';
import {Select} from '@wandb/weave/components/Form/Select';
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
import {ScorerFormRef} from '../MonitorsPage/MonitorFormDrawer';
import {LLMAsAJudgeScorerForm} from '../MonitorsPage/ScorerForms/LLMAsAJudgeScorerForm';
import {LLMDropdownLoaded} from '../PlaygroundPage/PlaygroundChat/LLMDropdown';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {ObjectVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {refStringToName} from './common';
import {LoadingSelect} from './components';
import {useEvaluationExplorerPageContext} from './context';
import {clientBound, hookify} from './hooks';
import {Column, ConfigSection, Row} from './layout';
import {
  getLatestScorerRefs,
  getObjByRef,
  getSimplifiedLLMAsAJudgeScorer,
  publishSimplifiedLLMAsAJudgeScorer,
} from './query';
import {defaultScorerConfigPayload} from './state';
import {SimplifiedLLMAsAJudgeScorer} from './types';
import {VersionedObjectPicker} from './VersionedObjectPicker';

// Helper to get valid refs from items
const getValidRefs = <T extends {originalSourceRef: string | null}>(
  items: T[]
): string[] => {
  return items
    .filter(item => item.originalSourceRef !== null)
    .map(item => item.originalSourceRef!);
};

const newScorerOption = {
  label: 'New Scorer',
  value: 'new-scorer',
};

// Create the hook for fetching scorer refs
// This wraps the async query function in a React hook that manages loading/error states
const useLatestScorerRefs = clientBound(hookify(getLatestScorerRefs));
const useSimplifiedScorer = clientBound(
  hookify(getSimplifiedLLMAsAJudgeScorer)
);

// Separate component for each scorer row to properly memoize callbacks
const ScorerRow: React.FC<{
  entity: string;
  project: string;
  scorer: {originalSourceRef: string | null};
  scorerNdx: number;
  updateScorerRef: (scorerNdx: number, ref: string | null) => void;
  deleteScorer: (scorerNdx: number) => void;
  setCurrentlyEditingScorerNdx: (
    ndx: number,
    simplifiedConfig?: SimplifiedLLMAsAJudgeScorer
  ) => void;
  scorerRefsQuery: ReturnType<typeof useLatestScorerRefs>;
  onSaveScorer: (
    scorerNdx: number,
    simplifiedConfig: SimplifiedLLMAsAJudgeScorer
  ) => Promise<string | null>;
  onRegisterSave: (scorerNdx: number, saveMethod: () => Promise<void>) => void;
  onUnregisterSave: (scorerNdx: number) => void;
}> = ({
  entity,
  project,
  scorer,
  scorerNdx,
  updateScorerRef,
  deleteScorer,
  setCurrentlyEditingScorerNdx,
  scorerRefsQuery,
  onSaveScorer,
  onRegisterSave,
  onUnregisterSave,
}) => {
  const handleRefChange = useCallback(
    (ref: string | null) => {
      updateScorerRef(scorerNdx, ref);
    },
    [scorerNdx, updateScorerRef]
  );

  const handleDelete = useCallback(() => {
    deleteScorer(scorerNdx);
  }, [scorerNdx, deleteScorer]);

  // Show loading state for individual dropdowns if query is loading
  if (scorerRefsQuery.loading) {
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
            objectType="scorer"
            selectedRef={scorer.originalSourceRef}
            onRefChange={handleRefChange}
            latestObjectRefs={scorerRefsQuery.data ?? []}
            loading={scorerRefsQuery.loading}
            newOptions={[{label: 'New Scorer', value: 'new-scorer'}]}
            allowNewOption={true}
          />
        </div>
        <Button icon="delete" variant="ghost" onClick={handleDelete} />
      </Row>
      <SimplifiedScorerConfig
        entity={entity}
        project={project}
        scorerRef={scorer.originalSourceRef}
        scorerNdx={scorerNdx}
        onSaveScorer={onSaveScorer}
        onOpenAdvancedSettings={setCurrentlyEditingScorerNdx}
        onRegisterSave={onRegisterSave}
        onUnregisterSave={onUnregisterSave}
      />
    </Column>
  );
};

interface SimplifiedScorerConfigProps {
  entity: string;
  project: string;
  scorerRef: string | null;
  scorerNdx: number;
  onSaveScorer: (
    scorerNdx: number,
    simplifiedConfig: SimplifiedLLMAsAJudgeScorer
  ) => Promise<string | null>;
  onOpenAdvancedSettings: (
    scorerNdx: number,
    simplifiedConfig: SimplifiedLLMAsAJudgeScorer
  ) => void;
  onRegisterSave?: (scorerNdx: number, saveMethod: () => Promise<void>) => void;
  onUnregisterSave?: (scorerNdx: number) => void;
}

/**
 * Simplified scorer configuration form for basic LLM-as-a-Judge scorers.
 * Provides an inline form for scorers that don't require advanced configuration.
 */
const SimplifiedScorerConfig: React.FC<SimplifiedScorerConfigProps> = ({
  entity,
  project,
  scorerRef,
  scorerNdx,
  onSaveScorer,
  onOpenAdvancedSettings,
  onRegisterSave,
  onUnregisterSave,
}) => {
  // Local state for the simplified form
  const [config, setConfig] = useState<SimplifiedLLMAsAJudgeScorer>(
    defaultScorerConfigPayload
  );

  const [isSaving, setIsSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(!scorerRef); // New scorers start with unsaved changes

  const simplifiedScorerQuery = useSimplifiedScorer(
    entity,
    project,
    scorerRef ?? ''
  );

  // Load existing scorer configuration when ref changes
  useEffect(() => {
    if (scorerRef && simplifiedScorerQuery.data !== null) {
      setConfig(simplifiedScorerQuery.data);
      setHasUnsavedChanges(false);
    }
  }, [scorerRef, simplifiedScorerQuery.data]);

  // Track unsaved changes
  const updateConfig = useCallback(
    (updates: Partial<SimplifiedLLMAsAJudgeScorer>) => {
      setConfig(prev => ({...prev, ...updates}));
      setHasUnsavedChanges(true);
    },
    []
  );

  // Validation: name and prompt are required, LLM is automatically selected
  const isValid =
    config.name.trim() !== '' &&
    config.prompt.trim() !== '' &&
    config.llmModelId.trim() !== '';

  const handleSave = useCallback(async () => {
    if (!isValid || isSaving || !hasUnsavedChanges) return;

    setIsSaving(true);
    try {
      // Save the scorer with current config
      const newRef = await onSaveScorer(scorerNdx, config);
      if (newRef) {
        setHasUnsavedChanges(false);
        // TODO: Show success message
        console.log('Scorer saved with ref:', newRef);
      }
    } finally {
      setIsSaving(false);
    }
  }, [isValid, isSaving, hasUnsavedChanges, onSaveScorer, scorerNdx, config]);

  // Register save method when this is a new scorer or has unsaved changes
  useEffect(() => {
    if (!scorerRef && onRegisterSave && hasUnsavedChanges && isValid) {
      onRegisterSave(scorerNdx, handleSave);
      return () => {
        onUnregisterSave?.(scorerNdx);
      };
    }
  }, [
    scorerNdx,
    scorerRef,
    hasUnsavedChanges,
    isValid,
    handleSave,
    onRegisterSave,
    onUnregisterSave,
    config.llmModelId, // Re-evaluate when LLM is selected
  ]);

  // Check if this scorer qualifies for simplified config
  const qualifies = !scorerRef || simplifiedScorerQuery.data !== null;

  // Show advanced configuration notice for complex scorers
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
        This scorer uses advanced configuration.{' '}
        <Button
          variant="ghost"
          size="small"
          onClick={() => onOpenAdvancedSettings(scorerNdx, config)}
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
            placeholder="Scorer name"
            value={config.name}
            onChange={value => updateConfig({name: value})}
          />
        </div>
        <div style={{flex: '0 0 120px'}}>
          <Select
            value={{
              label: config.scoreType === 'boolean' ? 'Boolean' : 'Number',
              value: config.scoreType,
            }}
            options={[
              {label: 'Boolean', value: 'boolean'},
              {label: 'Number', value: 'number'},
            ]}
            onChange={option =>
              updateConfig({
                scoreType: option?.value as 'boolean' | 'number',
              })
            }
          />
        </div>
      </Row>
      <Row>
        <TextArea
          placeholder="Enter the scoring prompt (e.g., 'Is the response helpful and accurate?')"
          value={config.prompt}
          onChange={e => updateConfig({prompt: e.target.value})}
          rows={10}
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
          // For new scorers, ensure we maintain unsaved state when auto-selecting
          if (!scorerRef && !hasUnsavedChanges) {
            setHasUnsavedChanges(true);
          }
        }}
      />
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
 * Main scorer configuration section component.
 * Manages the list of scorers with simplified inline configuration
 * and advanced configuration drawer for complex scorers.
 */
export interface ScorersConfigSectionRef {
  saveAllUnsaved: () => Promise<void>;
  saveAllUnsavedAndGetRefs: () => Promise<string[]>;
}

export const ScorersConfigSection = React.forwardRef<
  ScorersConfigSectionRef,
  {
    entity: string;
    project: string;
    error?: string;
  }
>(({entity, project, error}, ref) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();
  const scorerRefsQuery = useLatestScorerRefs(entity, project);

  const [currentlyEditingScorerNdx, setCurrentlyEditingScorerNdx] = useState<
    number | null
  >(null);

  // Track simplified config data to pass to drawer
  const [pendingSimplifiedConfig, setPendingSimplifiedConfig] =
    useState<SimplifiedLLMAsAJudgeScorer | null>(null);

  const scorers = useMemo(() => {
    return config.evaluationDefinition.properties.scorers;
  }, [config]);

  // Keep track of simplified config forms
  const simplifiedConfigRefs = useRef<Map<number, {save: () => Promise<void>}>>(
    new Map()
  );
  
  // Keep track of newly saved refs
  const newlySavedRefs = useRef<Map<number, string>>(new Map());

  const addScorer = useCallback(() => {
    editConfig(draft => {
      draft.evaluationDefinition.properties.scorers.push({
        originalSourceRef: null,
      });
    });
  }, [editConfig]);

  const scorerOptions = useMemo(() => {
    return [
      {
        label: 'Create new scorer',
        options: [newScorerOption],
      },
      {
        label: 'Load existing scorer',
        options:
          scorerRefsQuery.data?.map(ref => ({
            label: refStringToName(ref),
            value: ref,
          })) ?? [],
      },
    ];
  }, [scorerRefsQuery.data]);

  const deleteScorer = useCallback(
    (scorerNdx: number) => {
      editConfig(draft => {
        draft.evaluationDefinition.properties.scorers.splice(scorerNdx, 1);
      });
      // Clean up refs
      simplifiedConfigRefs.current.delete(scorerNdx);
      newlySavedRefs.current.delete(scorerNdx);
    },
    [editConfig]
  );

  const updateScorerRef = useCallback(
    (scorerNdx: number, ref: string | null) => {
      editConfig(draft => {
        // Don't update if the ref hasn't changed
        const currentRef =
          draft.evaluationDefinition.properties.scorers[scorerNdx]
            ?.originalSourceRef;
        if (ref === currentRef) {
          return;
        }

        if (ref === 'new-scorer' || ref === null) {
          // Reset to empty scorer
          draft.evaluationDefinition.properties.scorers[
            scorerNdx
          ].originalSourceRef = null;
        } else {
          // Set the selected scorer ref
          draft.evaluationDefinition.properties.scorers[
            scorerNdx
          ].originalSourceRef = ref;
        }
      });
    },
    [editConfig]
  );

  const client = useGetTraceServerClientContext()();

  // Save scorer handler for simplified config
  const saveScorer = useCallback(
    async (
      scorerNdx: number,
      simplifiedConfig: SimplifiedLLMAsAJudgeScorer
    ): Promise<string | null> => {
      const scorerRef = await publishSimplifiedLLMAsAJudgeScorer(
        client,
        entity,
        project,
        simplifiedConfig
      );
      // Store the newly saved ref
      if (scorerRef) {
        newlySavedRefs.current.set(scorerNdx, scorerRef);
      }
      updateScorerRef(scorerNdx, scorerRef);
      return scorerRef;
    },
    [client, entity, project, updateScorerRef]
  );

  // Handle opening advanced settings (either from gear or from simplified form)
  const handleOpenAdvancedSettings = useCallback(
    (
      scorerNdx: number | null,
      simplifiedConfig?: SimplifiedLLMAsAJudgeScorer
    ) => {
      if (simplifiedConfig) {
        // Store the simplified config to pass to the drawer
        setPendingSimplifiedConfig(simplifiedConfig);
      }
      setCurrentlyEditingScorerNdx(scorerNdx);
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
      saveAllUnsavedAndGetRefs: async () => {
        // First, wait for any pending saves
        const savePromises: Promise<void>[] = [];
        simplifiedConfigRefs.current.forEach(configRef => {
          if (configRef.save) {
            savePromises.push(configRef.save());
          }
        });
        await Promise.all(savePromises);
        
        // Wait a tick for React to process state updates
        await new Promise(resolve => setTimeout(resolve, 10));
        
        // Now get the latest config state by re-evaluating
        const latestScorers = config.evaluationDefinition.properties.scorers;
        
        // Collect all scorer refs, including newly saved ones
        const allRefs: string[] = [];
        latestScorers.forEach((scorer, idx) => {
          const newRef = newlySavedRefs.current.get(idx);
          const ref = newRef || scorer.originalSourceRef;
          if (ref) {
            allRefs.push(ref);
          }
        });
        
        console.log('Collected scorer refs:', allRefs);
        console.log('Newly saved refs map:', Array.from(newlySavedRefs.current.entries()));
        
        // Clear the newly saved refs for next time
        newlySavedRefs.current.clear();
        
        return allRefs;
      },
    }),
    [scorers, config]
  );

  const registerSimplifiedConfigRef = useCallback(
    (scorerNdx: number, saveMethod: () => Promise<void>) => {
      simplifiedConfigRefs.current.set(scorerNdx, {save: saveMethod});
    },
    []
  );

  const unregisterSimplifiedConfigRef = useCallback((scorerNdx: number) => {
    simplifiedConfigRefs.current.delete(scorerNdx);
  }, []);

  return (
    <ConfigSection
      title="Scorers"
      icon="type-number-alt"
      headerAction={
        <Button
          icon="add-new"
          variant="ghost"
          size="small"
          onClick={() => {
            addScorer();
          }}>
          Add Scorer
        </Button>
      }>
      <Column style={{gap: '8px'}}>
        {scorers.map((scorer, scorerNdx) => {
          let selectedOption = newScorerOption;
          const options = [...scorerOptions];
          if (scorer.originalSourceRef) {
            const name = refStringToName(scorer.originalSourceRef);
            selectedOption = {
              label: name,
              value: scorer.originalSourceRef,
            };
            // Add current selection if it's not in the list (e.g., from another project)
            const allOptions = options.flatMap(group => group.options);
            if (
              !allOptions.find(opt => opt.value === scorer.originalSourceRef)
            ) {
              // Add to the existing scorers group
              options[1].options.unshift(selectedOption);
            }
          }

          return (
            <ScorerRow
              key={scorerNdx}
              entity={entity}
              project={project}
              scorer={scorer}
              scorerNdx={scorerNdx}
              updateScorerRef={updateScorerRef}
              deleteScorer={deleteScorer}
              setCurrentlyEditingScorerNdx={handleOpenAdvancedSettings}
              scorerRefsQuery={scorerRefsQuery}
              onSaveScorer={saveScorer}
              onRegisterSave={registerSimplifiedConfigRef}
              onUnregisterSave={unregisterSimplifiedConfigRef}
            />
          );
        })}
        <ScorerDrawer
          entity={entity}
          project={project}
          open={currentlyEditingScorerNdx !== null}
          onClose={(newScorerRef?: string) => {
            if (newScorerRef && currentlyEditingScorerNdx !== null) {
              editConfig(draft => {
                draft.evaluationDefinition.properties.scorers[
                  currentlyEditingScorerNdx
                ].originalSourceRef = newScorerRef;
              });
            }
            setCurrentlyEditingScorerNdx(null);
            setPendingSimplifiedConfig(null); // Clear pending config
          }}
          initialScorerRef={
            currentlyEditingScorerNdx !== null
              ? scorers[currentlyEditingScorerNdx]?.originalSourceRef ??
                undefined
              : undefined
          }
          pendingSimplifiedConfig={pendingSimplifiedConfig}
        />
      </Column>
    </ConfigSection>
  );
});

const emptyScorer = (entity: string, project: string): ObjectVersionSchema => ({
  scheme: 'weave',
  weaveKind: 'object',
  entity,
  project,
  objectId: '',
  versionHash: '',
  path: '',
  versionIndex: 0,
  baseObjectClass: 'LLMAsAJudgeScorer',
  createdAtMs: Date.now(),
  val: {_type: 'LLMAsAJudgeScorer'},
});

const useScorer = clientBound(hookify(getObjByRef));

/**
 * Drawer component for advanced scorer configuration.
 * Opened when a scorer requires configuration beyond the simplified form.
 */
const ScorerDrawer: React.FC<{
  entity: string;
  project: string;
  open: boolean;
  onClose: (newScorerRef?: string) => void;
  initialScorerRef?: string;
  pendingSimplifiedConfig?: SimplifiedLLMAsAJudgeScorer | null;
}> = ({
  entity,
  project,
  open,
  onClose,
  initialScorerRef,
  pendingSimplifiedConfig,
}) => {
  const scorerFormRef = useRef<ScorerFormRef | null>(null);
  const onSave = useCallback(async () => {
    const newScorerRef = await scorerFormRef.current?.saveScorer();
    onClose(newScorerRef);
  }, [onClose]);

  const scorerQuery = useScorer(initialScorerRef);

  const scorerObj = useMemo(() => {
    let baseScorer;
    if (initialScorerRef) {
      baseScorer = scorerQuery.data ?? emptyScorer(entity, project);
    } else {
      baseScorer = emptyScorer(entity, project);
    }

    // If we have pendingSimplifiedConfig, merge it into the scorer object
    // if (pendingSimplifiedConfig) {
    //   const mappedConfig = mapSimplifiedConfigToScorer(pendingSimplifiedConfig);
    //   console.log('mappedConfig', mappedConfig);
    //   // Merge the mapped config into the base scorer
    //   return {
    //     ...baseScorer,
    //     objectId:
    //       sanitizeObjectId(pendingSimplifiedConfig.name) || baseScorer.objectId, // Set the name as objectId
    //     val: {
    //       ...baseScorer.val,
    //       ...mappedConfig,
    //     },
    //   };
    // }

    return baseScorer;
  }, [entity, initialScorerRef, project, scorerQuery.data]);

  if (scorerQuery.loading) {
    // TODO: Show a loading indicator
    return null;
  }

  if (scorerQuery.error) {
    // TODO: Show a loading indicator
    return null;
  }

  return (
    <ReusableDrawer
      open={open}
      onClose={() => onClose()}
      title="Scorer Configuration"
      onSave={onSave}>
      <Tailwind>
        <LLMAsAJudgeScorerForm
          key={`${initialScorerRef || 'new'}-${JSON.stringify(
            pendingSimplifiedConfig
          )}`}
          ref={scorerFormRef}
          scorer={scorerObj}
          onValidationChange={() => {
            // Pass
          }}
        />
      </Tailwind>
    </ReusableDrawer>
  );
};
