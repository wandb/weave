import {
  Dialog,
  DialogActions as MaterialDialogActions,
  DialogContent,
  DialogTitle,
} from '@material-ui/core';
import {Box} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
import {Tag} from '@wandb/weave/components/Tag';
import React, {useState} from 'react';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import {CopyableId} from '../../common/Id';
import {LLMMaxTokensKey} from '../llmMaxTokens';
import {OptionalTraceCallSchema, PlaygroundState} from '../types';
import {DEFAULT_SYSTEM_MESSAGE} from '../usePlaygroundState';
import {LLMDropdown} from './LLMDropdown';
import {SetPlaygroundStateFieldFunctionType} from './useChatFunctions';

type PlaygroundChatTopBarProps = {
  idx: number;
  settingsTab: number | null;
  setSettingsTab: (tab: number | null) => void;
  setPlaygroundStateField: SetPlaygroundStateFieldFunctionType;
  entity: string;
  project: string;
  playgroundStates: PlaygroundState[];
  setPlaygroundStates: (playgroundStates: PlaygroundState[]) => void;
  agentdome?: boolean;
};

const DialogActions = styled(MaterialDialogActions)<{$align: string}>`
  justify-content: ${({$align}) =>
    $align === 'left' ? 'flex-start' : 'flex-end'} !important;
  padding: 32px 32px 32px 32px !important;
`;
DialogActions.displayName = 'S.DialogActions';

export const PlaygroundChatTopBar: React.FC<PlaygroundChatTopBarProps> = ({
  idx,
  settingsTab,
  setSettingsTab,
  setPlaygroundStateField,
  entity,
  project,
  playgroundStates,
  setPlaygroundStates,
  agentdome,
}) => {
  const history = useHistory();
  const isLastChat = idx === playgroundStates.length - 1;
  const onlyOneChat = playgroundStates.length === 1;
  const [confirmClear, setConfirmClear] = useState(false);

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
    model: LLMMaxTokensKey,
    maxTokens: number
  ) => {
    setPlaygroundStateField(index, 'model', model);
    setPlaygroundStateField(index, 'maxTokensLimit', maxTokens);
    setPlaygroundStateField(index, 'maxTokens', Math.floor(maxTokens / 2));
  };

  const ConfirmClearModal: React.FC<{
    open: boolean;
    onClose: () => void;
    onConfirm: () => void;
  }> = ({open, onClose, onConfirm}) => {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
        <DialogTitle>Clear chat history</DialogTitle>
        <DialogContent style={{overflow: 'hidden'}}>
          <p>Are you sure you want to clear the chat history?</p>
        </DialogContent>
        <DialogActions $align="left">
          <Button variant="destructive" onClick={onConfirm}>
            Clear history
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </DialogActions>
      </Dialog>
    );
  };

  return (
    <Box
      sx={{
        width: '100%',
        display: 'flex',
        justifyContent: 'space-between',
      }}>
      <Box
        sx={{
          display: 'flex',
          gap: '8px',
          alignItems: 'center',
          backgroundColor: 'transparent',
        }}>
        {(!onlyOneChat || agentdome) && <Tag label={`${idx + 1}`} />}
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
          backgroundColor: 'transparent',
        }}>
        <Button
          tooltip={'Clear chat'}
          icon="sweeps-broom"
          size="medium"
          variant="ghost"
          onClick={() => setConfirmClear(true)}
        />
        {!agentdome &&
          (onlyOneChat ? (
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
              }}></Button>
          ))}
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
      <ConfirmClearModal
        open={confirmClear}
        onClose={() => setConfirmClear(false)}
        onConfirm={() => {
          clearCall(idx);
          setConfirmClear(false);
        }}
      />
    </Box>
  );
};
