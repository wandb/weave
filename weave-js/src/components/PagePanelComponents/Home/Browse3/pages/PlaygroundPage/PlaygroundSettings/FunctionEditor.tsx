import {Box, Chip, Tooltip} from '@mui/material';
import {styled} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
import {Icon} from '@wandb/weave/components/Icon';
import React, {useState} from 'react';

import {useMakeFunctionSpec} from '../../AgentdomePage/tsFunctionSpecs';
import {projectIdFromParts} from '../../wfReactInterface/tsDataModelHooks';
import {LLM_MAX_TOKENS} from '../llmMaxTokens';
import {PlaygroundState} from '../types';
import {FunctionDrawer} from './FunctionDrawer';

const StyledChip = styled(Chip)(({theme}) => ({
  cursor: 'pointer',
  width: '100%',
  justifyContent: 'space-between',
  '& .MuiChip-label': {
    paddingLeft: 8,
    paddingRight: 0,
    flex: 1,
    textAlign: 'left',
  },
  '& .MuiChip-deleteIcon': {
    marginRight: 8,
    marginLeft: 'auto',
  },
}));

type FunctionEditorProps = {
  entity: string;
  project: string;
  playgroundState: PlaygroundState;
  functions: Array<{name: string; [key: string]: any}>;
  setFunctions: React.Dispatch<
    React.SetStateAction<Array<{name: string; [key: string]: any}>>
  >;
};

export const FunctionEditor: React.FC<FunctionEditorProps> = ({
  entity,
  project,
  playgroundState,
  functions,
  setFunctions,
}) => {
  // null means the drawer is closed
  const [drawerFunctionIndex, setDrawerFunctionIndex] = useState<number | null>(
    null
  );
  const createFunctionSpec = useMakeFunctionSpec();

  const handleAddFunction = (functionJSON: string, index: number) => {
    try {
      const json = JSON.parse(functionJSON);
      if (typeof json === 'object') {
        setFunctions(
          (prevFunctions: Array<{name: string; [key: string]: any}>) => {
            const newFunctions = [...prevFunctions];
            if (index < newFunctions.length) {
              newFunctions[index] = json;
            } else {
              newFunctions.push(json);
            }
            return newFunctions;
          }
        );
        const name = json?.name;
        if (!name) {
          throw new Error('Function name is required');
        }
        createFunctionSpec({
          obj: {
            project_id: projectIdFromParts({entity, project}),
            object_id: name,
            val: json,
          },
        });
      }
    } catch (err) {
      console.error('Error parsing function json', err);
    }
  };

  const handleDeleteFunction = (functionToDelete: string) => {
    setFunctions(functions.filter(func => func.name !== functionToDelete));
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
      }}>
      <Box
        sx={{
          display: 'flex',
          gap: '4px',
          fontSize: '14px',
          alignItems: 'center',
        }}>
        Functions
        {!LLM_MAX_TOKENS[playgroundState.model]?.supports_function_calling && (
          <Tooltip title="This model does not support functions">
            <span>
              <Icon name="warning" className="text-sienna-500" />
            </span>
          </Tooltip>
        )}
      </Box>
      {functions.length > 0 && (
        <Box sx={{display: 'flex', flexDirection: 'column', gap: 1}}>
          {functions.map((func, index) => (
            <StyledChip
              key={index}
              label={func.name}
              onDelete={() => handleDeleteFunction(func.name)}
              size="small"
              onClick={() => setDrawerFunctionIndex(index)}
            />
          ))}
        </Box>
      )}
      <Button
        startIcon="add-new"
        variant="secondary"
        className="w-full"
        onClick={() => setDrawerFunctionIndex(functions.length)}>
        Add function
      </Button>

      <FunctionDrawer
        drawerFunctionIndex={drawerFunctionIndex}
        onClose={() => setDrawerFunctionIndex(null)}
        onAddFunction={handleAddFunction}
        functions={functions}
      />
    </Box>
  );
};
