import {Select} from '@wandb/weave/components/Form/Select';
import {TextArea} from '@wandb/weave/components/Form/TextArea';
import {TextField} from '@wandb/weave/components/Form/TextField';
import React, {useMemo} from 'react';

import {LoadingSelect} from './components';
import {BORDER_COLOR} from './constants';
import {useEvaluationExplorerPageContext} from './context';
import {DatasetConfigSection} from './DatasetConfigSection';
import {clientBound, hookify} from './hooks';
import {Column} from './layout';
import {ConfigSection, Row} from './layout';
import {getLatestEvaluationRefs} from './query';
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
  const refsQuery = useLatestEvaluationRefs(entity, project);
  const newEvaluationOption = useMemo(() => {
    return {
      label: 'New Evaluation',
      value: 'new-evaluation',
    };
  }, []);
  const selectOptions = useMemo(() => {
    return [
      newEvaluationOption,
      ...(refsQuery.data?.map(ref => ({
        label: ref,
      })) ?? []),
    ];
  }, [refsQuery.data, newEvaluationOption]);
  const selectedValue = useMemo(() => {
    return selectOptions[0];
  }, [selectOptions]);

  if (refsQuery.loading) {
    return <LoadingSelect />;
  }

  return (
    <Select
      options={selectOptions}
      value={selectedValue}
      onChange={option => {
        console.log(option);
        console.error('TODO: Implement me');
      }}
    />
  );
};
