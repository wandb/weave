import {
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  IconButton,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@material-ui/core';
import {
  Add as AddIcon,
  ArrowDownward as MoveDownIcon,
  ArrowUpward as MoveUpIcon,
  Delete as DeleteIcon,
  FileCopy as CloneIcon,
} from '@material-ui/icons';
import {refUri} from '@wandb/weave/react';
import React, {useEffect, useState} from 'react';

import {flattenObjectPreservingWeaveTypes} from '../../../Browse2/browse2Util';
import {parseRefMaybe} from '../../../Browse2/SmallRef';
import {
  ALL_VALUE,
  PythonLeaderboardObjectVal,
} from '../../views/Leaderboard/types/leaderboardConfigType';
import {EVALUATE_OP_NAME_POST_PYDANTIC} from '../common/heuristics';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {TraceObjSchema} from '../wfReactInterface/traceServerClientTypes';
import {projectIdFromParts} from '../wfReactInterface/tsDataModelHooks';
import {opVersionKeyToRefUri} from '../wfReactInterface/utilities';

export const LeaderboardConfigEditor: React.FC<{
  entity: string;
  project: string;
  leaderboardVal: PythonLeaderboardObjectVal;
  saving: boolean;
  isDirty: boolean;
  setWorkingCopy: (leaderboardVal: PythonLeaderboardObjectVal) => void;
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
  const handleNameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setWorkingCopy({...leaderboardVal, name: event.target.value});
  };

  const handleDescriptionChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    setWorkingCopy({...leaderboardVal, description: event.target.value});
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
      <Box flexGrow={1} overflow="auto" p={2}>
        <Typography variant="h6" gutterBottom>
          Display Name
        </Typography>
        <TextField
          fullWidth
          value={leaderboardVal.name}
          onChange={handleNameChange}
          margin="normal"
        />
        <Typography variant="h6" gutterBottom style={{marginTop: 16}}>
          Description
        </Typography>
        <TextField
          fullWidth
          value={leaderboardVal.description}
          onChange={handleDescriptionChange}
          margin="normal"
          multiline
          minRows={1}
          maxRows={10}
          InputProps={{style: {fontFamily: 'monospace', fontSize: '14px'}}}
        />
        <Typography variant="h6" gutterBottom style={{marginTop: 16}}>
          Columns
        </Typography>
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
        <Button startIcon={<AddIcon />} onClick={addColumn}>
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
          variant="outlined"
          onClick={discardChanges}
          disabled={saving}
          style={{marginRight: 8}}>
          {isDirty ? 'Discard' : 'Close'}
        </Button>
        {isDirty && (
          <Button
            variant="contained"
            color="primary"
            onClick={commitChanges}
            disabled={saving}>
            Save
          </Button>
        )}
      </Box>
    </Box>
  );
};

const ColumnEditor: React.FC<{
  column: PythonLeaderboardObjectVal['columns'][0];
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

  return (
    <Box
      display="flex"
      flexWrap="wrap"
      alignItems="center"
      mb={2}
      p={2}
      border={1}
      borderColor="divider"
      borderRadius={4}>
      <Box flexGrow={1} display="flex" flexWrap="wrap" alignItems="center">
        <Box flexGrow={1} minWidth={200} mr={2} mb={2}>
          <Select
            fullWidth
            value={column.evaluation_object_ref}
            onChange={e =>
              handleColumnChange(index, 'evaluation_object_ref', e.target.value)
            }
            displayEmpty
            margin="dense">
            <MenuItem value="">
              <em>Select Evaluation Object</em>
            </MenuItem>
            {evalObjs.map(obj => (
              <MenuItem key={obj.ref} value={obj.ref}>
                {`${obj.name}:v${obj.versionIndex} (${obj.digest.slice(0, 6)})`}
              </MenuItem>
            ))}
          </Select>
        </Box>
        <Box flexGrow={1} minWidth={200} mr={2} mb={2}>
          <Select
            fullWidth
            value={column.scorer_name}
            onChange={e =>
              handleColumnChange(index, 'scorer_name', e.target.value)
            }
            displayEmpty
            margin="dense"
            disabled={!column.evaluation_object_ref}>
            <MenuItem value="">
              <em>Select Scorer</em>
            </MenuItem>
            {scorers.map(scorer => (
              <MenuItem key={scorer} value={scorer}>
                {scorer}
              </MenuItem>
            ))}
          </Select>
        </Box>
        <Box flexGrow={1} minWidth={200} mr={2} mb={2}>
          <Select
            fullWidth
            value={column.summary_metric_path_parts.join('.')}
            onChange={e =>
              handleColumnChange(
                index,
                'summary_metric_path_parts',
                (e.target.value as string).split('.')
              )
            }
            displayEmpty
            margin="dense"
            disabled={!column.evaluation_object_ref || !column.scorer_name}>
            <MenuItem value="">
              <em>Select Metric Path</em>
            </MenuItem>
            {metrics.map(path => (
              <MenuItem key={path} value={path}>
                {path}
              </MenuItem>
            ))}
          </Select>
        </Box>
        <Box display="flex" alignItems="center" mb={2} mr={2}>
          <FormControlLabel
            control={
              <Checkbox
                checked={column.should_minimize}
                onChange={e =>
                  handleColumnChange(index, 'should_minimize', e.target.checked)
                }
              />
            }
            label="Minimize"
          />
        </Box>
      </Box>
      <Box display="flex" justifyContent="flex-end" mb={2}>
        <IconButton
          size="small"
          onClick={() => moveColumn(index, index - 1)}
          disabled={index === 0}>
          <MoveUpIcon />
        </IconButton>
        <IconButton
          size="small"
          onClick={() => moveColumn(index, index + 1)}
          disabled={index === totalColumns - 1}>
          <MoveDownIcon />
        </IconButton>
        <IconButton size="small" onClick={() => cloneColumn(index)}>
          <CloneIcon />
        </IconButton>
        <IconButton size="small" onClick={() => removeColumn(index)}>
          <DeleteIcon />
        </IconButton>
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
      console.log(res);
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
    // TODO: Implement the actual API call to fetch metrics for the given evaluation object and scorer
    // This is a placeholder implementation
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
