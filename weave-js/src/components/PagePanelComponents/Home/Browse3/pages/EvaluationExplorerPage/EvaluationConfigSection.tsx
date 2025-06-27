import React, {useCallback} from 'react';

import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {useEvaluationExplorerPageContext} from './context';
import {clientBound, hookify} from './hooks';
import {getLatestEvaluationRefs, getObjByRef} from './query';
import {VersionedObjectPicker} from './VersionedObjectPicker';

const useLatestEvaluationRefs = clientBound(hookify(getLatestEvaluationRefs));

export const EvaluationPicker: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  const {config, editConfig} = useEvaluationExplorerPageContext();
  const refsQuery = useLatestEvaluationRefs(entity, project);
  const getClient = useGetTraceServerClientContext();

  const setEvaluationRef = useCallback(
    async (evaluationRef: string | null) => {
      if (evaluationRef === 'new-evaluation' || evaluationRef === null) {
        // Reset to new evaluation
        editConfig(draft => {
          draft.evaluationDefinition.originalSourceRef = null;
          draft.evaluationDefinition.properties.name = '';
          draft.evaluationDefinition.properties.description = '';
          // Clear dataset and scorers
          draft.evaluationDefinition.properties.dataset.originalSourceRef =
            null;
          draft.evaluationDefinition.properties.scorers = [];
          // Clear models
          draft.models = [];
        });
      } else if (
        evaluationRef !== config.evaluationDefinition.originalSourceRef
      ) {
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

              // Update evaluation properties from loaded data
              draft.evaluationDefinition.properties.name = evalData.name || '';
              draft.evaluationDefinition.properties.description =
                evalData.description || '';

              // Clear existing dataset and scorers first
              draft.evaluationDefinition.properties.dataset.originalSourceRef =
                null;
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
      newOptions={[{label: 'New Evaluation', value: 'new-evaluation'}]}
      allowNewOption={true}
    />
  );
};
