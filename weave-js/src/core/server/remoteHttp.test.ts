/* tslint:disable */

import _ from 'lodash';
import {vi} from 'vitest';

import {
  constBoolean,
  constNumber,
  constString,
} from '../model/graph/construction';
import {opNumberAdd, opNumberMult} from '../ops';
import {StaticOpStore} from '../opStore';
import {RemoteHttpServer} from './remoteHttp';

const headersWithCacheKey = (cacheKey: string | undefined) =>
  expect.objectContaining({
    'weave-shadow': 'false',
    'Content-Type': 'application/json',
    ...(cacheKey == null ? {} : {'x-weave-client-cache-key': cacheKey}),
  });

describe('RemoteHttpServer', () => {
  it('handles simple 1 graph query', () => {
    const fetch = vi.fn().mockReturnValue({
      ok: true,
      json: () => Promise.resolve({data: [42]}),
    });
    const server = new RemoteHttpServer(
      {
        weaveUrl: 'https://weave-host/execute',
        fetch,
      },
      StaticOpStore.getInstance()
    );

    const result = server.query([constNumber(42)]);
    return result.then(r => {
      expect(fetch).toHaveBeenCalledWith('https://weave-host/execute', {
        body: '{"graphs":{"nodes":[{"nodeType":"const","type":"number","val":42}],"targetNodes":[0]}}',
        credentials: 'include',
        headers: headersWithCacheKey(server.clientCacheKey),
        method: 'POST',
      });
      expect(r).toEqual([42]);
    });
  });

  it('handles simple 2 graph query', () => {
    const fetch = vi.fn().mockReturnValue({
      ok: true,
      json: () => Promise.resolve({data: [42, 'foo']}),
    });
    const server = new RemoteHttpServer(
      {
        weaveUrl: 'https://weave-host/execute',
        fetch,
      },
      StaticOpStore.getInstance()
    );

    const result = server.query([constNumber(42), constString('foo')]);
    return result.then(r => {
      expect(fetch).toHaveBeenCalledWith('https://weave-host/execute', {
        body: '{"graphs":{"nodes":[{"nodeType":"const","type":"number","val":42},{"nodeType":"const","type":"string","val":"foo"}],"targetNodes":[0,1]}}',
        credentials: 'include',
        headers: headersWithCacheKey(server.clientCacheKey),
        method: 'POST',
      });
      expect(r).toEqual([42, 'foo']);
    });
  });

  it('batches disjoint queries into single request when contiguousBatchesOnly is unset', () => {
    const fetch = vi.fn().mockReturnValue({
      ok: true,
      json: () => Promise.resolve({data: [42, 'foo', true]}),
    });
    const server = new RemoteHttpServer(
      {
        weaveUrl: 'https://weave-host/execute',
        fetch,
      },
      StaticOpStore.getInstance()
    );

    const result = Promise.all([
      server.query([constNumber(42)]),
      server.query([constString('foo')]),
      server.query([constBoolean(true)]),
    ]);
    return result.then(r => {
      expect(fetch).toHaveBeenCalledWith('https://weave-host/execute', {
        body: '{"graphs":{"nodes":[{"nodeType":"const","type":"number","val":42},{"nodeType":"const","type":"string","val":"foo"},{"nodeType":"const","type":"boolean","val":true}],"targetNodes":[0,1,2]}}',
        credentials: 'include',
        headers: headersWithCacheKey(server.clientCacheKey),
        method: 'POST',
      });
      expect(r).toEqual([[42], ['foo'], [true]]);
    });
  });

  it('batches disjoint queries into separate requests when contiguousBatchesOnly is set', () => {
    const fetch = vi
      .fn()
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [42]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: ['foo']}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [true]}),
      });
    const server = new RemoteHttpServer(
      {
        weaveUrl: 'https://weave-host/execute',
        fetch,
        mergeInexpensiveBatches: false,
      },
      StaticOpStore.getInstance()
    );

    const result = Promise.all([
      server.query([constNumber(42)]),
      server.query([constString('foo')]),
      server.query([constBoolean(true)]),
    ]);

    return result.then(r => {
      expect(fetch).toHaveBeenNthCalledWith(1, 'https://weave-host/execute', {
        body: '{"graphs":{"nodes":[{"nodeType":"const","type":"number","val":42}],"targetNodes":[0]}}',
        credentials: 'include',
        headers: headersWithCacheKey(server.clientCacheKey),
        method: 'POST',
      });
      expect(fetch).toHaveBeenNthCalledWith(2, 'https://weave-host/execute', {
        body: '{"graphs":{"nodes":[{"nodeType":"const","type":"string","val":"foo"}],"targetNodes":[0]}}',
        credentials: 'include',
        headers: headersWithCacheKey(server.clientCacheKey),
        method: 'POST',
      });
      expect(fetch).toHaveBeenNthCalledWith(3, 'https://weave-host/execute', {
        body: '{"graphs":{"nodes":[{"nodeType":"const","type":"boolean","val":true}],"targetNodes":[0]}}',
        credentials: 'include',
        headers: headersWithCacheKey(server.clientCacheKey),
        method: 'POST',
      });
      expect(r).toEqual([[42], ['foo'], [true]]);
    });
  });

  it('batches contiguous queries into same requests when contiguousBatchesOnly is set', () => {
    const fetch = vi
      .fn()
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [20, 50]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: ['foo']}),
      });
    const server = new RemoteHttpServer(
      {
        weaveUrl: 'https://weave-host/execute',
        fetch,
        mergeInexpensiveBatches: false,
      },
      StaticOpStore.getInstance()
    );

    const commonNode = constNumber(10);
    const result = server.query([
      opNumberAdd({lhs: commonNode, rhs: constNumber(10)}),
      opNumberMult({lhs: commonNode, rhs: constNumber(5)}),
      constString('foo'),
    ]);

    return result.then(r => {
      expect(fetch).toHaveBeenNthCalledWith(1, 'https://weave-host/execute', {
        body: '{"graphs":{"nodes":[{"nodeType":"output","fromOp":1,"type":"number","id":"3831373993168090"},{"name":"number-add","inputs":{"lhs":2,"rhs":2}},{"nodeType":"const","type":"number","val":10},{"nodeType":"output","fromOp":4,"type":"number","id":"2790509981729619"},{"name":"number-mult","inputs":{"lhs":2,"rhs":5}},{"nodeType":"const","type":"number","val":5}],"targetNodes":[0,3]}}',
        credentials: 'include',
        headers: headersWithCacheKey(server.clientCacheKey),
        method: 'POST',
      });
      expect(fetch).toHaveBeenNthCalledWith(2, 'https://weave-host/execute', {
        body: '{"graphs":{"nodes":[{"nodeType":"const","type":"string","val":"foo"}],"targetNodes":[0]}}',
        credentials: 'include',
        headers: headersWithCacheKey(server.clientCacheKey),
        method: 'POST',
      });
      expect(r).toEqual([20, 50, 'foo']);
    });
  });

  it('retries network error', () => {
    const fetch = vi
      .fn()
      .mockRejectedValueOnce(new Error('Network error'))
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [42]}),
      });

    const server = new RemoteHttpServer(
      {
        weaveUrl: 'https://weave-host/execute',
        fetch,
        backoffBase: 1,
        backoffExpScalar: 1,
        backoffMax: 1,
      },
      StaticOpStore.getInstance()
    );
    const result = server.query([constNumber(42)]);
    return result.then(r => {
      expect(fetch).toHaveBeenCalledTimes(2);
      expect(r).toEqual([42]);
    });
  });

  it('retries failed, retryable requests', () => {
    const fetch = vi
      .fn()
      .mockReturnValueOnce({
        ok: false,
        status: 502, // bad gateway
        json: () => Promise.reject('An error has occurred'),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [42]}),
      });
    const server = new RemoteHttpServer(
      {
        weaveUrl: 'https://weave-host/execute',
        fetch,
      },
      StaticOpStore.getInstance()
    );

    const result = server.query([constNumber(42)]);
    return result.then(r => {
      expect(fetch).toHaveBeenCalledTimes(2);
      expect(r).toEqual([42]);
    });
  });

  it('throws exception on failed, non-retryable requests', () => {
    const fetch = vi.fn().mockReturnValue({
      ok: false,
      status: 400, // bad request??
      json: () => Promise.reject('An error has occurred'),
    });
    const server = new RemoteHttpServer(
      {
        weaveUrl: 'https://weave-host/execute',
        fetch,
      },
      StaticOpStore.getInstance()
    );

    const result = server.query([constNumber(42)]);
    return result.catch(e => {
      expect(fetch).toHaveBeenCalledTimes(1);
    });
  });

  it('eventually gives up on failed, retryable requests', () => {
    const fetch = vi.fn().mockReturnValue({
      ok: false,
      status: 502, // bad gateway
      json: () => Promise.reject('An error has occurred'),
    });
    const server = new RemoteHttpServer(
      {
        weaveUrl: 'https://weave-host/execute',
        fetch,
        maxRetries: 3,

        // Set the backoff to 1ms so that the test doesn't take too long
        backoffBase: 1,
        backoffExpScalar: 1,
        backoffMax: 1,
      },
      StaticOpStore.getInstance()
    );

    const result = server.query([constNumber(42)]);
    return result.catch(e => {
      expect(fetch).toHaveBeenCalledTimes(4); // 1 initial + 3 retries
      expect(e).toEqual({
        message: 'Weave request failed after 3 retries',
        traceback: [],
      });
    });
  });

  it('single-batching crossed wires stress test -- single .query()', () => {
    const fetch = vi.fn().mockReturnValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          data: [
            0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 2, 4, 6, 8, 10, 3, 6, 9, 12, 15, 4, 8,
            12, 16, 20,
          ],
        }),
    });

    const commonNodes = _.range(5).map(n => constNumber(n));
    const leafNodes = commonNodes
      .map(c =>
        _.range(5).map(n => opNumberMult({lhs: c, rhs: constNumber(n)}))
      )
      .flat();

    // Leaf nodes is 25 elements, every group of 5 share a common node
    // so we expect 5 batches
    const server = new RemoteHttpServer(
      {
        weaveUrl: 'https://weave-host/execute',
        contiguousBatchesOnly: false,
        fetch,
      },
      StaticOpStore.getInstance()
    );
    const result = server.query(leafNodes);
    return result.then(r => {
      expect(fetch).toHaveBeenCalledTimes(1);
      expect(r).toEqual([
        0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 2, 4, 6, 8, 10, 3, 6, 9, 12, 15, 4, 8, 12,
        16, 20,
      ]);
    });
  });

  it('single-batching crossed wires stress test -- multi .query()', () => {
    const fetch = vi.fn().mockReturnValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          data: [
            0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 2, 4, 6, 8, 10, 3, 6, 9, 12, 15, 4, 8,
            12, 16, 20,
          ],
        }),
    });

    const commonNodes = _.range(5).map(n => constNumber(n));
    const leafNodes = commonNodes
      .map(c =>
        _.range(5).map(n => opNumberMult({lhs: c, rhs: constNumber(n)}))
      )
      .flat();

    // Leaf nodes is 25 elements, every group of 5 share a common node
    // so we expect 5 batches
    const server = new RemoteHttpServer(
      {
        weaveUrl: 'https://weave-host/execute',
        contiguousBatchesOnly: false,
        fetch,
      },
      StaticOpStore.getInstance()
    );
    const result = Promise.all(leafNodes.map(n => server.query([n])));
    return result.then(r => {
      expect(fetch).toHaveBeenCalledTimes(1);
      expect(r.flat()).toEqual([
        0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 2, 4, 6, 8, 10, 3, 6, 9, 12, 15, 4, 8, 12,
        16, 20,
      ]);
    });
  });

  it('multi-batching crossed wires stress test -- single .query()', () => {
    const fetch = vi
      .fn()
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [0, 0, 0, 0, 0]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [1, 2, 3, 4, 5]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [2, 4, 6, 8, 10]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [3, 6, 9, 12, 15]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [4, 8, 12, 16, 20]}),
      });

    const commonNodes = _.range(5).map(n => constNumber(n));
    const leafNodes = commonNodes
      .map(c =>
        _.range(5).map(n => opNumberMult({lhs: c, rhs: constNumber(n)}))
      )
      .flat();

    // Leaf nodes is 25 elements, every group of 5 share a common node
    // so we expect 5 batches
    const server = new RemoteHttpServer(
      {
        weaveUrl: 'https://weave-host/execute',
        mergeInexpensiveBatches: false,
        fetch,
      },
      StaticOpStore.getInstance()
    );
    const result = server.query(leafNodes);
    return result.then(r => {
      expect(fetch).toHaveBeenCalledTimes(5); // 5 batches
      expect(r).toEqual([
        0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 2, 4, 6, 8, 10, 3, 6, 9, 12, 15, 4, 8, 12,
        16, 20,
      ]);
    });
  });

  it('multi-batching crossed wires stress test -- multi .query()', () => {
    const fetch = vi
      .fn()
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [0, 0, 0, 0, 0]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [1, 2, 3, 4, 5]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [2, 4, 6, 8, 10]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [3, 6, 9, 12, 15]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [4, 8, 12, 16, 20]}),
      });

    const commonNodes = _.range(5).map(n => constNumber(n));
    const leafNodes = commonNodes
      .map(c =>
        _.range(5).map(n => opNumberMult({lhs: c, rhs: constNumber(n)}))
      )
      .flat();

    // Leaf nodes is 25 elements, every group of 5 share a common node
    // so we expect 5 batches
    const server = new RemoteHttpServer(
      {
        weaveUrl: 'https://weave-host/execute',
        mergeInexpensiveBatches: false,
        fetch,
      },
      StaticOpStore.getInstance()
    );
    const result = Promise.all(leafNodes.map(n => server.query([n])));
    return result.then(r => {
      expect(fetch).toHaveBeenCalledTimes(5); // 5 batches
      expect(r.flat()).toEqual([
        0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 2, 4, 6, 8, 10, 3, 6, 9, 12, 15, 4, 8, 12,
        16, 20,
      ]);
    });
  });

  it('multiple rounds of multi-batching crossed wires stress test -- multi .query()', () => {
    const fetch = vi
      .fn()
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [0, 1, 2, 3, 4]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [5, 6, 7, 8, 9]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [10, 11, 12, 13, 14]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [15, 16, 17, 18, 19]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [20, 21, 22, 23, 24]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [25, 26, 27, 28, 29]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [30, 31, 32, 33, 34]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [35, 36, 37, 38, 39]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [40, 41, 42, 43, 44]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [45, 46, 47, 48, 49]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [50, 51, 52, 53, 54]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [55, 56, 57, 58, 59]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [60, 61, 62, 63, 64]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [65, 66, 67, 68, 69]}),
      })
      .mockReturnValueOnce({
        ok: true,
        json: () => Promise.resolve({data: [70, 71, 72, 73, 74]}),
      });

    const result = Promise.all(
      _.range(15).flatMap(e => {
        const commonNode = constNumber(e * 5);
        const leafNodes = _.range(5).map(
          n =>
            [
              e * 5 + n,
              opNumberAdd({
                rhs: opNumberAdd({
                  lhs: commonNode,
                  rhs: constNumber(n),
                }),
              }),
            ] as const
        );

        // Leaf nodes is 25 elements, every group of 5 share a common node
        // so we expect 5 batches
        const server = new RemoteHttpServer(
          {
            weaveUrl: 'https://weave-host/execute',
            mergeInexpensiveBatches: false,
            fetch,
          },
          StaticOpStore.getInstance()
        );
        return new Promise(resolve => {
          setTimeout(
            () =>
              resolve(
                Promise.all(
                  leafNodes.map(async n => {
                    return [n[0], await server.query([n[1]])] as const;
                  })
                )
              ),
            e * 100
          );
        });
      })
    );
    return (result as any).then((r: Array<any>) => {
      expect(fetch).toHaveBeenCalledTimes(15); // 5 batches
      const expected = r.flat(1).map(([e]) => e);
      const actual = r.flat(1).map(([__, a]) => a[0]);
      expect(actual).toEqual(expected);
    });
  });
});
