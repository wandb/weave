import {
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
} from '@material-ui/core';
import _ from 'lodash';
import React, {FC, useEffect, useState} from 'react';

import {DynamicConfigForm} from '../../DynamicConfigForm';
import {ReusableDrawer} from '../../ReusableDrawer';
import {
  ActionDefinition,
  ActionDefinitionSchema,
} from '../wfReactInterface/generatedBaseObjectClasses.zod';
import {actionTemplates} from './actionTemplates';
import {knownBuiltinActions} from './builtinActions';

interface NewBuiltInActionScorerModalProps {
  open: boolean;
  onClose: () => void;
  onSave: (newAction: ActionDefinition) => void;
  initialTemplate: string;
}

export const NewBuiltInActionScorerModal: FC<
  NewBuiltInActionScorerModalProps
> = ({open, onClose, onSave, initialTemplate}) => {
  const [name, setName] = useState('');
  const [selectedActionIndex, setSelectedActionIndex] = useState<number>(0);
  const [config, setConfig] = useState<Record<string, any>>({});

  useEffect(() => {
    if (initialTemplate) {
      const template = actionTemplates.find(t => t.name === initialTemplate);
      if (template) {
        setConfig(template.type);
        setName(template.name);
      }
    } else {
      setConfig({});
      setName('');
    }
  }, [initialTemplate]);

  const handleSave = () => {
    const newAction = ActionDefinitionSchema.parse({
      name,
      spec: knownBuiltinActions[selectedActionIndex].convert(config as any),
    });
    onSave(newAction);
    setConfig({});
    setSelectedActionIndex(0);
    setName('');
  };

  const [isValid, setIsValid] = useState(false);

  return (
    <ReusableDrawer
      open={open}
      title="Configure Scorer"
      onClose={onClose}
      onSave={handleSave}
      saveDisabled={!isValid}>
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
          {knownBuiltinActions.map(({name: actionName}, ndx) => (
            <MenuItem key={actionName} value={ndx}>
              {actionName}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      {selectedActionIndex !== -1 && (
        <DynamicConfigForm
          configSchema={
            knownBuiltinActions[selectedActionIndex].inputFriendlySchema
          }
          config={config}
          setConfig={setConfig}
          onValidChange={setIsValid}
        />
      )}
    </ReusableDrawer>
  );
};
