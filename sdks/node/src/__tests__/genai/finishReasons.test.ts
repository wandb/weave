import {
  finishReasonsFromResponses,
  normalizeFinishReason,
} from '../../genai/finishReasons';
import type {Message} from '../../genai/types';

describe('normalizeFinishReason', () => {
  it.each([
    ['stop', 'stop'],
    ['end_turn', 'stop'],
    ['STOP', 'stop'],
    ['length', 'length'],
    ['max_tokens', 'length'],
    ['max_output_tokens', 'length'],
    ['tool_calls', 'tool_call'],
    ['toolUse', 'tool_call'],
    ['tool_use', 'tool_call'],
    ['SAFETY', 'content_filter'],
    ['refusal', 'content_filter'],
    ['error', 'error'],
    ['aborted', 'aborted'],
  ])('maps %s to %s', (input, expected) => {
    expect(normalizeFinishReason(input)).toBe(expected);
  });
});

describe('finishReasonsFromResponses', () => {
  const messages: Message[] = [
    {
      role: 'assistant',
      parts: [{type: 'tool_call', toolCallId: 'c1', toolName: 'f'}],
    },
    {role: 'tool', parts: [{type: 'tool_result', toolCallId: 'c1'}]},
    {role: 'assistant', content: 'done'},
  ];

  it('emits one reason per output message for a completed response', () => {
    expect(
      finishReasonsFromResponses('completed', undefined, messages)
    ).toEqual(['tool_call', 'stop', 'stop']);
  });

  it('marks the last message with the incomplete reason', () => {
    expect(
      finishReasonsFromResponses('incomplete', 'max_output_tokens', messages)
    ).toEqual(['tool_call', 'stop', 'length']);
  });

  it('marks the last message of a failed response as error', () => {
    expect(finishReasonsFromResponses('failed', null, messages)).toEqual([
      'tool_call',
      'stop',
      'error',
    ]);
  });

  it('returns nothing when there are no output messages', () => {
    expect(finishReasonsFromResponses('completed', undefined, [])).toEqual([]);
  });
});
