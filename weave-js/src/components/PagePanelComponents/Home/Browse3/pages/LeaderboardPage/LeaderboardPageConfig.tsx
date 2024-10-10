import {
  Alert,
  Box,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Typography,
} from '@mui/material';
import React, {useCallback, useMemo, useState} from 'react';

import {useWFHooks} from '../wfReactInterface/context';
import {LeaderboardConfigType} from './LeaderboardConfigType';

export const LeaderboardConfig: React.FC<{
  entity: string;
  project: string;
  config: LeaderboardConfigType;
  onCancel: () => void;
  onPersist: () => void;
  setConfig: (
    updater: (config: LeaderboardConfigType) => LeaderboardConfigType
  ) => void;
}> = ({entity, project, config, setConfig, onPersist, onCancel}) => {
  const handleSave = () => {
    onPersist();
  };

  const handleCancel = () => {
    onCancel();
  };

  const [showAlert, setShowAlert] = useState(true);

  const {useRootObjectVersions} = useWFHooks();

  const evalObjects = useRootObjectVersions(
    entity,
    project,
    {
      baseObjectClasses: ['Evaluation'],
      latestOnly: true,
    },
    undefined,
    true
  );

  const [selectedEvalObject, setSelectedEvalObject] = useState<string | null>(
    null
  );

  // const evalObjectsMap = useMemo(() => {
  //   return new Map(
  //     (evalObjects.result ?? []).map(obj => [
  //       `${obj.objectId}:${obj.versionHash}`,
  //       obj,
  //     ])
  //   );
  // }, [evalObjects]);

  const onEvalObjectChange = useCallback(
    (newEvalObject: string) => {
      // const evalObject = evalObjectsMap.get(newEvalObject);
      // if (!evalObject) {
      //   console.warn('Invalid eval object selected', newEvalObject);
      //   return;
      // }
      const [name, version] = newEvalObject.split(':');
      // const datasetRef = parseRefMaybe(evalObject.val.dataset ?? '');
      // const scorers = (evalObject.val.scorers ?? [])
      //   .map((scorer: string) => parseRefMaybe(scorer ?? ''))
      //   .filter((scorer: ObjectRef | null) => scorer !== null) as ObjectRef[];
      // if (!datasetRef) {
      //   console.warn('Invalid dataset ref', evalObject.val.dataset);
      //   return;
      // }
      setConfig(old => ({
        ...old,
        config: {
          ...old.config,
          dataSelectionSpec: {
            ...old.config.dataSelectionSpec,
            sourceEvaluations: [
              ...(old.config.dataSelectionSpec.sourceEvaluations ?? []),
              {
                name,
                version,
              },
            ],
          },
        },
      }));
      setSelectedEvalObject(newEvalObject);
    },
    [setConfig]
  );

  const evalOptions = useMemo(() => {
    return (evalObjects.result ?? []).flatMap(obj => ([{
      label: `${obj.objectId}:v${obj.versionIndex} (latest) (${obj.versionHash.slice(
        0,
        6
      )})`,
      value: `${obj.objectId}:${obj.versionHash}`,
    }, {
      label: `${obj.objectId}:* (all)`,
      value: `${obj.objectId}:*`,
    }]));
  }, [evalObjects]);

  const toggleModelsGrouped = (shouldGroup: boolean) => {
    setConfig(old => {
      let newModels = [];
      const currModels = old.config.dataSelectionSpec.models ?? [];
      if (currModels.length === 0) {
        newModels.push({
          name: '*',
          version: '*',
          groupAllVersions: shouldGroup,
        });
      } else {
        newModels = currModels.map(model => ({
          ...model,
          groupAllVersions: shouldGroup,
        }));
      }
      return {
        ...old,
        config: {
          ...old.config,
          dataSelectionSpec: {
            ...old.config.dataSelectionSpec,
            models: newModels,
          },
        },
      };
    });
  };

  return (
    <Box
      sx={{
        width: '50%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        border: '1px solid #e0e0e0',
      }}>
      <Box
        sx={{
          // flexGrow: 1,
          overflowY: 'auto',
          p: 2,
        }}>
        {showAlert && <TempAlert onClose={() => setShowAlert(false)} />}
        <Typography variant="h5" gutterBottom>
          Leaderboard Configuration
        </Typography>
        <FormControl fullWidth sx={{mt: 2, mb: 2}}>
          <InputLabel id="eval-select-label">
            Add 'Preset' Evaluation
          </InputLabel>
          <Select
            labelId="eval-select-label"
            id="eval-select"
            value={selectedEvalObject || ''}
            onChange={event => {
              const selectedValue = event.target.value;
              onEvalObjectChange(selectedValue);
            }}
            label="Add 'Preset' Evaluation">
            {evalOptions.map(option => (
              <MenuItem key={option.value} value={option.value}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Button
          variant="outlined"
          onClick={() => toggleModelsGrouped(true)}
          sx={{mt: 2, mb: 2}}>
          Mark Model Versions as Grouped
        </Button>
        <Button
          variant="outlined"
          onClick={() => toggleModelsGrouped(false)}
          sx={{mt: 2, mb: 2}}>
          Mark Model Versions as Individual
        </Button>
      </Box>

      <Box sx={{mt: 2, mb: 2, flex: 1, overflowY: 'auto'}}>
        <Typography variant="h6" gutterBottom>
          Configuration Preview
        </Typography>
        <pre
          style={{
            backgroundColor: '#f5f5f5',
            padding: '10px',
            borderRadius: '4px',
            overflowX: 'auto',
            whiteSpace: 'pre-wrap',
            wordWrap: 'break-word',
          }}>
          {JSON.stringify(config, null, 2)}
        </pre>
      </Box>

      <Box
        sx={{
          display: 'flex',
          justifyContent: 'flex-end',
          height: '51px',
          p: 1,
          borderTop: '1px solid #e0e0e0',
        }}>
        <Button variant="outlined" onClick={handleCancel} sx={{mr: 2}}>
          Cancel
        </Button>
        <Button variant="contained" onClick={handleSave} sx={{mr: 2}}>
          Save
        </Button>
      </Box>
    </Box>
  );
};

const TempAlert: React.FC<{onClose: () => void}> = ({onClose}) => {
  return (
    <Alert severity="info" onClose={onClose}>
      <Typography variant="body1">
        Configuration edtior purely for internal exploration, not for production
        use.
      </Typography>
    </Alert>
  );
};
