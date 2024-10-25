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

const SimpleResponseFormatSchema = z
  .enum(['boolean', 'number', 'string'])
  .default('boolean');
const StructuredResponseFormatSchema = z.record(SimpleResponseFormatSchema);

const ResponseFormatSchema = z.discriminatedUnion('type', [
  z.object({
    type: z.literal('simple'),
    schema: SimpleResponseFormatSchema,
  }),
  z.object({
    type: z.literal('structured'),
    schema: StructuredResponseFormatSchema,
  }),
]);

const ConfiguredLlmJudgeActionFriendlySchema = z.object({
  model: z.enum(['gpt-4o-mini', 'gpt-4o']).default('gpt-4o-mini'),
  prompt: z.string(),
  response_format: ResponseFormatSchema,
});

const knownBuiltinActions = [
  {
    name: 'LLM Judge',
    actionSchema: ConfiguredLlmJudgeActionSchema,
    friendly: {
      schema: ConfiguredLlmJudgeActionFriendlySchema,
      convert: (
        data: z.infer<typeof ConfiguredLlmJudgeActionFriendlySchema>
      ): z.infer<typeof ConfiguredLlmJudgeActionSchema> => {
        let responseFormat: any;
        if (data.response_format.type === 'simple') {
          responseFormat = {type: data.response_format.schema};
        } else {
          responseFormat = {
            type: 'object',
            properties: _.mapValues(data.response_format.schema, value => ({type: value})),
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
