import {Box} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button/Button';
import {Checkbox} from '@wandb/weave/components/Checkbox/Checkbox';
import {Select} from '@wandb/weave/components/Form/Select';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {refUri} from '@wandb/weave/react';
import React, {useEffect, useMemo, useState} from 'react';

import {flattenObjectPreservingWeaveTypes} from '../../../Browse2/browse2Util';
import {parseRefMaybe} from '../../../Browse2/SmallRef';
import {
  ALL_VALUE,
  LeaderboardObjectVal,
} from '../../views/Leaderboard/types/leaderboardConfigType';
import {EVALUATE_OP_NAME_POST_PYDANTIC} from '../common/heuristics';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {TraceObjSchema} from '../wfReactInterface/traceServerClientTypes';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {opVersionKeyToRefUri} from '../wfReactInterface/utilities';
import {SimpleCodeLikeTextArea} from './SimpleCodeLikeTextArea';

export const LeaderboardConfigEditor: React.FC<{
  entity: string;
  project: string;
  leaderboardVal: LeaderboardObjectVal;
  saving: boolean;
  isDirty: boolean;
  setWorkingCopy: (leaderboardVal: LeaderboardObjectVal) => void;
  discardChanges: () => void;
  commitChanges: () => void;
}> = ({
  entity,
  project,
  leaderboardVal,
  saving,
  isDirty,
  setWorkingCopy,
  discardChanges,
  commitChanges,
}) => {
  const handleNameChange = (value: string) => {
    setWorkingCopy({...leaderboardVal, name: value});
  };

  const handleDescriptionChange = (value: string) => {
    setWorkingCopy({...leaderboardVal, description: value});
  };

  const handleColumnChange = (index: number, field: string, value: any) => {
    const newColumns = [...leaderboardVal.columns];
    newColumns[index] = {...newColumns[index], [field]: value};

    // Reset dependent fields when changing evaluation_object_ref or scorer_name
    if (field === 'evaluation_object_ref') {
      newColumns[index].scorer_name = '';
      newColumns[index].summary_metric_path_parts = [];
    } else if (field === 'scorer_name') {
      newColumns[index].summary_metric_path_parts = [];
    }

    setWorkingCopy({...leaderboardVal, columns: newColumns});
  };

  const addColumn = () => {
    setWorkingCopy({
      ...leaderboardVal,
      columns: [
        ...leaderboardVal.columns,
        {
          evaluation_object_ref: '',
          scorer_name: '',
          should_minimize: false,
          summary_metric_path_parts: [],
        },
      ],
    });
  };

  const removeColumn = (index: number) => {
    const newColumns = leaderboardVal.columns.filter((_, i) => i !== index);
    setWorkingCopy({...leaderboardVal, columns: newColumns});
  };

  const cloneColumn = (index: number) => {
    const newColumns = [...leaderboardVal.columns];
    newColumns.splice(index + 1, 0, {...newColumns[index]});
    setWorkingCopy({...leaderboardVal, columns: newColumns});
  };

  const moveColumn = (fromIndex: number, toIndex: number) => {
    const newColumns = [...leaderboardVal.columns];
    const [removed] = newColumns.splice(fromIndex, 1);
    newColumns.splice(toIndex, 0, removed);
    setWorkingCopy({...leaderboardVal, columns: newColumns});
  };

  const evalObjs = useEvaluationObjects(entity, project);

  return (
    <Box display="flex" flexDirection="column" height="100%" width="100%">
      <Box
        flexGrow={1}
        overflow="auto"
        sx={{
          mr: 4,
          ml: 4,
          mb: 2,
          paddingLeft: 2,
          paddingRight: 2,
        }}>
        <Label>Leaderboard Title</Label>
        <TextField
          icon="layout-grid"
          value={leaderboardVal.name}
          onChange={handleNameChange}
        />
        <Label>Description</Label>
        <SimpleCodeLikeTextArea
          value={leaderboardVal.description}
          onChange={handleDescriptionChange}
        />
        <Label>Columns</Label>
        {leaderboardVal.columns.map((column, index) => (
          <ColumnEditor
            key={index}
            column={column}
            index={index}
            evalObjs={evalObjs}
            entity={entity}
            project={project}
            handleColumnChange={handleColumnChange}
            moveColumn={moveColumn}
            cloneColumn={cloneColumn}
            removeColumn={removeColumn}
            totalColumns={leaderboardVal.columns.length}
          />
        ))}
        <Button icon="add-new" variant="ghost" onClick={addColumn}>
          Add Column
        </Button>
      </Box>
      <Box
        flexShrink={0}
        p={2}
        borderTop={1}
        borderColor="divider"
        height="52px"
        display="flex"
        alignItems="center"
        justifyContent="flex-end">
        <Button
          variant="ghost"
          onClick={discardChanges}
          disabled={saving}
          style={{marginRight: 8}}>
          {isDirty ? 'Discard' : 'Close'}
        </Button>
        <Button onClick={commitChanges} disabled={!isDirty || saving}>
          {saving ? 'Saving...' : isDirty ? 'Save' : 'Saved'}
        </Button>
      </Box>
    </Box>
  );
};

