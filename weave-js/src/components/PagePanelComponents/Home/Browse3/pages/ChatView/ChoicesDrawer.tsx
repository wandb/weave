import {Box, Drawer} from '@mui/material';
import {MOON_200} from '@wandb/weave/common/css/color.styles';
import {Tag} from '@wandb/weave/components/Tag';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React from 'react';

import {Button} from '../../../../../Button';
import {ChoiceView} from './ChoiceView';
import {Choice} from './types';

type ChoicesDrawerProps = {
  choices: Choice[];
  isStructuredOutput?: boolean;
  isDrawerOpen: boolean;
  setIsDrawerOpen: React.Dispatch<React.SetStateAction<boolean>>;
  selectedChoiceIndex: number;
  setSelectedChoiceIndex: (choiceIndex: number) => void;
};

export const ChoicesDrawer = ({
  choices,
  isStructuredOutput,
  isDrawerOpen,
  setIsDrawerOpen,
  selectedChoiceIndex,
  setSelectedChoiceIndex,
}: ChoicesDrawerProps) => {
  return (
    <Drawer
      open={isDrawerOpen}
      onClose={() => setIsDrawerOpen(false)}
      title="Choices"
      anchor="right"
      sx={{
        '& .MuiDrawer-paper': {mt: '60px', width: '400px'},
      }}>
      <Box
        sx={{
          position: 'sticky',
          top: 0,
          zIndex: 1,
          px: 2,
          height: 44,
          width: '100%',
          borderBottom: `1px solid ${MOON_200}`,
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: 'white',
        }}>
        <Box
          sx={{
            height: 44,
            display: 'flex',
            alignItems: 'center',
            fontWeight: 600,
            fontSize: '1.25rem',
          }}>
          Responses
        </Box>
        <Button
          size="medium"
          variant="ghost"
          icon="close"
          onClick={() => setIsDrawerOpen(false)}
          tooltip="Close"
        />
      </Box>
      <Tailwind>
        <div className="flex flex-col p-12">
          {choices.map((c, index) => (
            <div key={index}>
              <div className="flex items-center gap-4 font-semibold">
                <Tag color="moon" label={`Response ${index + 1}`} />
                {index === selectedChoiceIndex ? (
                  <Button
                    className="text-green-500"
                    size="small"
                    variant="ghost"
                    icon="checkmark">
                    <span className="text-moon-500">Response selected</span>
                  </Button>
                ) : (
                  <Button
                    size="small"
                    variant="ghost"
                    icon="boolean"
                    onClick={() => setSelectedChoiceIndex(index)}>
                    <span className="text-moon-500">Select response</span>
                  </Button>
                )}
              </div>
              <ChoiceView
                choice={c}
                isStructuredOutput={isStructuredOutput}
                choiceIndex={index}
                isNested
              />
            </div>
          ))}
        </div>
      </Tailwind>
    </Drawer>
  );
};
