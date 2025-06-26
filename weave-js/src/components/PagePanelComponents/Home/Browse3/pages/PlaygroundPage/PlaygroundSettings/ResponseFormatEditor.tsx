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

interface ResponseFormatEditorProps {
  jsonSchema: string | undefined;
  responseFormat: PlaygroundResponseFormats;
  setResponseFormat: (value: PlaygroundResponseFormats) => void;
  setJsonSchema: (value: string | undefined) => void;
}

export const ResponseFormatEditor: React.FC<
  ResponseFormatEditorProps
> = props => {
  const [jsonSchemaDrawerOpen, setJsonSchemaDrawerOpen] = useState(false);

  const setResponseFormat = (value: PlaygroundResponseFormats) => {
    props.setResponseFormat(value);
    if (value === PlaygroundResponseFormats.JsonSchema) {
      props.setJsonSchema(DEFAULT_SCHEMA);
    } else {
      props.setJsonSchema(undefined);
    }
  };

  return (
    <Tailwind>
      <div className="flex flex-col gap-4">
        <span className="text-sm">Response format</span>
        <ResponseFormatSelect
          {...props}
          setResponseFormat={setResponseFormat}
        />
        {props.responseFormat !== PlaygroundResponseFormats.Text &&
          (props.jsonSchema &&
          props.jsonSchema.trim() &&
          isValidJson(props.jsonSchema) ? (
            <div className="mt-4 flex items-center justify-between gap-4">
              <span className="flex items-center gap-2">
                <Icon name="checkmark" className="mr-2 text-green-500" />
                JSON schema defined
              </span>
              <Button
                variant="ghost"
                size="small"
                className="ml-auto"
                onClick={() => setJsonSchemaDrawerOpen(true)}
                icon="pencil-edit">
                Edit
              </Button>
            </div>
          ) : (
            <Button
              variant="secondary"
              onClick={() => setJsonSchemaDrawerOpen(true)}
              icon="add-new"
              className="mt-4 w-full">
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
      </div>
    </Tailwind>
  );
};

interface ResponseFormatSelectProps {
  responseFormat: PlaygroundResponseFormats;
  setResponseFormat: (value: PlaygroundResponseFormats) => void;
}

export const ResponseFormatSelect = ({
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
