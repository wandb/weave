import Box from '@mui/material/Box';
import {MOON_250} from '@wandb/weave/common/css/color.styles';
import {Switch} from '@wandb/weave/components';
import * as Tabs from '@wandb/weave/components/Tabs';
import {Tag} from '@wandb/weave/components/Tag';
import React, {SetStateAction} from 'react';

import {PlaygroundState, PlaygroundStateKey} from '../types';

export type PlaygroundSettingsProps = {
  playgroundStates: PlaygroundState[];
  setPlaygroundStateField: (
    index: number,
    field: PlaygroundStateKey,
    value: SetStateAction<PlaygroundState[PlaygroundStateKey]>
  ) => void;
  settingsTab: number;
  setSettingsTab: (tab: number) => void;
};

export const PlaygroundSettings: React.FC<PlaygroundSettingsProps> = ({
  playgroundStates,
  setPlaygroundStateField,
  settingsTab,
  setSettingsTab,
}) => {
  return (
    <Box
      sx={{
        padding: '16px',
        height: '100%',
        borderLeft: `1px solid ${MOON_250}`,
        display: 'flex',
        flexDirection: 'column',
        width: '320px',
        overflowY: 'scroll',
        flexShrink: 0,
      }}>
      <Tabs.Root value={settingsTab.toString()}>
        <Tabs.List>
          {playgroundStates.map((state, idx) => (
            <Tabs.Trigger
              key={idx}
              value={idx.toString()}
              onClick={() => setSettingsTab(idx)}
              className="max-w-[120px]">
              {playgroundStates.length > 1 && <Tag label={`${idx + 1}`} />}
              <span className="truncate">{state.model}</span>
            </Tabs.Trigger>
          ))}
        </Tabs.List>
        {playgroundStates.map((playgroundState, idx) => (
          <Tabs.Content key={idx} value={idx.toString()}>
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
                mt: 2,
              }}>
              <Box
                sx={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}>
                <label
                  className="cursor-pointer"
                  htmlFor="trackWithWeaveSwitch">
                  Track this LLM call with Weave
                </label>
                <Switch.Root
                  id="trackWithWeaveSwitch"
                  size="small"
                  checked={playgroundStates[idx].trackLLMCall}
                  onCheckedChange={() =>
                    setPlaygroundStateField(
                      idx,
                      'trackLLMCall',
                      !playgroundStates[idx].trackLLMCall
                    )
                  }>
                  <Switch.Thumb
                    size="small"
                    checked={playgroundStates[idx].trackLLMCall}
                  />
                </Switch.Root>
              </Box>
            </Box>
          </Tabs.Content>
        ))}
      </Tabs.Root>
    </Box>
  );
};
