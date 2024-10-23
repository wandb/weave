import { Box, Button, FormControl, InputLabel,MenuItem, Modal, Select, TextField, Typography } from '@material-ui/core';
import React, { FC, useEffect,useState } from 'react';

import { ActionWithConfig, ActionWithConfigSchema, knownBuiltinActions , ActionAndSpec} from '../../collections/actionCollection';
import { DynamicConfigForm } from './DynamicConfigForm';

interface NewBuiltInActionScorerModalProps {
  open: boolean;
  onClose: () => void;
  onSave: (newAction: ActionWithConfig) => void;
}

export const NewBuiltInActionScorerModal: FC<NewBuiltInActionScorerModalProps> = ({
  open,
  onClose,
  onSave,
}) => {
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
      config,
    });
    onSave(newAction);
  };

  return (
    <Modal
      open={open}
      onClose={null}
      aria-labelledby="new-built-in-action-scorer-modal"
    >
      <Box
        sx={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: 400,
          bgcolor: 'background.paper',
          boxShadow: 24,
          p: 4,
          borderRadius: 2,
          display: 'flex',
          flexDirection: 'column',
          maxHeight: '80vh',
        }}
      >
        <Typography id="new-built-in-action-scorer-modal" variant="h6" component="h2" gutterBottom>
          Configure new built-in action scorer
        </Typography>
        
        <Box sx={{ flexGrow: 1, overflowY: 'auto', my: 2 }}>
          <TextField
            fullWidth
            label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            margin="normal"
          />
          <FormControl fullWidth margin="normal">
            <InputLabel>Action Type</InputLabel>
            <Select
              value={selectedActionIndex}
              onChange={(e) => setSelectedActionIndex(parseInt(e.target.value))}
            >
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
        
        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
          <Button onClick={onClose} sx={{ mr: 1 }}>
            Cancel
          </Button>
          <Button onClick={handleSave} variant="contained" color="primary" disabled={!name || selectedActionIndex === -1}>
            Save
          </Button>
        </Box>
      </Box>
    </Modal>
  );
};
