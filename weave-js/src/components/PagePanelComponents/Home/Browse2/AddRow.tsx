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
import React, {FC, useCallback, useState} from 'react';

import {useWFHooks} from '../Browse3/pages/wfReactInterface/context';
import {Link} from './CommonLib';
import {ObjectEditor, useObjectEditorState} from './ObjectEditor';
import {ChosenObjectNameOption, ObjectNamePicker} from './ObjectPicker';
import {ProjectNamePicker} from './ProjectPicker';
import {useRefPageUrl} from './url';

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
  const {useApplyMutationsToRef} = useWFHooks();
  const applyMutationsToRef = useApplyMutationsToRef();
  const addRowToDataset = useCallback(async () => {
    if (projectName && datasetName) {
      setWorking('addingRow');
      // Note: this is not necessarily correct when we move to the new object
      // server - we may need to use a different ref type
      const refUri = `wandb-artifact:///${entityName}/${projectName}/${datasetName.name}:latest/obj#atr/rows`;
      const finalRootUri = await applyMutationsToRef(refUri, [
        {
          type: 'append',
          newValue: row,
        },
      ]);
      setNewUri(finalRootUri);
      setWorking('done');
    }
  }, [applyMutationsToRef, datasetName, entityName, projectName, row]);

  const handleSubmit = useCallback(() => {
    addRowToDataset();
  }, [addRowToDataset]);

  const refPageUrl = useRefPageUrl();

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
                  <Link to={refPageUrl('Dataset', newUri!)}>View Dataset</Link>
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
