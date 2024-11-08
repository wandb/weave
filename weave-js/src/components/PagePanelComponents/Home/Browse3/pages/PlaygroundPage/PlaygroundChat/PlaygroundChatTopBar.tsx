import {Box} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
import {Tag} from '@wandb/weave/components/Tag';
import React from 'react';
import {useHistory} from 'react-router-dom';

import {CopyableId} from '../../common/Id';
import {OptionalTraceCallSchema, PlaygroundState} from '../types';
import {DEFAULT_SYSTEM_MESSAGE} from '../usePlaygroundState';
import {LLMDropdown} from './LLMDropdown';

type PlaygroundChatTopBarProps = {
  idx: number;
  settingsTab: number | null;
  setSettingsTab: (tab: number | null) => void;
  setPlaygroundStateField: (
    index: number,
    field: keyof PlaygroundState,
    value: any
  ) => void;
  entity: string;
  project: string;
  playgroundStates: PlaygroundState[];
  setPlaygroundStates: (playgroundStates: PlaygroundState[]) => void;
};

export const PlaygroundChatTopBar: React.FC<PlaygroundChatTopBarProps> = ({
  idx,
  settingsTab,
  setSettingsTab,
  setPlaygroundStateField,
  entity,
  project,
  playgroundStates,
  setPlaygroundStates,
}) => {
  const history = useHistory();
  const isLastChat = idx === playgroundStates.length - 1;
  const onlyOneChat = playgroundStates.length === 1;

  const clearCall = (index: number) => {
    history.push(`/${entity}/${project}/weave/playground`);
    setPlaygroundStateField(index, 'traceCall', {
      project_id: `${entity}/${project}`,
      id: '',
      inputs: {
        messages: [DEFAULT_SYSTEM_MESSAGE],
      },
    } as OptionalTraceCallSchema);
  };

  const handleCompare = () => {
    if (onlyOneChat) {
      setPlaygroundStates([
        ...playgroundStates,
        JSON.parse(JSON.stringify(playgroundStates[0])),
      ]);
    }
  };

  const handleModelChange = (
    index: number,
    model: string,
    maxTokens: number
  ) => {
    setPlaygroundStateField(index, 'model', model);
    setPlaygroundStateField(index, 'maxTokensLimit', maxTokens);
    setPlaygroundStateField(index, 'maxTokens', maxTokens / 2);
  };

  return (
    <Box
      sx={{
        width: '100%',
        display: 'flex',
        justifyContent: 'space-between',
        paddingBottom: '8px',
      }}>
      <Box
        sx={{
          display: 'flex',
          gap: '8px',
          alignItems: 'center',
          backgroundColor: 'white',
        }}>
        {!onlyOneChat && <Tag label={`${idx + 1}`} />}
        <LLMDropdown
          value={playgroundStates[idx].model}
          onChange={(model, maxTokens) =>
            handleModelChange(idx, model, maxTokens)
          }
        />
        {playgroundStates[idx].traceCall?.id && (
          <CopyableId id={playgroundStates[idx]!.traceCall!.id!} type="Call" />
        )}
      </Box>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          backgroundColor: 'white',
        }}>
        <Button
          tooltip={'Clear chat'}
          icon="sweeps-broom"
          size="medium"
          variant="ghost"
          onClick={() => clearCall(idx)}
        />
        {onlyOneChat ? (
          <Button
            tooltip={'Add chat'}
            endIcon="swap"
            size="medium"
            variant="ghost"
            onClick={handleCompare}>
            Compare
          </Button>
        ) : (
          <Button
            tooltip={'Remove chat'}
            endIcon="close"
            size="medium"
            variant="ghost"
            onClick={() => {
              if (settingsTab === idx) {
                setSettingsTab(0);
              }
              setPlaygroundStates(
                playgroundStates.filter((_, index) => index !== idx)
              );
            }}>
            Remove
          </Button>
        )}
        {isLastChat && (
          <Button
            tooltip={'Chat settings'}
            icon="settings-parameters"
            size="medium"
            variant="ghost"
            active={settingsTab !== null}
            onClick={() => {
              if (settingsTab !== null) {
                setSettingsTab(null);
              } else {
                setSettingsTab(idx);
              }
            }}
          />
        )}
      </Box>
    </Box>
  );
};
