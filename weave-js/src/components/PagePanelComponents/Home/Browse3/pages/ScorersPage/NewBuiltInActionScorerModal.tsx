import {
  Box,
  Button,
  Drawer,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@material-ui/core';
import React, {FC, useEffect, useState} from 'react';

import {
  ActionWithConfig,
  ActionWithConfigSchema,
  knownBuiltinActions,
} from '../../collections/actionCollection';
import {DynamicConfigForm} from '../../DynamicConfigForm';

interface NewBuiltInActionScorerModalProps {
  open: boolean;
  onClose: () => void;
  onSave: (newAction: ActionWithConfig) => void;
}

export const NewBuiltInActionScorerModal: FC<
  NewBuiltInActionScorerModalProps
> = ({open, onClose, onSave}) => {
  const [name, setName] = useState('');
  const [selectedActionIndex, setSelectedActionIndex] = useState<number>(0);
  const [config, setConfig] = useState<Record<string, any>>({});

  useEffect(() => {
    // Reset config when action type changes
    setConfig({});
  }, [selectedActionIndex]);

  const handleSave = () => {
    const newAction = ActionWithConfigSchema.parse({
      name,
      action: knownBuiltinActions[selectedActionIndex].action,
      config: knownBuiltinActions[selectedActionIndex].convertToConfig(config),
    });
    onSave(newAction);
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={() => {
        // Prevent closing if the user hasn't saved
        return;
      }}
      ModalProps={{
        keepMounted: true, // Better open performance on mobile
      }}>
      <Box
        sx={{
          width: '40vw',
          marginTop: '60px',
          height: '100%',
          bgcolor: 'background.paper',
          p: 4,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'auto',
        }}>
        <Typography
          id="new-built-in-action-scorer-modal"
          variant="h6"
          component="h2"
          gutterBottom>
          Configure new built-in action scorer
        </Typography>

        <Box sx={{flexGrow: 1, overflow: 'auto', my: 2}}>
          <TextField
            fullWidth
            label="Name"
            value={name}
            onChange={e => setName(e.target.value)}
            margin="normal"
          />
          <FormControl fullWidth margin="normal">
            <InputLabel>Action Type</InputLabel>
            <Select
              value={selectedActionIndex}
              onChange={e =>
                setSelectedActionIndex(parseInt(e.target.value as string, 10))
              }>
              {knownBuiltinActions.map(({action}, ndx) => (
                <MenuItem key={action.name} value={ndx}>
                  {action.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {selectedActionIndex !== -1 && (
            <DynamicConfigForm
              configSchema={knownBuiltinActions[selectedActionIndex].configSpec}
              config={config}
              setConfig={setConfig}
            />
          )}
        </Box>

        <Box sx={{display: 'flex', justifyContent: 'flex-end', mt: 2}}>
          <Button onClick={onClose} style={{marginRight: 8}}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            variant="contained"
            color="primary"
            disabled={!name || selectedActionIndex === -1}>
            Save
          </Button>
        </Box>
      </Box>
    </Drawer>
  );
};