const Label: React.FC<{children: React.ReactNode}> = ({children}) => {
  return (
    <Box sx={{fontSize: '14px', fontWeight: 'bold', mb: 1, mt: 3}}>
      {children}
    </Box>
  );
};

const ColumnEditor: React.FC<{
  column: LeaderboardObjectVal['columns'][0];
  index: number;
  evalObjs: EvaluationHelperObj[];
  entity: string;
  project: string;
  handleColumnChange: (index: number, field: string, value: any) => void;
  moveColumn: (fromIndex: number, toIndex: number) => void;
  cloneColumn: (index: number) => void;
  removeColumn: (index: number) => void;
  totalColumns: number;
}> = ({
  column,
  index,
  evalObjs,
  entity,
  project,
  handleColumnChange,
  moveColumn,
  cloneColumn,
  removeColumn,
  totalColumns,
}) => {
  const scorers = useScorers(entity, project, column.evaluation_object_ref);
  const metrics = useMetrics(
    entity,
    project,
    column.evaluation_object_ref,
    column.scorer_name
  );
  const selectedEvalObj = evalObjs.find(
    obj => obj.ref === column.evaluation_object_ref
  );
  const selectedScorer = useMemo(
    () => (column.scorer_name ? {val: column.scorer_name} : undefined),
    [column.scorer_name]
  );
  const selectedMetricPath = useMemo(
    () => ({val: column.summary_metric_path_parts.join('.')}),
    [column.summary_metric_path_parts]
  );
  return (
    <Box flexGrow={1} display="flex" flexWrap="wrap" alignItems="center">
      <Box flexGrow={1} minWidth={200} mr={2} mb={2}>
        <Select<EvaluationHelperObj>
          value={selectedEvalObj}
          placeholder="Evaluation Definition"
          onChange={newVal =>
            handleColumnChange(index, 'evaluation_object_ref', newVal?.ref)
          }
          options={evalObjs}
          getOptionLabel={obj =>
            `${obj.name}:v${obj.versionIndex} (${obj.digest.slice(0, 6)})`
          }
          getOptionValue={obj => obj.ref}
        />
      </Box>
      <Box flexGrow={1} minWidth={200} mr={2} mb={2}>
        <Select<{val: string}>
          value={selectedScorer}
          onChange={newVal =>
            handleColumnChange(index, 'scorer_name', newVal?.val)
          }
          options={scorers.map(scorer => ({val: scorer}))}
          isDisabled={!column.evaluation_object_ref}
          getOptionLabel={scorer => scorer.val}
          getOptionValue={scorer => scorer.val}
        />
      </Box>
      <Box flexGrow={1} minWidth={200} mr={2} mb={2}>
        <Select<{val: string}>
          value={selectedMetricPath}
          onChange={newVal =>
            handleColumnChange(
              index,
              'summary_metric_path_parts',
              newVal?.val.split('.')
            )
          }
          options={metrics.map(metric => ({val: metric}))}
          isDisabled={!column.evaluation_object_ref || !column.scorer_name}
          getOptionLabel={metric => metric.val}
          getOptionValue={metric => metric.val}
        />
      </Box>
      <Box display="flex" alignItems="center" mb={2} sx={{gridGap: 4}}>
        <Checkbox
          checked={column.should_minimize ?? false}
          onCheckedChange={checked =>
            handleColumnChange(index, 'should_minimize', !!checked)
          }
        />
        <span>Minimize</span>
      </Box>
      <Box display="flex" justifyContent="flex-end" mb={2}>
        <Button
          size="small"
          icon="chevron-up"
          variant="quiet"
          onClick={() => moveColumn(index, index - 1)}
          disabled={index === 0}></Button>
        <Button
          size="small"
          icon="chevron-down"
          variant="quiet"
          onClick={() => moveColumn(index, index + 1)}
          disabled={index === totalColumns - 1}></Button>
        <Button
          icon="copy"
          variant="quiet"
          size="small"
          onClick={() => cloneColumn(index)}></Button>
        <Button
          icon="delete"
          variant="quiet"
          size="small"
          onClick={() => removeColumn(index)}></Button>
      </Box>
    </Box>
  );
};

