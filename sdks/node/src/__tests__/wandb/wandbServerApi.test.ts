import {WandbServerApi} from '../../wandb/wandbServerApi';

const originalFetch = global.fetch;
const api = new WandbServerApi('https://api.wandb.ai', 'abcdef123456');

const mockGoodResponse = {
  ok: true,
  json: jest
    .fn()
    .mockResolvedValue({data: {viewer: {defaultEntity: {name: 'test'}}}}),
};
const mockInvalidEntityResponse = {
  ok: true,
  json: jest.fn().mockResolvedValue({data: {viewer: {defaultEntity: {}}}}),
};
const mockBadGQLResponse = {
  ok: true,
  json: jest.fn().mockResolvedValue({errors: [{message: 'problem'}]}),
};

describe('wandbServerApi', () => {
  afterEach(() => {
    global.fetch = originalFetch;
  });

  test('default entity happy path', async () => {
    const mockFetch = jest.fn().mockResolvedValue(mockGoodResponse);
    global.fetch = mockFetch;

    const result = await api.defaultEntityName();
    expect(result).toEqual('test');
  });

  test('default entity error path', async () => {
    const mockFetch = jest.fn().mockResolvedValue(mockInvalidEntityResponse);
    global.fetch = mockFetch;

    await expect(api.defaultEntityName()).rejects.toThrow(/name not found/);
  });

  test('gql error path', async () => {
    const mockFetch = jest.fn().mockResolvedValue(mockBadGQLResponse);
    global.fetch = mockFetch;

    await expect(api.defaultEntityName()).rejects.toThrow(/GraphQL Error/);
  });
});
