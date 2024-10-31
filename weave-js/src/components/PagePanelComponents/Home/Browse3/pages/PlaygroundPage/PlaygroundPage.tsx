import {Box} from '@mui/material';
import {WeaveLoader} from '@wandb/weave/common/components/WeaveLoader';
import React, {
  SetStateAction,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';

import {SimplePageLayout} from '../common/SimplePageLayout';
import {useWFHooks} from '../wfReactInterface/context';
import {
  OptionalCallSchema,
  PlaygroundChat,
} from './PlaygroundChat/PlaygroundChat';
import {
  PlaygroundSettings,
  PlaygroundState,
} from './PlaygroundSettings/PlaygroundSettings';
import {PlaygroundResponseFormats} from './PlaygroundSettings/ResponseFormatEditor';

export type PlaygroundPageProps = {
  entity: string;
  project: string;
  callId: string;
};

type PlaygroundStateKey = keyof PlaygroundState;
type TraceCallOutput = {
  choices?: any[];
};

export const PlaygroundPage = (props: PlaygroundPageProps) => {
  return (
    <SimplePageLayout
      title={'Playground'}
      hideTabsIfSingle
      tabs={[
        {
          label: 'main',
          content: <PlaygroundPageInner {...props} />,
        },
      ]}
    />
  );
};

export const PlaygroundPageInner = (props: PlaygroundPageProps) => {
  const [settingsTab, setSettingsTab] = useState<number | null>(null);
  const [playgroundStates, setPlaygroundStates] = useState<PlaygroundState[]>([
    {
      loading: false,
      functions: [],
      responseFormat: PlaygroundResponseFormats.Text,
      temperature: 1,
      maxTokens: 4000,
      stopSequences: [],
      topP: 1,
      frequencyPenalty: 0,
      presencePenalty: 0,
      nTimes: 1,
      maxTokensLimit: 16000,
      model: 'gpt-4o-mini',
    },
  ]);

  const setPlaygroundStateField = useCallback(
    (
      index: number,
      key: PlaygroundStateKey,
      value:
        | PlaygroundState[PlaygroundStateKey]
        | SetStateAction<Array<{[key: string]: any; name: string}>>
        | SetStateAction<PlaygroundResponseFormats>
        | SetStateAction<number>
        | SetStateAction<string[]>
    ) => {
      setPlaygroundStates(prevStates =>
        prevStates.map((state, i) =>
          i === index
            ? {
                ...state,
                [key]:
                  typeof value === 'function'
                    ? (value as SetStateAction<any>)(state[key])
                    : value,
              }
            : state
        )
      );
    },
    []
  );

  const {useCall} = useWFHooks();
  const call = useCall(
    useMemo(() => {
      return props.callId
        ? {
            entity: props.entity,
            project: props.project,
            callId: props.callId,
          }
        : null;
    }, [props.entity, props.project, props.callId])
  );

  const [calls, setCalls] = useState<OptionalCallSchema[]>([]);

  const deleteMessage = (callIndex: number, messageIndex: number) => {
    setCalls(prevCalls => {
      const updatedCalls = [...prevCalls];
      const newCall = clearTraceCallId(updatedCalls[callIndex]);
      if (newCall && newCall.traceCall?.inputs?.messages) {
        newCall.traceCall.inputs.messages =
          newCall.traceCall.inputs.messages.filter(
            (_: any, index: number) => index !== messageIndex
          );

        if (newCall.traceCall.inputs.messages.length === 0) {
          newCall.traceCall.inputs.messages = [
            {
              role: 'system',
              content: 'You are a helpful assistant.',
            },
          ];
        }
      }
      return updatedCalls;
    });
  };

  const editMessage = (
    callIndex: number,
    messageIndex: number,
    newMessage: any // Replace 'any' with the appropriate type for a message
  ) => {
    setCalls(prevCalls => {
      const updatedCalls = [...prevCalls];
      const newCall = clearTraceCallId(updatedCalls[callIndex]);
      if (newCall && newCall.traceCall?.inputs?.messages) {
        newCall.traceCall.inputs.messages[messageIndex] = newMessage;
      }
      return updatedCalls;
    });
  };

  const addMessage = (callIndex: number, newMessage: any) => {
    setCalls(prevCalls => {
      const updatedCalls = [...prevCalls];
      const newCall = clearTraceCallId(updatedCalls[callIndex]);
      if (newCall && newCall.traceCall?.inputs?.messages) {
        if (
          newCall.traceCall.output &&
          (newCall.traceCall.output as TraceCallOutput).choices &&
          Array.isArray((newCall.traceCall.output as TraceCallOutput).choices)
        ) {
          (newCall.traceCall.output as TraceCallOutput).choices!.forEach(
            (choice: any) => {
              if (choice.message) {
                newCall.traceCall?.inputs!.messages.push(choice.message);
              }
            }
          );
          (newCall.traceCall.output as TraceCallOutput).choices = undefined;
        }
        newCall.traceCall.inputs.messages.push(newMessage);
      }
      return updatedCalls;
    });
  };

  const deleteChoice = (callIndex: number, choiceIndex: number) => {
    setCalls(prevCalls => {
      const updatedCalls = [...prevCalls];
      const newCall = clearTraceCallId(updatedCalls[callIndex]);
      const output = newCall?.traceCall?.output as TraceCallOutput;
      if (output && Array.isArray(output.choices)) {
        output.choices = output.choices.filter(
          (_, index: number) => index !== choiceIndex
        );
        if (newCall && newCall.traceCall) {
          newCall.traceCall.output = output;
          updatedCalls[callIndex] = newCall;
        }
      }
      return updatedCalls;
    });
  };

  const editChoice = (
    callIndex: number,
    choiceIndex: number,
    newChoice: any
  ) => {
    setCalls(prevCalls => {
      const updatedCalls = [...prevCalls];
      const newCall = clearTraceCallId(updatedCalls[callIndex]);
      if (
        newCall?.traceCall?.output &&
        Array.isArray((newCall.traceCall.output as TraceCallOutput).choices)
      ) {
        // Delete the old choice
        (newCall.traceCall.output as TraceCallOutput).choices = (
          newCall.traceCall.output as TraceCallOutput
        ).choices!.filter((_, index) => index !== choiceIndex);

        // Add the new choice as a message
        newCall.traceCall.inputs = newCall.traceCall.inputs ?? {};
        newCall.traceCall.inputs.messages =
          newCall.traceCall.inputs.messages ?? [];
        newCall.traceCall.inputs.messages.push({
          role: 'assistant',
          content: newChoice.message?.content || newChoice.content,
        });
      }
      return updatedCalls;
    });
  };

  const setPlaygroundStateFromInputs = useCallback(
    (inputs: Record<string, any>) => {
      // https://docs.litellm.ai/docs/completion/input
      // pulled from litellm
      setPlaygroundStates(prevState => {
        const newState = {...prevState[0]};
        if (inputs.tools) {
          newState.functions = [];
          for (const tool of inputs.tools) {
            if (tool.type === 'function') {
              newState.functions = [...newState.functions, tool.function];
            }
          }
        }
        if (inputs.n) {
          newState.nTimes = parseInt(inputs.n, 10);
        }
        if (inputs.temperature) {
          newState.temperature = parseFloat(inputs.temperature);
        }
        if (inputs.response_format) {
          newState.responseFormat = inputs.response_format.type;
        }
        if (inputs.top_p) {
          newState.topP = parseFloat(inputs.top_p);
        }
        if (inputs.frequency_penalty) {
          newState.frequencyPenalty = parseFloat(inputs.frequency_penalty);
        }
        if (inputs.presence_penalty) {
          newState.presencePenalty = parseFloat(inputs.presence_penalty);
        }
        return [newState];
      });
    },
    []
  );

  const clearTraceCallId = (callWithTraceCallId: OptionalCallSchema) => {
    if (callWithTraceCallId.traceCall) {
      callWithTraceCallId.traceCall.id = '';
    }
    return callWithTraceCallId;
  };

  useEffect(() => {
    if (!call.loading && call.result) {
      setCalls([call.result]);
      if (call.result.traceCall?.inputs) {
        setPlaygroundStateFromInputs(call.result.traceCall.inputs);
      }
    } else if (calls.length === 0) {
      setCalls([
        {
          entity: props.entity,
          project: props.project,
          traceCall: {
            inputs: {
              messages: [
                {
                  role: 'system',
                  content: 'You are a helpful assistant.',
                },
              ],
            },
          },
        },
      ]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    call,
    props.entity,
    props.project,
    setPlaygroundStateFromInputs,
    // calls.length,
  ]);

  return (
    <Box
      sx={{
        display: 'flex',
        height: '100%',
        width: '100%',
      }}>
      {call.loading ? (
        <Box
          sx={{
            display: 'flex',
            height: '100%',
            width: '100%',
          }}>
          <WeaveLoader />
        </Box>
      ) : (
        <PlaygroundChat
          setCalls={setCalls}
          calls={calls}
          deleteMessage={deleteMessage}
          editMessage={editMessage}
          deleteChoice={deleteChoice}
          editChoice={editChoice}
          addMessage={addMessage}
          playgroundStates={playgroundStates}
          setPlaygroundStates={setPlaygroundStates}
          setPlaygroundStateField={setPlaygroundStateField}
          entity={props.entity}
          project={props.project}
          setSettingsTab={setSettingsTab}
          settingsTab={settingsTab}
        />
      )}
      {settingsTab !== null && (
        <PlaygroundSettings
          playgroundStates={playgroundStates}
          setPlaygroundStateField={setPlaygroundStateField}
          settingsTab={settingsTab}
          setSettingsTab={setSettingsTab}
        />
      )}
    </Box>
  );
};
