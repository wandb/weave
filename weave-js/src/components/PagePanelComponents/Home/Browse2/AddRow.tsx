import {
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  Typography,
} from '@mui/material';
import {useWeaveContext} from '@wandb/weave/context';
import {constString, opGet} from '@wandb/weave/core';
import React, {FC, useCallback, useState} from 'react';

import {Link} from './CommonLib';
import {useWeaveflowRouteContext} from './context';
import {
  mutationAppend,
  mutationPublishArtifact,
  weaveGet,
  weaveObject,
} from './easyWeave';
import {ObjectEditor, useObjectEditorState} from './ObjectEditor';
import {ChosenObjectNameOption, ObjectNamePicker} from './ObjectPicker';
import {ProjectNamePicker} from './ProjectPicker';

interface AddRowToPaneFormState {
  projectName?: string;
  datasetName?: string;
  row?: {[key: string]: any};
}

export const AddRowToTable: FC<{
  entityName: string;
  open: boolean;
  handleClose: () => void;
  initialFormState: AddRowToPaneFormState;
}> = ({entityName, open, handleClose, initialFormState}) => {
  const weave = useWeaveContext();
  const routeContext = useWeaveflowRouteContext();
  const [projectName, setProjectName] = useState<string | null>(
    initialFormState.projectName ?? null
  );
  const [datasetName, setDatasetName] = useState<ChosenObjectNameOption | null>(
    initialFormState.datasetName != null
      ? {name: initialFormState.datasetName}
      : null
  );

  const {
    value: row,
    valid: rowValid,
    props: objectEditorProps,
  } = useObjectEditorState(initialFormState.row ?? {});

  const formValid = rowValid && projectName && datasetName;

  const [working, setWorking] = useState<
    'idle' | 'addingRow' | 'publishing' | 'done'
  >('idle');
  const [newUri, setNewUri] = useState<string | null>(null);

  const addRowToDataset = useCallback(async () => {
    if (projectName && datasetName) {
      setWorking('addingRow');

      const datasetRowsNode = weaveGet(
        // Dataset object we are appending to
        `wandb-artifact:///${entityName}/${projectName}/${datasetName.name}:latest/obj`,
        // Default value if the dataset doesn't exist
        weaveObject('Dataset', {rows: []})
      ).getAttr('rows');

      const workingRootUri = await mutationAppend(weave, datasetRowsNode, row);
      setWorking('publishing');

      // Returns final root uri if we need it.
      const finalRootUri = await mutationPublishArtifact(
        weave,
        // Local branch
        opGet({uri: constString(workingRootUri)}),
        // Target branch
        entityName,
        projectName,
        datasetName.name
      );
      setNewUri(finalRootUri);
      setWorking('done');
    }
  }, [datasetName, entityName, projectName, row, weave]);

  const handleSubmit = useCallback(() => {
    addRowToDataset();
  }, [addRowToDataset]);

  return (
    <Dialog fullWidth maxWidth="sm" open={open} onClose={handleClose}>
      <DialogTitle>Add Row</DialogTitle>
      {working === 'idle' ? (
        <>
          <DialogContent>
            <Grid container direction="column" spacing={2}>
              <Grid item>
                <ProjectNamePicker
                  entityName={entityName}
                  value={projectName}
                  setValue={setProjectName}
                />
              </Grid>
              <Grid item>
                <ObjectNamePicker
                  entityName={entityName}
                  projectName={projectName}
                  rootType="Dataset"
                  value={datasetName}
                  setChosenObjectName={setDatasetName}
                />
                <Typography variant="caption">
                  {datasetName?.isNew
                    ? `Dataset ${datasetName.name} will be created`
                    : ''}
                </Typography>
              </Grid>
              <Grid item>
                <ObjectEditor {...objectEditorProps} label="Row Data" />
              </Grid>
            </Grid>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleClose}>Cancel</Button>
            <Button onClick={handleSubmit} disabled={!formValid}>
              Add Row
            </Button>
          </DialogActions>
        </>
      ) : (
        <>
          <DialogContent>
            <Typography>Adding row to dataset...</Typography>
            {(working === 'publishing' || working === 'done') && (
              <Typography>Publishing new dataset version...</Typography>
            )}
            {working === 'done' && <Typography>Done</Typography>}
            {working === 'done' && (
              <Box mt={2}>
                <Typography>
                  <Link to={routeContext.refPageUrl('Dataset', newUri!)}>
                    View Dataset
                  </Link>
                </Typography>
              </Box>
            )}
          </DialogContent>
          <DialogActions>
            <Button disabled={working !== 'done'} onClick={handleClose}>
              Close
            </Button>
          </DialogActions>
        </>
      )}
    </Dialog>
  );
};
