import {Box, Drawer} from '@mui/material';
import {MOON_200} from '@wandb/weave/common/css/color.styles';
import {Tag} from '@wandb/weave/components/Tag';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useState, useEffect, useCallback} from 'react';

import {Button} from '../../../../../Button';
import {ChoiceView} from './ChoiceView';
import {Choice} from './types';
import {ResizableDrawer} from '../common/ResizableDrawer';
import {Icon} from '@wandb/weave/components/Icon';

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
  const [width, setWidth] = useState(784);
  const [maxAllowedWidth, setMaxAllowedWidth] = useState(window.innerWidth - 73);

  useEffect(() => {
    const handleResize = () => {
      const newMaxWidth = window.innerWidth - 73;
      setMaxAllowedWidth(newMaxWidth);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const handleFullScreen = useCallback(() => {
    const newWidth = width === maxAllowedWidth ? 784 : maxAllowedWidth;
    setWidth(newWidth);
  }, [width, maxAllowedWidth]);

  return (
    <ResizableDrawer
      open={isDrawerOpen}
      onClose={() => setIsDrawerOpen(false)}
      defaultWidth={width}
      setWidth={setWidth}>
      <Box
        sx={{
          position: 'sticky',
          top: 0,
          zIndex: 20,
          pl: "16px",
          pr: "8px",
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
          Trials
        </Box>
        <Box sx={{display: 'flex', gap: 1}}>
          <Button
            size="medium"
            variant="ghost"
            icon="full-screen-mode-expand"
            onClick={handleFullScreen}
            tooltip={width === maxAllowedWidth ? "Exit full screen" : "Full screen"}
          />
          <Button
            size="medium"
            variant="ghost"
            icon="close"
            onClick={() => setIsDrawerOpen(false)}
            tooltip="Close"
          />
        </Box>
      </Box>
      <Tailwind>
        <div className="flex flex-col pt-[8px] pb-[16px] px-[16px] mb-[72px] gap-[16px]">
          {choices.map((c, index) => (
            <div key={index}>
              <div className="sticky top-[44px] flex items-center bg-white py-[8px] z-10">
                <p className="text-[14px] font-semibold mr-auto">Trial {index + 1}</p>
                {index === selectedChoiceIndex ? (
                  <div className="flex items-center gap-[2px]">
                    <Icon name="checkmark" className="ml-[4px] w-[16px] text-green-500" />
                    <span className="font-semibold text-sm">Response selected</span>
                  </div>
                ) : (
                  <Button
                    size="small"
                    variant="secondary"
                    icon="checkmark"
                    onClick={() => setSelectedChoiceIndex(index)}>
                    Select response
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
    </ResizableDrawer>
  );
};
