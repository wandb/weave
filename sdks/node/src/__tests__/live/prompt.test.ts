import {MessagesPrompt, StringPrompt} from '../../prompt';
import {init} from '../../clientApi';
import {WandbServerApi} from 'weave/wandb/wandbServerApi';
import {Api as TraceServerApi} from '../../generated/traceServerApi';

jest.mock('../../wandb/wandbServerApi');

jest.mock('../../generated/traceServerApi');

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
  const mockObjCreateObjCreatePost = jest.fn();

  beforeEach(() => {
    // Mock WandbServerApi
    (WandbServerApi as jest.Mock).mockImplementation(() => ({
      defaultEntityName: jest.fn().mockResolvedValue('test-entity'),
    }));
  });

  test('should persist a string prompt', async () => {
    // Mock TraceServerApi
    (TraceServerApi as jest.Mock).mockImplementation(() => ({
      obj: {
        objCreateObjCreatePost: mockObjCreateObjCreatePost.mockResolvedValue({
          data: {
            digest: 'test-digest',
          },
        }),
        objReadObjReadPost: jest.fn().mockResolvedValue({
          data: {
            obj: {
              object_id: 'StringPrompt',
              val: {
                _type: 'StringPrompt',
                _class_name: 'StringPrompt',
                _bases: ['Prompt', 'Object', 'BaseModel'],
                content: 'Hello, {name}!',
              },
            },
          },
        }),
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

    expect(mockObjCreateObjCreatePost).toHaveBeenCalledWith({
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
    // Mock TraceServerApi
    (TraceServerApi as jest.Mock).mockImplementation(() => ({
      obj: {
        objCreateObjCreatePost: mockObjCreateObjCreatePost.mockResolvedValue({
          data: {
            digest: 'test-digest',
          },
        }),
        objReadObjReadPost: jest.fn().mockResolvedValue({
          data: {
            obj: {
              object_id: 'MessagesPrompt',
              val: {
                _type: 'MessagesPrompt',
                _class_name: 'MessagesPrompt',
                _bases: ['Prompt', 'Object', 'BaseModel'],
                messages: [{role: 'user', content: 'Hello, {name}!'}],
              },
            },
          },
        }),
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

    expect(mockObjCreateObjCreatePost).toHaveBeenCalledWith({
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
    // Mock WandbServerApi
    (WandbServerApi as jest.Mock).mockImplementation(() => ({
      defaultEntityName: jest.fn().mockResolvedValue('test-entity'),
    }));
  });

  test('should get a string prompt by URI', async () => {
    const content = 'Hello, {name}!';
    const name = 'test-prompt';
    const description = 'A test prompt';

    // Mock TraceServerApi
    (TraceServerApi as jest.Mock).mockImplementation(() => ({
      obj: {
        objReadObjReadPost: jest.fn().mockResolvedValue({
          data: {
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
          },
        }),
      },
    }));

    const client = await init('test-project');
    const prompt = await StringPrompt.get(
      client,
      `weave:///test-entity/test-project/object/${name}:abc123`
    );

    // Verify type
    expect(prompt).toBeInstanceOf(StringPrompt);
    // Verify properties
    expect(prompt.content).toBe(content);
    expect(prompt.name).toBe(name);
    expect(prompt.description).toBe(description);
  });

  test('should get a messages prompt by URI', async () => {
    const messages = [{role: 'user', content: 'Hello, {name}!'}];
    const name = 'test-messages-prompt';
    const description = 'A test messages prompt';

    // Mock TraceServerApi
    (TraceServerApi as jest.Mock).mockImplementation(() => ({
      obj: {
        objReadObjReadPost: jest.fn().mockResolvedValue({
          data: {
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
          },
        }),
      },
    }));

    const client = await init('test-project');
    const prompt = await MessagesPrompt.get(
      client,
      `weave:///test-entity/test-project/object/${name}:def456`
    );

    // Verify type
    expect(prompt).toBeInstanceOf(MessagesPrompt);
    // Verify properties
    expect(prompt.messages).toEqual(messages);
    expect(prompt.name).toBe(name);
    expect(prompt.description).toBe(description);
  });
});
