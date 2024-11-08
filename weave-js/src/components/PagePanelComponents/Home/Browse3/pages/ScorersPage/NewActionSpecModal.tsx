import {
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
} from '@material-ui/core';
import React, {FC, useEffect, useState} from 'react';

import {DynamicConfigForm} from '../../DynamicConfigForm';
import {ReusableDrawer} from '../../ReusableDrawer';
import {
  ActionSpec,
  ActionSpecSchema,
  ActionType,
} from '../wfReactInterface/generatedBaseObjectClasses.zod';
import {actionSpecConfigurationSpecs} from './actionSpecConfigurations';

interface NewActionSpecModalProps {
  open: boolean;
  onClose: () => void;
  onSave: (newAction: ActionSpec) => void;
  initialTemplate?: {
    actionType: ActionType;
    template: {name: string; config: Record<string, any>};
  } | null;
}

export const NewActionSpecModal: FC<NewActionSpecModalProps> = ({
  open,
  onClose,
  onSave,
  initialTemplate,
}) => {
  const [name, setName] = useState<string>('');
  const [selectedActionType, setSelectedActionType] =
    useState<ActionType>('llm_judge');
  const [config, setConfig] = useState<Record<string, any>>({});
  const selectedActionSpecConfigurationSpec =
    actionSpecConfigurationSpecs[selectedActionType];

  useEffect(() => {
    if (initialTemplate) {
      setConfig(initialTemplate.template.config);
      setSelectedActionType(initialTemplate.actionType);
      setName(initialTemplate.template.name);
    } else {
      setConfig({});
      setName('');
    }
  }, [initialTemplate]);

  const handleSave = () => {
    if (!selectedActionSpecConfigurationSpec) {
      return;
    }
    const newAction = ActionSpecSchema.parse({
      name,
      config: selectedActionSpecConfigurationSpec.convert(config as any),
    });
    onSave(newAction);
    setConfig({});
    setSelectedActionType('llm_judge');
    setName('');
  };

  const [isValid, setIsValid] = useState(false);

  return (
    <ReusableDrawer
      open={open}
      title="Configure Scorer"
      onClose={onClose}
      onSave={handleSave}
      saveDisabled={!isValid || name === ''}>
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
          value={selectedActionType}
          onChange={e => setSelectedActionType(e.target.value as ActionType)}>
          {Object.entries(actionSpecConfigurationSpecs).map(
            ([actionType, spec], ndx) => (
              <MenuItem key={actionType} value={actionType}>
                {spec.name}
              </MenuItem>
            )
          )}
        </Select>
      </FormControl>
      {selectedActionSpecConfigurationSpec && (
        <DynamicConfigForm
          configSchema={selectedActionSpecConfigurationSpec.inputFriendlySchema}
          config={config}
          setConfig={setConfig}
          onValidChange={setIsValid}
        />
      )}
    </ReusableDrawer>
  );
};
