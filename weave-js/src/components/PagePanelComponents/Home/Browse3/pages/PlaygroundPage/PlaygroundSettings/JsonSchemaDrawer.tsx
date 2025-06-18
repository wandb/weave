import {Box} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
import {CodeEditor} from '@wandb/weave/components/CodeEditor';
import React, {useEffect, useState} from 'react';

import {ResizableDrawer} from '../../common/ResizableDrawer';
import {TabUseBannerError} from '../../common/TabUseBanner';
import {PlaygroundResponseFormats} from '../types';

export type JsonSchemaDrawerProps = {
  open: boolean;
  onClose: () => void;
  jsonSchema: string;
  setJsonSchema: (val: string) => void;
  responseFormat: PlaygroundResponseFormats;
  setResponseFormat: (val: PlaygroundResponseFormats) => void;
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
  setJsonSchema,
  responseFormat,
  setResponseFormat,
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
      setJsonSchema(localSchema);
      if (responseFormat !== PlaygroundResponseFormats.JsonSchema) {
        setResponseFormat(PlaygroundResponseFormats.JsonSchema);
      }
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
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            px: 3,
            py: 2,
            borderBottom: '1px solid',
            borderColor: 'divider',
            backgroundColor: 'background.paper',
          }}>
          <span style={{fontSize: 20, fontWeight: 600}}>Edit JSON Schema</span>
          <Button icon="close" variant="ghost" onClick={onClose} />
        </Box>
      }>
      <Box
        sx={{
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}>
        {/* Content */}
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            px: 3,
            py: 2,
            overflowY: 'auto',
            overflowX: 'hidden',
            gap: 2,
          }}>
          {error && (
            <TabUseBannerError>
              Invalid JSON:
              {error.split('\n').map((line, index) => (
                <span key={index}>{line}</span>
              ))}
            </TabUseBannerError>
          )}

          <Box sx={{display: 'flex', justifyContent: 'flex-end', gap: 1}}>
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
          </Box>

          <CodeEditor
            value={localSchema}
            language="json"
            minHeight={200}
            maxHeight={500}
            onChange={(val: string) => setLocalSchema(val)}
            wrapLines
          />
        </Box>
        {/* Footer */}
        <Box
          sx={{
            py: 2,
            px: 0,
            borderTop: '1px solid',
            borderColor: 'divider',
            backgroundColor: 'background.paper',
            width: '100%',
            display: 'flex',
            flexShrink: 0,
            position: 'sticky',
            bottom: 0,
          }}>
          <Box sx={{display: 'flex', gap: 2, width: '100%', mx: 2}}>
            <Button
              onClick={onClose}
              variant="secondary"
              style={{flex: 1}}
              twWrapperStyles={{flex: 1}}>
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              variant="primary"
              style={{flex: 1}}
              twWrapperStyles={{flex: 1}}>
              Save
            </Button>
          </Box>
        </Box>
      </Box>
    </ResizableDrawer>
  );
};
