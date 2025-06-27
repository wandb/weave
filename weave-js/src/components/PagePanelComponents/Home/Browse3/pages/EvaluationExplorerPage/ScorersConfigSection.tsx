import {MOON_100, MOON_200} from '@wandb/weave/common/css/color.styles';
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
  onRegisterSaveHandler: (
    scorerNdx: number,
    handler: (() => Promise<string>) | null
  ) => void;
}> = ({
  entity,
  project,
  scorer,
  scorerNdx,
  updateScorerRef,
  deleteScorer,
  setCurrentlyEditingScorerNdx,
  scorerRefsQuery,
  onRegisterSaveHandler,
}) => {
  const [canSave, setCanSave] = useState(false);
  const [saveHandler, setSaveHandler] = useState<
    (() => Promise<string>) | null
  >(null);

  const handleRefChange = useCallback(
    (ref: string | null) => {
      updateScorerRef(scorerNdx, ref);
    },
    [scorerNdx, updateScorerRef]
  );

  const handleDelete = useCallback(() => {
    deleteScorer(scorerNdx);
  }, [scorerNdx, deleteScorer]);

  const handleSaveStateChange = useCallback(
    (canSave: boolean, handler: () => Promise<string>) => {
      setCanSave(canSave);
      setSaveHandler(() => handler);
      // Register/unregister with parent
      onRegisterSaveHandler(scorerNdx, canSave ? handler : null);
    },
    [scorerNdx, onRegisterSaveHandler]
  );

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
    <Column style={{}}>
      <Row
        style={{
          alignItems: 'center',
          gap: '8px',
          borderTop: `2px solid ${MOON_100}`,
          borderLeft: `2px solid ${MOON_100}`,
          borderRight: `2px solid ${MOON_100}`,
          borderTopLeftRadius: '4px',
          borderTopRightRadius: '4px',
          padding: '8px',
        }}>
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

        <Button
          icon="save"
          variant="primary"
          size="small"
          onClick={() => saveHandler?.()}
          tooltip="Save scorer configuration"
          disabled={!(canSave && saveHandler)}
        />
        <Button icon="delete" variant="ghost" onClick={handleDelete} />
      </Row>
      <SimplifiedScorerConfig
        entity={entity}
        project={project}
        scorerRef={scorer.originalSourceRef}
        scorerNdx={scorerNdx}
        onScorerSaved={updateScorerRef}
        onOpenAdvancedSettings={setCurrentlyEditingScorerNdx}
        onSaveStateChange={handleSaveStateChange}
      />
    </Column>
  );
};

interface SimplifiedScorerConfigProps {
  entity: string;
  project: string;
  scorerRef: string | null;
  scorerNdx: number;
  onScorerSaved: (scorerNdx: number, newRef: string) => void;
  onOpenAdvancedSettings: (
    scorerNdx: number,
    simplifiedConfig: SimplifiedLLMAsAJudgeScorer
  ) => void;
  onSaveStateChange: (
    canSave: boolean,
    saveHandler: () => Promise<string>
  ) => void;
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
  onScorerSaved,
  onOpenAdvancedSettings,
  onSaveStateChange,
}) => {
  const client = useGetTraceServerClientContext()();
  // Local state for the simplified form
  const [config, setConfig] = useState<SimplifiedLLMAsAJudgeScorer>(
    defaultScorerConfigPayload
  );

  const [isSaving, setIsSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(!scorerRef); // New scorers start with unsaved changes
  const [initialLoadComplete, setInitialLoadComplete] = useState(false);

  const simplifiedScorerQuery = useSimplifiedScorer(
    entity,
    project,
    scorerRef ?? ''
  );

  // Load existing scorer configuration when ref changes
  useEffect(() => {
    if (
      scorerRef &&
      simplifiedScorerQuery.data !== null &&
      !simplifiedScorerQuery.loading
    ) {
      setConfig(simplifiedScorerQuery.data);
      setHasUnsavedChanges(false);
      setInitialLoadComplete(true);
    } else if (!scorerRef) {
      // For new scorers, mark as loaded immediately
      setInitialLoadComplete(true);
    }
  }, [scorerRef, simplifiedScorerQuery.data, simplifiedScorerQuery.loading]);

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
    if (!isValid || isSaving) return '';

    setIsSaving(true);
    try {
      // Save the scorer directly
      const scorerRef = await publishSimplifiedLLMAsAJudgeScorer(
        client,
        entity,
        project,
        config
      );

      if (scorerRef) {
        setHasUnsavedChanges(false);
        onScorerSaved(scorerNdx, scorerRef);
        return scorerRef; // Return the ref for the save-all handler
      }
      return '';
    } catch (error) {
      console.error('Failed to save scorer:', error);
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
    scorerNdx,
    onScorerSaved,
  ]);

  // Check if this scorer qualifies for simplified config
  const qualifies = !scorerRef || simplifiedScorerQuery.data !== null;
  const isLoading = scorerRef && simplifiedScorerQuery.loading;

  // For new scorers, if LLM is auto-selected, mark as having unsaved changes
  useEffect(() => {
    if (!scorerRef && config.llmModelId && initialLoadComplete) {
      setHasUnsavedChanges(true);
    }
  }, [scorerRef, config.llmModelId, initialLoadComplete]);

  // Notify parent about save state changes
  useEffect(() => {
    const canSave = hasUnsavedChanges && isValid && !isSaving;
    // Pass the handler directly since it already returns a Promise<string>
    onSaveStateChange(canSave, canSave ? handleSave : (null as any));
  }, [hasUnsavedChanges, isValid, isSaving, handleSave, onSaveStateChange]);

  // Show loading state while checking if scorer qualifies
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
        Loading scorer configuration...
      </div>
    );
  }

  // Show advanced configuration notice for complex scorers
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
        backgroundColor: MOON_100,
        borderBottomLeftRadius: '4px',
        borderBottomRightRadius: '4px',
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
        }}
      />
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

  // Keep track of save handlers for each scorer
  const saveHandlersRef = useRef<Map<number, () => Promise<string>>>(new Map());

  // Keep track of newly saved refs to avoid stale closure issue
  const newlySavedRefsRef = useRef<Map<number, string>>(new Map());

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
      // Clean up save handler when deleting
      saveHandlersRef.current.delete(scorerNdx);
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

  const registerSaveHandler = useCallback(
    (scorerNdx: number, handler: (() => Promise<string>) | null) => {
      if (handler) {
        saveHandlersRef.current.set(scorerNdx, handler);
      } else {
        saveHandlersRef.current.delete(scorerNdx);
      }
    },
    []
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
        // Save all scorers that have save handlers
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

        // Save all unsaved scorers and capture their refs
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
        scorers.forEach((scorer, idx) => {
          const newRef = newlySavedRefsRef.current.get(idx);
          const ref = newRef || scorer.originalSourceRef;
          if (ref) {
            allRefs.push(ref);
          }
        });

        return allRefs;
      },
    }),
    [scorers]
  );

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
              onRegisterSaveHandler={registerSaveHandler}
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
