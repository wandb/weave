import {Button} from '@wandb/weave/components/Button';
import {Select} from '@wandb/weave/components/Form/Select';
import {TextArea} from '@wandb/weave/components/Form/TextArea';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useCallback, useMemo, useRef, useState} from 'react';

import {ReusableDrawer} from '../../ReusableDrawer';
import {ScorerFormRef} from '../MonitorsPage/MonitorFormDrawer';
import {LLMAsAJudgeScorerForm} from '../MonitorsPage/ScorerForms/LLMAsAJudgeScorerForm';
import {ObjectVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {refStringToName} from './common';
import {LoadingSelect} from './components';
import {useEvaluationExplorerPageContext} from './context';
import {clientBound, hookify} from './hooks';
import {Column, ConfigSection, Row} from './layout';
import {getLatestScorerRefs, getObjByRef} from './query';
import {VersionedObjectPicker} from './VersionedObjectPicker';

const newScorerOption = {
  label: 'New Scorer',
  value: 'new-scorer',
};

// Create the hook for fetching scorer refs
// This wraps the async query function in a React hook that manages loading/error states
const useLatestScorerRefs = clientBound(hookify(getLatestScorerRefs));

// Separate component for each scorer row to properly memoize callbacks
const ScorerRow: React.FC<{
  entity: string;
  project: string;
  scorer: {originalSourceRef: string | null};
  scorerNdx: number;
  updateScorerRef: (scorerNdx: number, ref: string | null) => void;
  deleteScorer: (scorerNdx: number) => void;
  setCurrentlyEditingScorerNdx: (ndx: number, simplifiedConfig?: any) => void;
  scorerRefsQuery: ReturnType<typeof useLatestScorerRefs>;
  onSaveScorer: (
    scorerNdx: number,
    simplifiedConfig?: any
  ) => Promise<string | null>;
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
}) => {
  const handleRefChange = useCallback(
    (ref: string | null) => {
      updateScorerRef(scorerNdx, ref);
    },
    [scorerNdx, updateScorerRef]
  );

  const handleSettings = useCallback(() => {
    setCurrentlyEditingScorerNdx(scorerNdx);
  }, [scorerNdx, setCurrentlyEditingScorerNdx]);

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
        <Button icon="settings" variant="ghost" disabled />
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
        <Button icon="settings" variant="ghost" onClick={handleSettings} />
        <Button icon="delete" variant="ghost" onClick={handleDelete} />
      </Row>
      <SimplifiedScorerConfig
        entity={entity}
        project={project}
        scorerRef={scorer.originalSourceRef}
        scorerNdx={scorerNdx}
        onSaveScorer={onSaveScorer}
        onOpenAdvancedSettings={setCurrentlyEditingScorerNdx}
      />
    </Column>
  );
};

// Stub function to determine if a scorer qualifies for simplified config
// TODO: Fill this out with actual logic
export const scorerQualifiesForSimplifiedConfig = (
  scorerRef: string | null,
  scorerData?: any
): boolean => {
  // New scorers always qualify
  if (scorerRef === null || scorerRef === 'new-scorer') {
    return true;
  }

  // TODO: Add logic to check if existing scorer has simple structure
  // For now, return false for all existing scorers
  return false;
};

// Convert simplified config to full scorer object
export const mapSimplifiedConfigToScorer = (simplifiedConfig: {
  name: string;
  type: 'boolean' | 'number';
  model: string;
  prompt: string;
}): any => {
  // The model will be created/selected in the ModelConfigurationForm
  // For now, we just pass the prompt and let the form handle model creation

  return {
    _type: 'LLMAsAJudgeScorer',
    _class_name: 'LLMAsAJudgeScorer',
    _bases: ['Scorer', 'Object', 'BaseModel'],
    name: simplifiedConfig.name,
    scoring_prompt: simplifiedConfig.prompt,
    // Store the simplified config model choice and type in a special field
    // so ModelConfigurationForm can use it
    _simplifiedConfig: {
      modelChoice: simplifiedConfig.model,
      scoreType: simplifiedConfig.type,
    },
    // Note: name is not part of val, it's handled as objectId in the scorer object
  };
};

interface SimplifiedScorerConfigProps {
  entity: string;
  project: string;
  scorerRef: string | null;
  scorerNdx: number;
  onSaveScorer: (
    scorerNdx: number,
    simplifiedConfig?: any
  ) => Promise<string | null>;
  onOpenAdvancedSettings: (scorerNdx: number, simplifiedConfig?: any) => void;
}

