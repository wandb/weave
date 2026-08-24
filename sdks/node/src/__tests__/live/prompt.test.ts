import {MessagesPrompt, StringPrompt} from '../../prompt';
import {init} from '../../clientApi';
import {createTraceServerClient} from '../../traceServerClient';
import {WandbServerApi} from 'weave/wandb/wandbServerApi';
import {stainlessPromise} from '../helpers/stainlessPromise';

jest.mock('../../wandb/wandbServerApi');
jest.mock('../../traceServerClient', () => ({
  createTraceServerClient: jest.fn(),
  TRACE_SERVER_TIMEOUT_MS: 5 * 60 * 1000,
}));

describe('Prompt', () => {
  test('should format a string prompt', async () => {
    const prompt = new StringPrompt({
      content: 'Hello, {name}!',
    });
    const formatted = prompt.format({name: 'John'});
    expect(formatted).toBe('Hello, John!');
  });
});

describe('MessagesPrompt', () => {
  test('should format a messages prompt', async () => {
    const prompt = new MessagesPrompt({
      messages: [{role: 'user', content: 'Hello, {name}!'}],
    });
    const formatted = prompt.format({name: 'John'});
    expect(formatted).toEqual([{role: 'user', content: 'Hello, John!'}]);
  });
});

describe('Prompt persistence', () => {
  const mockCreate = jest.fn();

  beforeEach(() => {
    (WandbServerApi as jest.Mock).mockImplementation(() => ({
      defaultEntityName: jest.fn().mockResolvedValue('test-entity'),
    }));
  });

  test('should persist a string prompt', async () => {
    (createTraceServerClient as jest.Mock).mockImplementation(() => ({
      objects: {
        create: mockCreate.mockReturnValue(
          stainlessPromise({digest: 'test-digest'})
        ),
        read: jest.fn().mockReturnValue(
          stainlessPromise({
            obj: {
              object_id: 'StringPrompt',
              val: {
                _type: 'StringPrompt',
                _class_name: 'StringPrompt',
                _bases: ['Prompt', 'Object', 'BaseModel'],
                content: 'Hello, {name}!',
              },
            },
          })
        ),
      },
    }));

    const client = await init('test-project');

    const prompt = new StringPrompt({
      content: 'Hello, {name}!',
      name: 'test-prompt',
      description: 'test-description',
    });

    const ref = await client.publish(prompt);

    expect(ref.uri()).toBe(
      'weave:///test-entity/test-project/object/test-prompt:test-digest'
    );

    expect(mockCreate).toHaveBeenCalledWith({
      obj: {
        project_id: 'test-entity/test-project',
        object_id: 'test-prompt',
        val: {
          _type: 'StringPrompt',
          _class_name: 'StringPrompt',
          _bases: ['Prompt', 'Object', 'BaseModel'],
          content: 'Hello, {name}!',
          name: 'test-prompt',
          description: 'test-description',
        },
      },
    });

    const retrievedObj = await ref.get();

    expect(retrievedObj.content).toBe('Hello, {name}!');
  });

  test('should persist a messages prompt', async () => {
    (createTraceServerClient as jest.Mock).mockImplementation(() => ({
      objects: {
        create: mockCreate.mockReturnValue(
          stainlessPromise({digest: 'test-digest'})
        ),
        read: jest.fn().mockReturnValue(
          stainlessPromise({
            obj: {
              object_id: 'MessagesPrompt',
              val: {
                _type: 'MessagesPrompt',
                _class_name: 'MessagesPrompt',
                _bases: ['Prompt', 'Object', 'BaseModel'],
                messages: [{role: 'user', content: 'Hello, {name}!'}],
              },
            },
          })
        ),
      },
    }));
    const client = await init('test-project');

    const prompt = new MessagesPrompt({
      messages: [{role: 'user', content: 'Hello, {name}!'}],
    });

    const ref = await client.publish(prompt);

    expect(ref.uri()).toBe(
      'weave:///test-entity/test-project/object/MessagesPrompt:test-digest'
    );

    expect(mockCreate).toHaveBeenCalledWith({
      obj: {
        project_id: 'test-entity/test-project',
        object_id: 'MessagesPrompt',
        val: {
          _type: 'MessagesPrompt',
          _class_name: 'MessagesPrompt',
          _bases: ['Prompt', 'Object', 'BaseModel'],
          messages: [{role: 'user', content: 'Hello, {name}!'}],
          name: undefined,
          description: undefined,
        },
      },
    });

    const retrievedObj = await ref.get();

    expect(retrievedObj.messages).toEqual([
      {role: 'user', content: 'Hello, {name}!'},
    ]);
  });
});

describe('Prompt.get static methods', () => {
  beforeEach(() => {
    (WandbServerApi as jest.Mock).mockImplementation(() => ({
      defaultEntityName: jest.fn().mockResolvedValue('test-entity'),
    }));
  });

  test('should get a string prompt by URI', async () => {
    const content = 'Hello, {name}!';
    const name = 'test-prompt';
    const description = 'A test prompt';

    (createTraceServerClient as jest.Mock).mockImplementation(() => ({
      objects: {
        read: jest.fn().mockReturnValue(
          stainlessPromise({
            obj: {
              object_id: name,
              val: {
                _type: 'StringPrompt',
                _class_name: 'StringPrompt',
                _bases: ['Prompt', 'Object', 'BaseModel'],
                content,
                name,
                description,
              },
            },
          })
        ),
      },
    }));

    const client = await init('test-project');
    const prompt = await StringPrompt.get(
      client,
      `weave:///test-entity/test-project/object/${name}:abc123`
    );

    expect(prompt).toBeInstanceOf(StringPrompt);
    expect(prompt.content).toBe(content);
    expect(prompt.name).toBe(name);
    expect(prompt.description).toBe(description);
  });

  test('should get a messages prompt by URI', async () => {
    const messages = [{role: 'user', content: 'Hello, {name}!'}];
    const name = 'test-messages-prompt';
    const description = 'A test messages prompt';

    (createTraceServerClient as jest.Mock).mockImplementation(() => ({
      objects: {
        read: jest.fn().mockReturnValue(
          stainlessPromise({
            obj: {
              object_id: name,
              val: {
                _type: 'MessagesPrompt',
                _class_name: 'MessagesPrompt',
                _bases: ['Prompt', 'Object', 'BaseModel'],
                messages,
                name,
                description,
              },
            },
          })
        ),
      },
    }));

    const client = await init('test-project');
    const prompt = await MessagesPrompt.get(
      client,
      `weave:///test-entity/test-project/object/${name}:def456`
    );

    expect(prompt).toBeInstanceOf(MessagesPrompt);
    expect(prompt.messages).toEqual(messages);
    expect(prompt.name).toBe(name);
    expect(prompt.description).toBe(description);
  });
});
