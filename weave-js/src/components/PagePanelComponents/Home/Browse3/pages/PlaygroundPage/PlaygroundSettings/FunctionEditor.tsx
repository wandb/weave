import {Box, Chip} from '@mui/material';
import {styled} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
import React, {useState} from 'react';

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
  functions: Array<{name: string; [key: string]: any}>;
  setFunctions: React.Dispatch<
    React.SetStateAction<Array<{name: string; [key: string]: any}>>
  >;
};

export const FunctionEditor: React.FC<FunctionEditorProps> = ({
  functions,
  setFunctions,
}) => {
  // null means the drawer is closed
  const [drawerFunctionIndex, setDrawerFunctionIndex] = useState<number | null>(
    null
  );

  const handleAddFunction = (functionJSON: string, index: number) => {
    try {
      const json = JSON.parse(functionJSON);
      if (
        typeof json === 'object' &&
        json !== null &&
        'name' in json &&
        (functions[index] || functions.every(func => func.name !== json.name))
      ) {
        setFunctions(prevFunctions => {
          const newFunctions = [...prevFunctions];
          if (index < newFunctions.length) {
            newFunctions[index] = json;
          } else {
            newFunctions.push(json);
          }
          return newFunctions;
        });
      } else {
        console.error('Function JSON must have a name property');
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
        gap: '8px',
      }}>
      <span>Functions</span>
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
