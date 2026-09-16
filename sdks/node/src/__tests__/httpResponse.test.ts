import {APIError, APIConnectionError} from '../vendor/weave-server-sdk';
import {asHttpResponse, throwAsHttpResponse} from '../httpResponse';
import {stainlessPromise, stainlessReject} from './helpers/stainlessPromise';

describe('throwAsHttpResponse', () => {
  it('throws a swagger-shaped object for HTTP APIError', () => {
    const err = new APIError(
      404,
      {detail: 'Project not found'},
      'not found',
      new Headers()
    );
    try {
      throwAsHttpResponse(err);
      throw new Error('expected throw');
    } catch (thrown) {
      expect(thrown).toMatchObject({
        status: 404,
        data: null,
        error: {detail: 'Project not found'},
      });
    }
  });

  it('rethrows a connection error', () => {
    const err = new APIConnectionError({message: 'offline'});
    expect(() => throwAsHttpResponse(err)).toThrow(err);
  });

  it('rethrows a bare Error', () => {
    const err = new Error('boom');
    expect(() => throwAsHttpResponse(err)).toThrow('boom');
  });
});

describe('asHttpResponse', () => {
  it('returns .data on success', async () => {
    const result = await asHttpResponse(
      stainlessPromise({agents: [], total_count: 0}) as any
    );
    expect(result.data).toEqual({agents: [], total_count: 0});
    expect(result.error).toBeNull();
    expect(result.ok).toBe(true);
    expect(result.status).toBe(200);
  });

  it('throws the swagger-shaped object on HTTP APIError', async () => {
    const err = new APIError(
      404,
      {detail: 'Project not found'},
      'not found',
      new Headers()
    );
    await expect(
      asHttpResponse(stainlessReject(err) as any)
    ).rejects.toMatchObject({
      status: 404,
      data: null,
      error: {detail: 'Project not found'},
    });
  });

  it('propagates a bare Error', async () => {
    await expect(
      asHttpResponse(stainlessReject(new Error('boom')) as any)
    ).rejects.toThrow('boom');
  });
});
