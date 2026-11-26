import {serializeMessages, toWireMessage} from '../../genai/serialize';

describe('toWireMessage', () => {
  it('wraps flat content in a text part', () => {
    expect(toWireMessage({role: 'user', content: 'hi'})).toEqual({
      role: 'user',
      parts: [{type: 'text', content: 'hi'}],
    });
  });

  it('emits no parts for a message without content', () => {
    expect(toWireMessage({role: 'assistant'})).toEqual({
      role: 'assistant',
      parts: [],
    });
  });

  it('turns a flat tool message into a tool_call_response part without leaking tool fields', () => {
    expect(
      toWireMessage({
        role: 'tool',
        content: '{"temp":28}',
        toolCallId: 'call_1',
        toolName: 'get_weather',
      })
    ).toEqual({
      role: 'tool',
      parts: [
        {type: 'tool_call_response', id: 'call_1', response: '{"temp":28}'},
      ],
    });
  });

  it('maps developer to system and function to tool', () => {
    expect(toWireMessage({role: 'developer', content: 'Be brief.'})).toEqual({
      role: 'system',
      parts: [{type: 'text', content: 'Be brief.'}],
    });
    expect(toWireMessage({role: 'function', content: 'ok'})).toEqual({
      role: 'tool',
      parts: [{type: 'tool_call_response', response: 'ok'}],
    });
  });

  it('prefers explicit parts and converts them to wire keys', () => {
    expect(
      toWireMessage({
        role: 'assistant',
        content: 'ignored',
        parts: [
          {type: 'reasoning', content: 'thinking'},
          {
            type: 'tool_call',
            toolCallId: 'call_1',
            toolName: 'get_weather',
            arguments: '{"city":"Tokyo"}',
          },
        ],
      })
    ).toEqual({
      role: 'assistant',
      parts: [
        {type: 'reasoning', content: 'thinking'},
        {
          type: 'tool_call',
          id: 'call_1',
          name: 'get_weather',
          arguments: '{"city":"Tokyo"}',
        },
      ],
    });
    expect(
      toWireMessage({
        role: 'tool',
        parts: [{type: 'tool_result', toolCallId: 'call_1', result: 'sunny'}],
      })
    ).toEqual({
      role: 'tool',
      parts: [{type: 'tool_call_response', id: 'call_1', response: 'sunny'}],
    });
  });

  it('converts media parts to snake_case keys', () => {
    expect(
      toWireMessage({
        role: 'user',
        parts: [
          {
            type: 'file',
            fileId: 'f-1',
            mimeType: 'application/pdf',
            modality: 'document',
          },
          {
            type: 'blob',
            content: 'AAAA',
            mimeType: 'image/png',
            modality: 'image',
          },
          {type: 'uri', uri: 'https://example.com/a.png', modality: 'image'},
        ],
      })
    ).toEqual({
      role: 'user',
      parts: [
        {
          type: 'file',
          file_id: 'f-1',
          mime_type: 'application/pdf',
          modality: 'document',
        },
        {
          type: 'blob',
          content: 'AAAA',
          mime_type: 'image/png',
          modality: 'image',
        },
        {type: 'uri', uri: 'https://example.com/a.png', modality: 'image'},
      ],
    });
  });
});

describe('serializeMessages', () => {
  it('JSON-encodes the wire shape', () => {
    expect(serializeMessages([{role: 'user', content: 'hi'}])).toBe(
      '[{"role":"user","parts":[{"type":"text","content":"hi"}]}]'
    );
  });
});
