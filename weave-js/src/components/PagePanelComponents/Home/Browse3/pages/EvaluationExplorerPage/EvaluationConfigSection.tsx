import {Select} from '@wandb/weave/components/Form/Select';
import {TextArea} from '@wandb/weave/components/Form/TextArea';
import {TextField} from '@wandb/weave/components/Form/TextField';
import React, {useCallback, useEffect, useMemo} from 'react';

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
import {VersionedObjectPicker} from './VersionedObjectPicker';

export const EvaluationConfigSection: React.FC<{
  entity: string;
  project: string;
  setNewDatasetEditorMode: (mode: 'new-empty' | 'new-file') => void;
}> = ({entity, project, setNewDatasetEditorMode}) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();
  return (
    <ConfigSection title="Evaluation" icon="baseline-alt">
      <Column
        style={{
          flex: 0,
        }}>
        <Row style={{paddingBottom: '8px'}}>
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
        <Row style={{paddingBottom: '16px'}}>
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
const useEvaluationByRef = clientBound(hookify(getObjByRef));

export const EvaluationPicker: React.FC<{
  entity: string; 
  project: string;
}> = ({
  entity,
  project,
}) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();
  const refsQuery = useLatestEvaluationRefs(entity, project);
  const getClient = useGetTraceServerClientContext();
  
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
          draft.evaluationDefinition.properties.dataset.originalSourceRef = null;
          draft.evaluationDefinition.properties.scorers = [];
          // Clear models
          draft.models = [];
        });
      } else if (evaluationRef !== config.evaluationDefinition.originalSourceRef) {
        // Only update if the ref actually changed
        try {
          const client = getClient();
          const evaluationData = await getObjByRef(client, evaluationRef);
          
          if (evaluationData) {
            const evalData = evaluationData.val;
            
            // Batch all updates into a single editConfig call
            editConfig(draft => {
              // Set the ref
              draft.evaluationDefinition.originalSourceRef = evaluationRef;
              draft.evaluationDefinition.dirtied = false;
              
              // Update evaluation properties from loaded data
              draft.evaluationDefinition.properties.name = evalData.name || '';
              draft.evaluationDefinition.properties.description =
                evalData.description || '';

              // Clear existing dataset and scorers first
              draft.evaluationDefinition.properties.dataset.originalSourceRef = null;
              draft.evaluationDefinition.properties.scorers = [];
              
              // Set dataset ref if it exists
              if (evalData.dataset) {
                draft.evaluationDefinition.properties.dataset.originalSourceRef =
                  evalData.dataset;
              }
              
              // Set scorer refs if they exist
              if (evalData.scorers && Array.isArray(evalData.scorers)) {
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
    [editConfig, getClient, config.evaluationDefinition.originalSourceRef]
  );

  return (
    <VersionedObjectPicker
      entity={entity}
      project={project}
      objectType="evaluation"
      selectedRef={config.evaluationDefinition.originalSourceRef}
      onRefChange={setEvaluationRef}
      latestObjectRefs={refsQuery.data ?? []}
      loading={refsQuery.loading}
      newOptions={[{label: "New Evaluation", value: "new-evaluation"}]}
      allowNewOption={true}
    />
  );
};
