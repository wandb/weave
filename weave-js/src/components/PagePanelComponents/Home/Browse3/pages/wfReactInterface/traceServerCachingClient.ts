import LRUCache from 'lru-cache';

import {
  TraceFileContentReadReq,
  TraceFileContentReadRes,
  TraceObjReadReq,
  TraceObjReadRes,
  TraceTableQueryReq,
  TraceTableQueryRes,
  TraceTableQueryStatsBatchReq,
  TraceTableQueryStatsBatchRes,
} from './traceServerClientTypes';
import {DirectTraceServerClient} from './traceServerDirectClient';

interface CacheConfig {
  max: number;
  getCacheKey: (req: any) => string;
}

export type TraceTableRowQueryReq = {
  project_id: string;
  digest: string;
  row_digests: string[];
};

export type TraceTableRowQueryRes = {
  rows: Array<{
    digest: string;
    val: any;
  }>;
};

export class CachingTraceServerClient extends DirectTraceServerClient {
  private caches: Map<
    string,
    {cache: LRUCache<string, any>; config: CacheConfig}
  >;
  // The `tableDigestCache` is distinct from the general purpose method caches
  // as we are applying custom logic beyond simply keying on the request.
  // In particular, since table rows are keyed by their digest (and the same
  // digest can appear in multiple tables), we only need to key on the digest
  // of the row itself!.
  private tableDigestCache: LRUCache<string, any>;

  constructor(baseUrl: string) {
    super(baseUrl);
    this.caches = new Map();

    // Configure caches for specific methods
    this.addCache('fileContent', {
      max: 1000,
      getCacheKey: (req: TraceFileContentReadReq) => JSON.stringify(req),
    });

    this.addCache('objRead', {
      max: 1000,
      getCacheKey: (req: TraceObjReadReq) => JSON.stringify(req),
    });

    this.addCache('tableQuery', {
      max: 1000,
      getCacheKey: (req: TraceTableQueryReq) => JSON.stringify(req),
    });

    this.addCache('tableQueryStatsBatch', {
      max: 1000,
      getCacheKey: (req: TraceTableQueryStatsBatchReq) => JSON.stringify(req),
    });

    this.tableDigestCache = new LRUCache<string, any>({max: 1000});
  }

  protected addCache(methodName: string, config: CacheConfig) {
    this.caches.set(methodName, {
      cache: new LRUCache({max: config.max}),
      config,
    });
  }

  protected withCache<Req, Res>(
    methodName: string,
    req: Req,
    getFresh: () => Promise<Res>
  ): Promise<Res> {
    const cacheInfo = this.caches.get(methodName);
    if (!cacheInfo) {
      return getFresh();
    }

    const {cache, config} = cacheInfo;
    const key = config.getCacheKey(req);
    const cached = cache.get(key) as Res | undefined;

    if (cached) {
      return Promise.resolve(cached);
    }

    return getFresh().then(result => {
      cache.set(key, result);
      return result;
    });
  }

  public override fileContent(
    req: TraceFileContentReadReq
  ): Promise<TraceFileContentReadRes> {
    return this.withCache('fileContent', req, () => super.fileContent(req));
  }

  public override objRead(req: TraceObjReadReq): Promise<TraceObjReadRes> {
    return this.withCache('objRead', req, () => super.objRead(req));
  }

  public override tableQuery(
    req: TraceTableQueryReq
  ): Promise<TraceTableQueryRes> {
    return this.withCache('tableQuery', req, () => super.tableQuery(req));
  }

  public override tableQueryStatsBatch(
    req: TraceTableQueryStatsBatchReq
  ): Promise<TraceTableQueryStatsBatchRes> {
    return this.withCache('tableQueryStatsBatch', req, () =>
      super.tableQueryStatsBatch(req)
    );
  }

  public tableRowQuery(
    req: TraceTableRowQueryReq
  ): Promise<TraceTableRowQueryRes> {
    // In order to maximize cache hits, we first split the request into
    // the subset of digests that are already cached and the subset that
    // are not. We then only make a single tableQuery request for the
    // missing digests, and reconstruct the correct results before returning.
    const cachedResults = new Map<string, any>();
    for (const digest of req.row_digests) {
      const cached = this.tableDigestCache.get(digest);
      if (cached) {
        cachedResults.set(digest, cached);
      }
    }

    const missingDigests = req.row_digests.filter(
      digest => !cachedResults.has(digest)
    );

    const resultPromise = new Promise<TraceTableRowQueryRes>(
      async (resolve, reject) => {
        if (missingDigests.length === 0) {
          resolve({
            rows: req.row_digests.map(digest => ({
              digest,
              val: cachedResults.get(digest),
            })),
          });
        } else {
          const res = await super.tableQuery({
            project_id: req.project_id,
            digest: req.digest,
            filter: {
              row_digests: missingDigests,
            },
          });

          for (const row of res.rows) {
            this.tableDigestCache.set(row.digest, row.val);
            cachedResults.set(row.digest, row.val);
          }
          resolve({
            rows: req.row_digests.map(digest => ({
              digest,
              val: cachedResults.get(digest),
            })),
          });
        }
      }
    );

    return resultPromise;
  }
}
