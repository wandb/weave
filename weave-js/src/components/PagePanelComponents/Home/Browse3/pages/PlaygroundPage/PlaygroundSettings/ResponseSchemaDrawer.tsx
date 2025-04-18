import {Drawer} from '@mui/material';
import {Alert} from '@wandb/weave/components/Alert';
import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useEffect, useState} from 'react';

import {StyledTextArea} from '../../../StyledTextarea';

type JsonSchemaDrawerProps = {
  isOpen: boolean;
  onClose: () => void;
  currentSchema: string; // Pass the current schema as a string
  onSaveSchema: (schemaJSON: string) => void;
};

// Basic placeholder for a JSON Schema
const SCHEMA_PLACEHOLDER = `{
  "type": "object",
  "properties": {
    "sentiment": {
      "type": "string",
      "description": "The sentiment of the text",
      "enum": ["positive", "negative", "neutral"]
    },
    "confidence": {
      "type": "number",
      "description": "Confidence score between 0 and 1"
    }
  },
  "required": ["sentiment"]
}`;

export const JsonSchemaDrawer: React.FC<JsonSchemaDrawerProps> = ({
  isOpen,
  onClose,
  currentSchema,
  onSaveSchema,
}) => {
  // State to hold the schema string being edited
  const [schemaJsonString, setSchemaJsonString] = useState(currentSchema);

  // Update local state if the drawer is opened with a different schema
  useEffect(() => {
    if (isOpen) {
      // Prettify the incoming schema string or use placeholder if empty
      try {
        const parsed = JSON.parse(currentSchema || SCHEMA_PLACEHOLDER);
        setSchemaJsonString(JSON.stringify(parsed, null, 2));
      } catch {
        setSchemaJsonString(currentSchema || SCHEMA_PLACEHOLDER); // Fallback to raw string or placeholder
      }
    } else {
      // Optional: Reset when closing if desired, or keep state
      // setSchemaJsonString(''); // Uncomment to clear on close
    }
  }, [isOpen, currentSchema]);

  const handleSave = () => {
    // Validation ensures we only save valid JSON string
    try {
      JSON.parse(schemaJsonString); // Final validation check
      onSaveSchema(schemaJsonString);
      onClose(); // Close after saving
    } catch (err) {
      // This case should ideally be prevented by disabled button, but good to have
      console.error('Attempted to save invalid JSON:', err);
    }
  };

  // --- Validation Logic ---
  let jsonValidationError = null;
  try {
    // Try parsing to check for valid JSON structure
    JSON.parse(schemaJsonString);
  } catch (err) {
    if (schemaJsonString.trim()) {
      // Only show error if the textarea is not empty
      jsonValidationError = `${err}`;
    }
  }

  // Determine if save button should be disabled
  const disableSaveButton = !schemaJsonString.trim() || !!jsonValidationError;
  let buttonTooltip = '';

  if (!schemaJsonString.trim()) {
    buttonTooltip = 'Schema JSON cannot be empty';
  } else if (jsonValidationError) {
    buttonTooltip = `Invalid JSON: ${jsonValidationError}`;
  } else {
    buttonTooltip = 'Save JSON Schema';
  }
  // --- End Validation Logic ---

  return (
    <Drawer
      anchor="right"
      open={isOpen}
      onClose={onClose}
      sx={{
        '& .MuiDrawer-paper': {
          width: '500px', // Or adjust as needed
          marginTop: '60px', // Match FunctionDrawer style
        },
      }}>
      <Tailwind style={{height: 'calc(100% - 60px)'}}>
        <div className="flex h-full w-full flex-col gap-8 overscroll-y-auto p-12">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="text-xl font-semibold">Edit JSON Schema</div>
            <Button icon="close" variant="ghost" onClick={onClose} />
          </div>

          {/* Description */}
          <p>
            Define the JSON structure the model should follow in its response.
          </p>

          {/* Placeholder Button */}
          <Button
            variant="ghost"
            size="small"
            onClick={() => {
              try {
                // Prettify placeholder
                const parsed = JSON.parse(SCHEMA_PLACEHOLDER);
                setSchemaJsonString(JSON.stringify(parsed, null, 2));
              } catch {
                setSchemaJsonString(SCHEMA_PLACEHOLDER);
              }
            }}>
            Load placeholder
          </Button>

          {/* Text Area */}
          <StyledTextArea
            value={schemaJsonString}
            placeholder={SCHEMA_PLACEHOLDER}
            startHeight="100%"
            onChange={e => setSchemaJsonString(e.target.value)}
            className="!resize-none"
          />

          {/* Validation Error Alert */}
          {jsonValidationError && (
            <Alert severity="warning">
              Invalid JSON format: {jsonValidationError}
            </Alert>
          )}

          {/* Footer Buttons */}
          <div className="mt-auto flex justify-end gap-8">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleSave}
              disabled={disableSaveButton}
              tooltip={buttonTooltip}>
              Save Schema
            </Button>
          </div>
        </div>
      </Tailwind>
    </Drawer>
  );
};
