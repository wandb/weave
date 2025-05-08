import {
  Dialog,
  DialogActions as MaterialDialogActions,
  DialogContent,
  DialogTitle,
} from '@material-ui/core';
import {Button} from '@wandb/weave/components/Button';
import {Tag} from '@wandb/weave/components/Tag';
import React, {useState} from 'react';
import {useHistory} from 'react-router-dom';
import styled from 'styled-components';

import {CopyableId} from '../../common/Id';
import {TraceObjSchemaForBaseObjectClass} from '../../wfReactInterface/objectClassQuery';
import {LLMMaxTokensKey} from '../llmMaxTokens';
import {
  OptionalTraceCallSchema,
  PlaygroundState,
  SavedPlaygroundModelState,
} from '../types';
import {
  DEFAULT_SAVED_MODEL,
  DEFAULT_SYSTEM_MESSAGE,
} from '../usePlaygroundState';
import {LLMDropdown} from './LLMDropdown';
import {ProviderOption} from './LLMDropdownOptions';
import {
  SetPlaygroundStateFieldFunctionType,
  TraceCallOutput,
} from './useChatFunctions';

type PlaygroundChatTopBarProps = {
  idx: number;
  settingsTab: number | null;
  setSettingsTab: (tab: number | null) => void;
  setPlaygroundStateField: SetPlaygroundStateFieldFunctionType;
  entity: string;
  project: string;
  playgroundStates: PlaygroundState[];
  setPlaygroundStates: (playgroundStates: PlaygroundState[]) => void;
  isTeamAdmin: boolean;
  refetchConfiguredProviders: () => void;
  refetchCustomLLMs: () => void;
  llmDropdownOptions: ProviderOption[];
  areProvidersLoading: boolean;
  customProvidersResult: TraceObjSchemaForBaseObjectClass<'Provider'>[];
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
  isTeamAdmin,
  refetchConfiguredProviders,
  refetchCustomLLMs,
  llmDropdownOptions,
  areProvidersLoading,
  customProvidersResult,
}) => {
  const history = useHistory();
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

  const handleModelChange = (
    index: number,
    model: LLMMaxTokensKey,
    maxTokens: number,
    savedModel?: SavedPlaygroundModelState
  ) => {
    if (!savedModel) {
      setPlaygroundStates(
        playgroundStates.map((state, i) => {
          if (i === index) {
            return {
              ...state,
              model,
              maxTokensLimit: maxTokens,
              maxTokens: Math.floor(maxTokens / 2),
            };
          }
          return state;
        })
      );
      return;
    }

    const {messagesTemplate, ...defaultParams} =
      savedModel?.savedModelParams ?? {};

    setPlaygroundStates(
      playgroundStates.map((state, i) => {
        if (i === index) {
          return {
            ...state,
            model,
            maxTokensLimit: maxTokens,
            maxTokens: Math.floor(maxTokens / 2),

            // Update the state to show we are using a saved model
            savedModel: savedModel ?? DEFAULT_SAVED_MODEL,
            traceCall: {
              ...state.traceCall,
              inputs: {
                ...state.traceCall?.inputs,
                // If the saved model has messages, use them, otherwise use the current messages
                messages: messagesTemplate ?? state.traceCall?.inputs?.messages,
              },
              output: {
                ...(state.traceCall?.output as TraceCallOutput),
                // If the saved model has messages, clear the choices, otherwise use the current choices
                choices: messagesTemplate
                  ? undefined
                  : (state.traceCall?.output as TraceCallOutput)?.choices,
              },
            },
            // Update the other params
            ...defaultParams,
          };
        }
        return state;
      })
    );
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
    <div className="flex w-full justify-between">
      <div className="flex items-center gap-8 bg-transparent">
        <Tag label={`${idx + 1}`} />
        <LLMDropdown
          value={playgroundStates[idx].model}
          onChange={(model, maxTokens, savedModel) =>
            handleModelChange(
              idx,
              model as LLMMaxTokensKey,
              maxTokens,
              savedModel
            )
          }
          entity={entity}
          project={project}
          isTeamAdmin={isTeamAdmin}
          refetchConfiguredProviders={refetchConfiguredProviders}
          refetchCustomLLMs={refetchCustomLLMs}
          llmDropdownOptions={llmDropdownOptions}
          areProvidersLoading={areProvidersLoading}
          customProvidersResult={customProvidersResult}
        />
        {playgroundStates[idx].traceCall?.id && (
          <CopyableId id={playgroundStates[idx]!.traceCall!.id!} type="Call" />
        )}
        <Button
          tooltip={'Chat settings'}
          icon="settings-parameters"
          size="medium"
          variant="ghost"
          active={settingsTab === idx}
          onClick={() => {
            if (settingsTab === idx) {
              setSettingsTab(null);
            } else {
              setSettingsTab(idx);
            }
          }}
        />
      </div>
      <div className="flex items-center gap-4 bg-transparent">
        <Button
          tooltip={'Clear chat'}
          icon="randomize-reset-reload"
          size="medium"
          variant="ghost"
          onClick={() => setConfirmClear(true)}
        />

        <Button
          endIcon="close"
          size="medium"
          variant="ghost"
          disabled={onlyOneChat}
          tooltip={onlyOneChat ? 'Cannot remove last chat' : 'Remove chat'}
          onClick={() => {
            // If the settings tab is set to length that is going to be removed,
            // we need to set the settings tab to the previous chat.
            if (settingsTab && settingsTab < playgroundStates.length + 1) {
              setSettingsTab(settingsTab - 1);
            }
            setPlaygroundStates(
              playgroundStates.filter((_, index) => index !== idx)
            );
          }}
        />
      </div>
      <ConfirmClearModal
        open={confirmClear}
        onClose={() => setConfirmClear(false)}
        onConfirm={() => {
          clearCall(idx);
          setConfirmClear(false);
        }}
      />
    </div>
  );
};
