import {Box} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
import {Select} from '@wandb/weave/components/Form/Select';
import {Icon} from '@wandb/weave/components/Icon';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useState} from 'react';

import {PlaygroundResponseFormats} from '../types';
import {
  DEFAULT_SCHEMA,
  EMPTY_SCHEMA,
  JsonSchemaDrawer,
} from './JsonSchemaDrawer';

const RESPONSE_FORMATS: PlaygroundResponseFormats[] = Object.values(
  PlaygroundResponseFormats
);

export const ResponseFormatEditor: React.FC<
  ResponseFormatSelectProps
> = props => {
  const [jsonSchemaDrawerOpen, setJsonSchemaDrawerOpen] = useState(false);

  return (
    <Tailwind>
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
        }}>
        <span style={{fontSize: '14px'}}>Response format</span>
        <ResponseFormatSelect {...props} />
        {props.responseFormat !== PlaygroundResponseFormats.Text &&
          (props.jsonSchema &&
          props.jsonSchema.trim() &&
          isValidJson(props.jsonSchema) ? (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                justifyContent: 'space-between',
              }}>
              <span
                style={{
                  fontSize: 16,
                  display: 'flex',
                  alignItems: 'center',
                }}>
                <Icon
                  name="checkmark"
                  style={{marginRight: 6, fontSize: 20}}
                  className="text-green-500"
                />
                JSON schema defined
              </span>
              <Button
                variant="ghost"
                style={{marginLeft: 'auto'}}
                onClick={() => setJsonSchemaDrawerOpen(true)}
                icon="pencil-edit">
                Edit
              </Button>
            </Box>
          ) : (
            <Button
              variant="secondary"
              onClick={() => setJsonSchemaDrawerOpen(true)}
              icon="add-new"
              className="w-full">
              Add JSON schema
            </Button>
          ))}
        <JsonSchemaDrawer
          open={jsonSchemaDrawerOpen}
          onClose={() => setJsonSchemaDrawerOpen(false)}
          jsonSchema={props.jsonSchema ?? EMPTY_SCHEMA}
          onSave={jsonSchema => {
            props.setJsonSchema(jsonSchema);
            props.setResponseFormat(PlaygroundResponseFormats.JsonSchema);
          }}
        />
      </Box>
    </Tailwind>
  );
};

interface ResponseFormatSelectProps {
  jsonSchema: string | undefined;
  responseFormat: PlaygroundResponseFormats;
  setResponseFormat: (value: PlaygroundResponseFormats) => void;
  setJsonSchema: (value: string | undefined) => void;
}

export const ResponseFormatSelect = ({
  setJsonSchema,
  responseFormat,
  setResponseFormat,
}: ResponseFormatSelectProps) => {
  const options = RESPONSE_FORMATS.map(format => ({
    value: format,
    label: format,
  }));
  return (
    <Select
      value={options.find(opt => opt.value === responseFormat)}
      onChange={option => {
        if (option) {
          setResponseFormat(
            (option as {value: PlaygroundResponseFormats}).value
          );
          if (option.value === PlaygroundResponseFormats.JsonSchema) {
            setJsonSchema(DEFAULT_SCHEMA);
          } else {
            setJsonSchema(undefined);
          }
        }
      }}
      options={options}
      size="medium"
    />
  );
};

function isValidJson(str: string): boolean {
  try {
    JSON.parse(str);
    return true;
  } catch {
    return false;
  }
}
