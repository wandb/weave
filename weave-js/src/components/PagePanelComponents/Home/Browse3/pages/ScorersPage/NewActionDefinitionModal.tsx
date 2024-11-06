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
  ActionDefinition,
  ActionDefinitionSchema,
  ActionType,
} from '../wfReactInterface/generatedBaseObjectClasses.zod';
import {actionDefinitionConfigurationSpecs} from './actionDefinitionConfigurationSpecs';

interface NewActionDefinitionModalProps {
  open: boolean;
  onClose: () => void;
  onSave: (newAction: ActionDefinition) => void;
  initialTemplate?: {
    actionType: ActionType;
    template: {name: string; config: Record<string, any>};
  } | null;
}

export const NewActionDefinitionModal: FC<NewActionDefinitionModalProps> = ({
  open,
  onClose,
  onSave,
  initialTemplate,
}) => {
  const [name, setName] = useState<string>('');
  const [selectedActionType, setSelectedActionType] =
    useState<ActionType>('llm_judge');
  const [config, setConfig] = useState<Record<string, any>>({});
  const selectedActionDefinitionConfigurationSpec =
    actionDefinitionConfigurationSpecs[selectedActionType];

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
    if (!selectedActionDefinitionConfigurationSpec) {
      return;
    }
    const newAction = ActionDefinitionSchema.parse({
      name,
      spec: selectedActionDefinitionConfigurationSpec.convert(config as any),
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
          {Object.entries(actionDefinitionConfigurationSpecs).map(
            ([actionType, spec], ndx) => (
              <MenuItem key={actionType} value={actionType}>
                {spec.name}
              </MenuItem>
            )
          )}
        </Select>
      </FormControl>
      {selectedActionDefinitionConfigurationSpec && (
        <DynamicConfigForm
          configSchema={
            selectedActionDefinitionConfigurationSpec.inputFriendlySchema
          }
          config={config}
          setConfig={setConfig}
          onValidChange={setIsValid}
        />
      )}
    </ReusableDrawer>
  );
};