const SimplifiedScorerConfig: React.FC<SimplifiedScorerConfigProps> = ({
  entity,
  project,
  scorerRef,
  scorerNdx,
  onSaveScorer,
  onOpenAdvancedSettings,
}) => {
  // Local state for the simplified form
  const [config, setConfig] = useState({
    name: '',
    type: 'boolean' as 'boolean' | 'number',
    model: 'gpt-4o',
    prompt: '',
  });

  const [isSaving, setIsSaving] = useState(false);

  // Check if this scorer qualifies for simplified config
  const qualifies = scorerQualifiesForSimplifiedConfig(scorerRef);

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

  // Validation
  const isValid = config.name.trim() !== '' && config.prompt.trim() !== '';

  const handleSave = async () => {
    if (!isValid || isSaving) return;

    setIsSaving(true);
    try {
      // Save the scorer with current config
      const newRef = await onSaveScorer(scorerNdx, config);
      if (newRef) {
        // TODO: Show success message
        console.log('Scorer saved with ref:', newRef);
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleOpenAdvanced = () => {
    // Just open the advanced settings drawer (same as gear button)
    // User can save their simplified config first if they want to
    onOpenAdvancedSettings(scorerNdx, config);
  };

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
            onChange={value => setConfig({...config, name: value})}
          />
        </div>
        <div style={{flex: '0 0 120px'}}>
          <Select
            value={{
              label: config.type === 'boolean' ? 'Boolean' : 'Number',
              value: config.type,
            }}
            options={[
              {label: 'Boolean', value: 'boolean'},
              {label: 'Number', value: 'number'},
            ]}
            onChange={option =>
              setConfig({
                ...config,
                type: option?.value as 'boolean' | 'number',
              })
            }
          />
        </div>
        <div style={{flex: '0 0 140px'}}>
          <Select
            value={{label: config.model, value: config.model}}
            options={[
              {label: 'gpt-4o', value: 'gpt-4o'},
              {label: 'gpt-4o-mini', value: 'gpt-4o-mini'},
              {label: 'gpt-3.5-turbo', value: 'gpt-3.5-turbo'},
              {label: 'claude-3-opus', value: 'claude-3-opus'},
              {label: 'claude-3-sonnet', value: 'claude-3-sonnet'},
            ]}
            onChange={option =>
              setConfig({...config, model: option?.value || 'gpt-4o'})
            }
          />
        </div>
      </Row>
      <Row>
        <TextArea
          placeholder="Enter the scoring prompt (e.g., 'Is the response helpful and accurate?')"
          value={config.prompt}
          onChange={e => setConfig({...config, prompt: e.target.value})}
          rows={3}
          style={{width: '100%'}}
        />
      </Row>
      <Row style={{justifyContent: 'flex-end', gap: '8px'}}>
        <Button variant="secondary" size="small" onClick={handleOpenAdvanced}>
          Advanced settings
        </Button>
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

export const ScorersConfigSection: React.FC<{
  entity: string;
  project: string;
  error?: string;
}> = ({entity, project, error}) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();
  const scorerRefsQuery = useLatestScorerRefs(entity, project);

  const [currentlyEditingScorerNdx, setCurrentlyEditingScorerNdx] = useState<
    number | null
  >(null);

  // Track simplified config data to pass to drawer
  const [pendingSimplifiedConfig, setPendingSimplifiedConfig] =
    useState<any>(null);

  const scorers = useMemo(() => {
    return config.evaluationDefinition.properties.scorers;
  }, [config]);

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
          // Only mark as dirty if we're actually changing something
          if (currentRef !== null) {
            draft.evaluationDefinition.dirtied = true;
          }
        } else {
          // Set the selected scorer ref
          draft.evaluationDefinition.properties.scorers[
            scorerNdx
          ].originalSourceRef = ref;
          // Mark as dirty since we're changing
          draft.evaluationDefinition.dirtied = true;
        }
      });
    },
    [editConfig]
  );

  // Save scorer handler for simplified config
  const saveScorer = useCallback(
    async (
      scorerNdx: number,
      simplifiedConfig?: any
    ): Promise<string | null> => {
      // TODO: Implement actual save logic
      // This should:
      // 1. Use the simplifiedConfig passed from the component
      // 2. Convert it to a full scorer object using mapSimplifiedConfigToScorer
      // 3. Save it to Weave
      // 4. Update the scorer ref
      console.log('Saving scorer', scorerNdx, simplifiedConfig);

      if (simplifiedConfig) {
        // TODO: Convert simplified config to full scorer object
        const scorerObject = mapSimplifiedConfigToScorer(simplifiedConfig);

        // TODO: Save to Weave and get ref
        // const newRef = await saveToWeave(scorerObject);
        // updateScorerRef(scorerNdx, newRef);
        // return newRef;
      }

      // For now, return null as placeholder
      return null;
    },
    []
  );

  // Handle opening advanced settings (either from gear or from simplified form)
  const handleOpenAdvancedSettings = useCallback(
    (scorerNdx: number | null, simplifiedConfig?: any) => {
      if (simplifiedConfig) {
        // Store the simplified config to pass to the drawer
        setPendingSimplifiedConfig(simplifiedConfig);
      }
      setCurrentlyEditingScorerNdx(scorerNdx);
    },
    []
  );

  return (
    <ConfigSection title="Scorers" icon="type-number-alt" error={error}>
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
            />
          );
        })}
        <Row>
          <Button
            icon="add-new"
            variant="ghost"
            onClick={() => {
              addScorer();
            }}
          />
        </Row>
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
};

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

const ScorerDrawer: React.FC<{
  entity: string;
  project: string;
  open: boolean;
  onClose: (newScorerRef?: string) => void;
  initialScorerRef?: string;
  pendingSimplifiedConfig?: any;
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
    if (pendingSimplifiedConfig) {
      const mappedConfig = mapSimplifiedConfigToScorer(pendingSimplifiedConfig);
      // Merge the mapped config into the base scorer
      return {
        ...baseScorer,
        objectId: pendingSimplifiedConfig.name || baseScorer.objectId, // Set the name as objectId
        val: {
          ...baseScorer.val,
          ...mappedConfig,
        },
      };
    }

    return baseScorer;
  }, [
    entity,
    initialScorerRef,
    project,
    scorerQuery.data,
    pendingSimplifiedConfig,
  ]);

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
