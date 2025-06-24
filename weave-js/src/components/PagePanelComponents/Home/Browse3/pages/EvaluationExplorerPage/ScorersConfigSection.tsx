import {Button} from '@wandb/weave/components/Button';
import {Select} from '@wandb/weave/components/Form/Select';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useCallback, useMemo, useRef, useState} from 'react';

import {ReusableDrawer} from '../../ReusableDrawer';
import {ScorerFormRef} from '../MonitorsPage/MonitorFormDrawer';
import {LLMAsAJudgeScorerForm} from '../MonitorsPage/ScorerForms/LLMAsAJudgeScorerForm';
import {ObjectVersionSchema} from '../wfReactInterface/wfDataModelHooksInterface';
import {refStringToName} from './common';
import {useEvaluationExplorerPageContext} from './context';
import {clientBound, hookify} from './hooks';
import {Column, ConfigSection, Row} from './layout';
import {getObjByRef} from './query';

const newScorerOption = {
  label: 'New Scorer',
  value: 'new-scorer',
};

export const ScorersConfigSection: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();

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
    return [newScorerOption];
  }, []);

  const deleteScorer = useCallback(
    (scorerNdx: number) => {
      editConfig(draft => {
        draft.evaluationDefinition.properties.scorers.splice(scorerNdx, 1);
      });
    },
    [editConfig]
  );

  return (
    <ConfigSection
      title="Scorers"
      icon="type-number-alt"
      style={{
        paddingBottom: '0px',
        paddingRight: '0px',
      }}>
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
            options.unshift(selectedOption);
          }
          return (
            <Row key={scorerNdx} style={{alignItems: 'center', gap: '8px'}}>
              <div style={{flex: 1}}>
                <Select
                  options={options}
                  value={selectedOption}
                  onChange={option => {
                    console.log(option);
                    console.error('TODO: Implement me');
                  }}
                />
              </div>
              <Button
                icon="settings"
                variant="ghost"
                onClick={() => {
                  setCurrentlyEditingScorerNdx(scorerNdx);
                }}
              />
              {/* <Button
              icon="copy"
              variant="ghost"
              onClick={() => {
                console.error('TODO: Implement me');
              }}
            /> */}
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
          onClose={newScorerRef => {
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