type EvaluationHelperObj = {
  obj: TraceObjSchema;
  ref: string;
  name: string;
  versionIndex: number;
  digest: string;
};

const useEvaluationObjects = (
  entity: string,
  project: string
): EvaluationHelperObj[] => {
  const getClient = useGetTraceServerClientContext();
  const client = getClient();
  const [evalObjs, setEvalObjs] = useState<EvaluationHelperObj[]>([]);
  useEffect(() => {
    let mounted = true;
    client
      .objsQuery({
        project_id: projectIdFromParts({entity, project}),
        filter: {
          base_object_classes: ['Evaluation'],
          is_op: false,
        },
        metadata_only: true,
        sort_by: [{field: 'created_at', direction: 'desc'}],
      })
      .then(res => {
        if (mounted) {
          setEvalObjs(
            res.objs.map(obj => ({
              obj,
              ref: refUri({
                scheme: 'weave',
                entityName: entity,
                projectName: project,
                weaveKind: 'object',
                artifactName: obj.object_id,
                artifactVersion: obj.digest,
              }),
              name: obj.object_id,
              versionIndex: obj.version_index,
              digest: obj.digest,
            }))
          );
        }
      });

    return () => {
      mounted = false;
    };
  }, [client, entity, project]);
  return evalObjs;
};

const useScorers = (
  entity: string,
  project: string,
  evaluationObjectRef: string
): string[] => {
  const getClient = useGetTraceServerClientContext();
  const client = getClient();
  const [scorers, setScorers] = useState<string[]>([]);

  useEffect(() => {
    if (!evaluationObjectRef) {
      setScorers([]);
      return;
    }

    let mounted = true;
    client.readBatch({refs: [evaluationObjectRef]}).then(res => {
      if (mounted) {
        setScorers(
          (res.vals[0].scorers ?? [])
            .map((scorer: string) => parseRefMaybe(scorer)?.artifactName)
            .filter(Boolean) as string[]
        );
      }
    });

    return () => {
      mounted = false;
    };
  }, [client, entity, project, evaluationObjectRef]);

  return scorers;
};

const useMetrics = (
  entity: string,
  project: string,
  evaluationObjectRef: string,
  scorerName: string
): string[] => {
  const getClient = useGetTraceServerClientContext();
  const client = getClient();
  const [metrics, setMetrics] = useState<string[]>([]);

  useEffect(() => {
    if (!evaluationObjectRef || !scorerName) {
      setMetrics([]);
      return;
    }

    let mounted = true;
    client
      .callsStreamQuery({
        project_id: projectIdFromParts({entity, project}),
        filter: {
          op_names: [
            opVersionKeyToRefUri({
              entity,
              project,
              opId: EVALUATE_OP_NAME_POST_PYDANTIC,
              versionHash: ALL_VALUE,
            }),
          ],
          input_refs: [evaluationObjectRef],
        },
        limit: 1,
      })
      .then(res => {
        if (mounted) {
          const calls = res.calls;
          if (calls.length === 0) {
            setMetrics([]);
          } else {
            const output = calls[0].output ?? {};
            if (
              typeof output === 'object' &&
              output != null &&
              scorerName in output
            ) {
              setMetrics(
                Object.keys(
                  flattenObjectPreservingWeaveTypes(
                    (output as Record<string, any>)[scorerName]
                  )
                )
              );
            } else {
              setMetrics([]);
            }
          }
        }
      });

    return () => {
      mounted = false;
    };
  }, [client, entity, project, evaluationObjectRef, scorerName]);

  return metrics;
};
