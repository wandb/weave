import {Select} from '@wandb/weave/components/Form/Select';
import {TextArea} from '@wandb/weave/components/Form/TextArea';
import {TextField} from '@wandb/weave/components/Form/TextField';
import React, {useCallback, useMemo} from 'react';

import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {refStringToName} from './common';
import {LoadingSelect} from './components';
import {BORDER_COLOR} from './constants';
import {useEvaluationExplorerPageContext} from './context';
import {DatasetConfigSection} from './DatasetConfigSection';
import {clientBound, hookify} from './hooks';
import {Column} from './layout';
import {ConfigSection, Row} from './layout';
import {getLatestEvaluationRefs, getObjByRef} from './query';
import {ScorersConfigSection} from './ScorersConfigSection';

export const EvaluationConfigSection: React.FC<{
  entity: string;
  project: string;
  setNewDatasetEditorMode: (mode: 'new-empty' | 'new-file') => void;
}> = ({entity, project, setNewDatasetEditorMode}) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();
  return (
    <ConfigSection title="Evaluation" icon="baseline-alt">
      <EvaluationPicker entity={entity} project={project} />
      <Column
        style={{
          flex: 0,
          borderLeft: `1px solid ${BORDER_COLOR}`,
          marginTop: '16px',
        }}>
        <Row style={{padding: '8px 0px 8px 16px'}}>
          <TextField
            value={config.evaluationDefinition.properties.name}
            placeholder="Evaluation Name"
            onChange={value => {
              editConfig(draft => {
                draft.evaluationDefinition.properties.name = value;
                draft.evaluationDefinition.dirtied = true;
              });
            }}
          />
        </Row>
        <Row style={{padding: '8px 0px 16px 16px'}}>
          <TextArea
            value={config.evaluationDefinition.properties.description}
            placeholder="Evaluation Description"
            onChange={e => {
              editConfig(draft => {
                draft.evaluationDefinition.properties.description =
                  e.target.value;
                draft.evaluationDefinition.dirtied = true;
              });
            }}
          />
        </Row>
        <DatasetConfigSection
          entity={entity}
          project={project}
          setNewDatasetEditorMode={setNewDatasetEditorMode}
        />
        <ScorersConfigSection entity={entity} project={project} />
      </Column>
    </ConfigSection>
  );
};

const useLatestEvaluationRefs = clientBound(hookify(getLatestEvaluationRefs));

const EvaluationPicker: React.FC<{entity: string; project: string}> = ({
  entity,
  project,
}) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();
  const refsQuery = useLatestEvaluationRefs(entity, project);
  const getClient = useGetTraceServerClientContext();

  const newEvaluationOption = useMemo(() => {
    return {
      label: 'New Evaluation',
      value: 'new-evaluation',
    };
  }, []);

  const selectOptions = useMemo(() => {
    return [
      {
        label: 'Create new evaluation',
        options: [newEvaluationOption],
      },
      {
        label: 'Load existing evaluation',
        options:
          refsQuery.data?.map(ref => ({
            label: refStringToName(ref),
            value: ref,
          })) ?? [],
      },
    ];
  }, [refsQuery.data, newEvaluationOption]);

  const selectedOption = useMemo(() => {
    if (config.evaluationDefinition.originalSourceRef) {
      return {
        label: refStringToName(config.evaluationDefinition.originalSourceRef),
        value: config.evaluationDefinition.originalSourceRef,
      };
    }
    return newEvaluationOption;
  }, [config.evaluationDefinition.originalSourceRef, newEvaluationOption]);

  const setEvaluationRef = useCallback(
    async (evaluationRef: string | null) => {
      if (evaluationRef === 'new-evaluation' || evaluationRef === null) {
        // Reset to new evaluation
        editConfig(draft => {
          draft.evaluationDefinition.originalSourceRef = null;
          draft.evaluationDefinition.dirtied = false;
          draft.evaluationDefinition.properties.name = '';
          draft.evaluationDefinition.properties.description = '';
          // Clear dataset and scorers
          draft.evaluationDefinition.properties.dataset.originalSourceRef =
            null;
          draft.evaluationDefinition.properties.scorers = [];
          // Clear models
          draft.models = [];
        });
      } else {
        // First set the ref
        editConfig(draft => {
          draft.evaluationDefinition.originalSourceRef = evaluationRef;
          draft.evaluationDefinition.dirtied = false;
        });

        // Then load the evaluation data
        try {
          const client = getClient();
          const evaluationData = await getObjByRef(client, evaluationRef);

          console.log('Loading evaluation data:', evaluationData);

          if (evaluationData) {
            const evalData = evaluationData.val;
            console.log('Evaluation val:', evalData);

            editConfig(draft => {
              // Update evaluation properties from loaded data
              draft.evaluationDefinition.properties.name = evalData.name || '';
              draft.evaluationDefinition.properties.description =
                evalData.description || '';

              // Clear existing dataset and scorers first
              draft.evaluationDefinition.properties.dataset.originalSourceRef =
                null;
              draft.evaluationDefinition.properties.scorers = [];

              // Set dataset ref if it exists - the field is called 'dataset' not 'datasetRef'
              if (evalData.dataset) {
                console.log('Setting dataset ref:', evalData.dataset);
                draft.evaluationDefinition.properties.dataset.originalSourceRef =
                  evalData.dataset;
              }

              // Set scorer refs if they exist - the field is called 'scorers' not 'scorerRefs'
              if (evalData.scorers && Array.isArray(evalData.scorers)) {
                console.log('Setting scorer refs:', evalData.scorers);
                draft.evaluationDefinition.properties.scorers =
                  evalData.scorers.map((ref: string) => ({
                    originalSourceRef: ref,
                  }));
              }
            });
          }
        } catch (error) {
          console.error('Failed to load evaluation:', error);
          // Reset on error
          editConfig(draft => {
            draft.evaluationDefinition.originalSourceRef = null;
          });
        }
      }
    },
    [editConfig, getClient]
  );

  if (refsQuery.loading) {
    return <LoadingSelect />;
  }

  return (
    <Select
      blurInputOnSelect
      options={selectOptions}
      value={selectedOption}
      onChange={option => {
        setEvaluationRef(option?.value ?? null);
      }}
    />
  );
};
