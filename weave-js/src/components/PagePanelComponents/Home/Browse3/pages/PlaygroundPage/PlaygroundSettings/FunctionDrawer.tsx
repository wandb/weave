import {Drawer} from '@mui/material';
import {Alert} from '@wandb/weave/components/Alert';
import {Button} from '@wandb/weave/components/Button';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useEffect, useState} from 'react';

import {StyledTextArea} from '../../../StyledTextarea';

type FunctionDrawerProps = {
  drawerFunctionIndex: number | null;
  onClose: () => void;
  functions: Array<{name: string; [key: string]: any}>;
  onAddFunction: (functionJSON: string, index: number) => void;
};

const FUNCTION_PLACEHOLDER = `{
  "name": "get_stock_price",
  "description": "Get the current stock price",
  "strict": true,
  "parameters": {
    "type": "object",
    "properties": {
      "symbol": {
        "type": "string",
        "description": "The stock symbol"
      }
    },
    "additionalProperties": false,
    "required": [
      "symbol"
    ]
  }
}`;

export const FunctionDrawer: React.FC<FunctionDrawerProps> = ({
  drawerFunctionIndex,
  onClose,
  onAddFunction,
  functions,
}) => {
  const isUpdating =
    drawerFunctionIndex !== null && drawerFunctionIndex < functions.length;
  const [functionJSON, setFunctionJSON] = useState(
    drawerFunctionIndex !== null
      ? JSON.stringify(functions[drawerFunctionIndex], null, 2) ?? ''
      : ''
  );

  // if updating, set the function JSON to current function
  useEffect(() => {
    setFunctionJSON(
      isUpdating
        ? JSON.stringify(functions[drawerFunctionIndex], null, 2) ?? ''
        : ''
    );
  }, [drawerFunctionIndex, isUpdating, functions]);

  const handleAddFunction = () => {
    if (drawerFunctionIndex !== null) {
      onAddFunction(functionJSON, drawerFunctionIndex);
    }
    setFunctionJSON('');
    onClose();
  };

  let jsonValidationError = null;
  let parsedFunctionJSON: Record<string, any> | null = null;
  try {
    parsedFunctionJSON = JSON.parse(functionJSON);
    JSON.stringify(parsedFunctionJSON, null, 2);
  } catch (err) {
    jsonValidationError = `${err}`;
  }

  let disableActionButton = true;
  let buttonTooltip = '';

  if (functionJSON.length === 0 || !functionJSON.trim()) {
    buttonTooltip = 'Function JSON is empty';
  } else if (!!jsonValidationError) {
    buttonTooltip = jsonValidationError;
  } else if (
    typeof parsedFunctionJSON?.name !== 'string' ||
    !parsedFunctionJSON?.name
  ) {
    buttonTooltip = 'Function JSON has no name';
  } else if (
    drawerFunctionIndex !== null &&
    functions.some(
      (func, idx) =>
        parsedFunctionJSON?.name &&
        func.name === parsedFunctionJSON.name &&
        idx !== drawerFunctionIndex
    )
  ) {
    buttonTooltip = 'Function with this name already exists';
  } else {
    disableActionButton = false;
    buttonTooltip = `${isUpdating ? 'Update' : 'Add'} function`;
  }

  return (
    <Drawer
      anchor="right"
      open={drawerFunctionIndex !== null}
      onClose={onClose}
      sx={{
        '& .MuiDrawer-paper': {
          width: '500px',
          marginTop: '60px',
        },
      }}>
      <Tailwind style={{height: 'calc(100% - 60px)'}}>
        <div className="flex h-full w-full flex-col gap-8 overscroll-y-auto p-12">
          <div className="flex items-center justify-between">
            <div className="text-xl font-semibold">Add Function</div>
            <Button icon="close" variant="ghost" onClick={onClose} />
          </div>
          <p>
            The model will intelligently decide to call functions based on input
            it receives from the user.
          </p>
          <Button
            variant="ghost"
            size="small"
            onClick={() => setFunctionJSON(FUNCTION_PLACEHOLDER)}>
            Load placeholder
          </Button>
          <StyledTextArea
            value={functionJSON}
            placeholder={FUNCTION_PLACEHOLDER}
            startHeight="100%"
            onChange={e => setFunctionJSON(e.target.value)}
            className="!resize-none"
          />
          {jsonValidationError && functionJSON.length > 0 && (
            <Alert severity="warning">
              Value is not valid JSON: {jsonValidationError}
            </Alert>
          )}
          <div className="mt-auto flex justify-end gap-8">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleAddFunction}
              disabled={disableActionButton}
              tooltip={buttonTooltip}>
              {isUpdating ? 'Update' : 'Add'}
            </Button>
          </div>
        </div>
      </Tailwind>
    </Drawer>
  );
};
