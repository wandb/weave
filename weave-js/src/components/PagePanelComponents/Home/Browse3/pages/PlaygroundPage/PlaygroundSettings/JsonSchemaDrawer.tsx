import {Button} from '@wandb/weave/components/Button';
import {CodeEditor} from '@wandb/weave/components/CodeEditor';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useEffect, useState} from 'react';

import {ResizableDrawer} from '../../common/ResizableDrawer';
import {TabUseBannerError} from '../../common/TabUseBanner';

export type JsonSchemaDrawerProps = {
  open: boolean;
  onClose: () => void;
  jsonSchema: string;
  onSave: (jsonSchema: string) => void;
};

export const EMPTY_SCHEMA = `{
  "type": "json_schema",
  "json_schema": {}
}`;

export const DEFAULT_SCHEMA = `{
  "type": "json_schema",
  "json_schema": {
    "name": "my_schema",
    "strict": true,
    "schema": {
        "type": "object",
        "properties": {
          "name": { "type": "string" },
          "age": { "type": "integer" }
        },
        "required": [ "name", "age" ],
        "additionalProperties": false
    }
  }
}`;

export const JsonSchemaDrawer: React.FC<JsonSchemaDrawerProps> = ({
  open,
  onClose,
  jsonSchema,
  onSave,
}) => {
  const [localSchema, setLocalSchema] = useState(jsonSchema || DEFAULT_SCHEMA);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLocalSchema(jsonSchema || DEFAULT_SCHEMA);
    setError(null);
  }, [open, jsonSchema]);

  const handleSave = () => {
    try {
      JSON.parse(localSchema);
      onSave(localSchema);
      onClose();
    } catch (e: any) {
      setError(e.message);
    }
  };

  return (
    <ResizableDrawer
      open={open}
      onClose={onClose}
      defaultWidth={500}
      marginTop={60}
      headerContent={
        <Tailwind>
          <div className="flex h-64 items-center justify-between border-b border-moon-200 px-16 py-8">
            <span className="text-2xl font-semibold">Edit JSON Schema</span>
            <Button icon="close" variant="ghost" onClick={onClose} />
          </div>
        </Tailwind>
      }>
      <Tailwind style={{height: '100%'}}>
        <div className="flex h-full flex-col justify-between overflow-hidden">
          {/* Content */}
          <div className="flex flex-1 flex-col gap-8 overflow-hidden px-16 py-16">
            {error && (
              <TabUseBannerError>
                Invalid JSON:
                {error.split('\n').map((line, index) => (
                  <span key={index}>{line}</span>
                ))}
              </TabUseBannerError>
            )}

            <div className="flex justify-end gap-1">
              <Button
                variant="secondary"
                size="small"
                onClick={() => setLocalSchema(DEFAULT_SCHEMA)}>
                Load placeholder schema
              </Button>
              <Button
                variant="secondary"
                size="small"
                onClick={() => setLocalSchema(EMPTY_SCHEMA)}>
                Clear schema
              </Button>
            </div>

            <CodeEditor
              value={localSchema}
              language="json"
              minHeight={200}
              maxHeight={500}
              onChange={(val: string) => setLocalSchema(val)}
              wrapLines
            />
          </div>

          {/* Footer */}
          <div className="flex gap-2 border-t border-moon-200 px-0 py-16">
            <div className="flex w-full gap-8 px-16">
              <Button
                onClick={onClose}
                variant="secondary"
                className="flex-1"
                twWrapperStyles={{flex: 1}}>
                Cancel
              </Button>
              <Button
                onClick={handleSave}
                variant="primary"
                className="flex-1"
                twWrapperStyles={{flex: 1}}>
                Save
              </Button>
            </div>
          </div>
        </div>
      </Tailwind>
    </ResizableDrawer>
  );
};
