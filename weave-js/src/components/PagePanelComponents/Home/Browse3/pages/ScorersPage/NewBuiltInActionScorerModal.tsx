import {
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
} from '@material-ui/core';
import _ from 'lodash';
import React, {FC, useEffect, useState} from 'react';
import {z} from 'zod';

import {
  ConfiguredActionSchema,
  ConfiguredActionType,
  ConfiguredLlmJudgeActionSchema,
  ConfiguredWordCountActionSchema,
} from '../../collections/actionCollection';
import {DynamicConfigForm} from '../../DynamicConfigForm';
import {ReusableDrawer} from '../../ReusableDrawer';
import {
  actionTemplates,
  ConfiguredLlmJudgeActionFriendlySchema,
} from './actionTemplates';

const knownBuiltinActions = [
  {
    name: 'LLM Judge',
    actionSchema: ConfiguredLlmJudgeActionSchema,
    friendly: {
      schema: ConfiguredLlmJudgeActionFriendlySchema,
      convert: (
        data: z.infer<typeof ConfiguredLlmJudgeActionFriendlySchema>
      ): z.infer<typeof ConfiguredLlmJudgeActionSchema> => {
        let responseFormat: z.infer<
          typeof ConfiguredLlmJudgeActionSchema
        >['response_format'];
        if (data.response_format.type === 'simple') {
          responseFormat = {type: data.response_format.schema};
        } else {
          responseFormat = {
            type: 'object',
            properties: _.mapValues(data.response_format.schema, value => ({
              type: value as 'boolean' | 'number' | 'string',
            })),
            additionalProperties: false,
          };
        }
        return {
          action_type: 'llm_judge',
          model: data.model,
          prompt: data.prompt,
          response_format: responseFormat,
        };
      },
    },
  },
  {
    name: 'Word Count',
    actionSchema: ConfiguredWordCountActionSchema,
    friendly: {
      schema: z.object({}),
      convert: (
        data: z.infer<typeof ConfiguredWordCountActionSchema>
      ): z.infer<typeof ConfiguredWordCountActionSchema> => {
        return {
          action_type: 'wordcount',
        };
      },
    },
  },
];

interface NewBuiltInActionScorerModalProps {
  open: boolean;
  onClose: () => void;
  onSave: (newAction: ConfiguredActionType) => void;
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
    const newAction = ConfiguredActionSchema.parse({
      name,
      config: knownBuiltinActions[selectedActionIndex].friendly.convert(
        config as any
      ),
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
            knownBuiltinActions[selectedActionIndex].friendly.schema
          }
          config={config}
          setConfig={setConfig}
          onValidChange={setIsValid}
        />
      )}
    </ReusableDrawer>
  );
};
