import {Button} from '@wandb/weave/components/Button';
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

          // Show loading state for individual dropdowns if query is loading
          if (scorerRefsQuery.loading) {
            return (
              <Row key={scorerNdx} style={{alignItems: 'center', gap: '8px'}}>
                <div style={{flex: 1}}>
                  <LoadingSelect />
                </div>
                <Button icon="settings" variant="ghost" disabled />
                <Button icon="delete" variant="ghost" disabled />
              </Row>
            );
          }

          return (
            <Row key={scorerNdx} style={{alignItems: 'center', gap: '8px'}}>
              <div style={{flex: 1}}>
                <VersionedObjectPicker
                  entity={entity}
                  project={project}
                  objectType="scorer"
                  selectedRef={scorer.originalSourceRef}
                  onRefChange={ref => {
                    updateScorerRef(scorerNdx, ref);
                  }}
                  latestObjectRefs={scorerRefsQuery.data ?? []}
                  loading={scorerRefsQuery.loading}
                  newOptions={[{label: 'New Scorer', value: 'new-scorer'}]}
                  allowNewOption={true}
                />
              </div>
              <Button
                icon="settings"
                variant="ghost"
                onClick={() => {
                  setCurrentlyEditingScorerNdx(scorerNdx);
                }}
              />
              <Button
                icon="delete"
                variant="ghost"
                onClick={() => {
                  deleteScorer(scorerNdx);
                }}
              />
            </Row>
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
          }}
          initialScorerRef={
            currentlyEditingScorerNdx !== null
              ? scorers[currentlyEditingScorerNdx]?.originalSourceRef ??
                undefined
              : undefined
          }
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
}> = ({entity, project, open, onClose, initialScorerRef}) => {
  const scorerFormRef = useRef<ScorerFormRef | null>(null);
  const onSave = useCallback(async () => {
    const newScorerRef = await scorerFormRef.current?.saveScorer();
    onClose(newScorerRef);
  }, [onClose]);

  const scorerQuery = useScorer(initialScorerRef);

  const scorerObj = useMemo(() => {
    if (initialScorerRef) {
      return scorerQuery.data ?? emptyScorer(entity, project);
    } else {
      return emptyScorer(entity, project);
    }
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
          key={initialScorerRef}
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
