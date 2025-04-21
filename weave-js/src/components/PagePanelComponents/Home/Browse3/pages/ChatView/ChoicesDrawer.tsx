import {Box} from '@mui/material';
import {MOON_200} from '@wandb/weave/common/css/color.styles';
import {Icon} from '@wandb/weave/components/Icon';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useCallback, useEffect, useState} from 'react';

import {Button} from '../../../../../Button';
import {ResizableDrawer} from '../common/ResizableDrawer';
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
  const [width, setWidth] = useState(784);
  const [maxAllowedWidth, setMaxAllowedWidth] = useState(
    window.innerWidth - 73
  );

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
          pl: '16px',
          pr: '8px',
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
            tooltip={
              width === maxAllowedWidth ? 'Exit full screen' : 'Full screen'
            }
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
        <div className="mb-[72px] flex flex-col px-[16px] pb-[16px] pt-[8px]">
          {choices.map((c, index) => (
            <div key={index}>
              <div className="sticky top-[44px] z-10 flex items-center bg-white py-[8px]">
                <p className="mr-[8px] text-[14px] font-semibold">
                  Trial {index + 1}
                </p>
                {index === selectedChoiceIndex ? (
                  <div className="flex items-center gap-[2px]">
                    <Icon
                      name="checkmark"
                      className="ml-[4px] w-[16px] text-green-500"
                    />
                    <span className="text-sm font-semibold">
                      Response selected
                    </span>
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
              />
            </div>
          ))}
        </div>
      </Tailwind>
    </ResizableDrawer>
  );
};
