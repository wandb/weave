import LRUCache from 'lru-cache';

import {
  TraceFileContentReadReq,
  TraceFileContentReadRes,
  TraceObjReadReq,
  TraceObjReadRes,
  TraceTableQueryReq,
  TraceTableQueryRes,
  TraceTableQueryStatsReq,
  TraceTableQueryStatsRes,
} from './traceServerClientTypes';
import {DirectTraceServerClient} from './traceServerDirectClient';

interface CacheConfig {
  max: number;
  getCacheKey: (req: any) => string;
}

export class CachingTraceServerClient extends DirectTraceServerClient {
  private caches: Map<
    string,
    {cache: LRUCache<string, any>; config: CacheConfig}
  >;

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

    this.addCache('tableQueryStats', {
      max: 1000,
      getCacheKey: (req: TraceTableQueryStatsReq) => JSON.stringify(req),
    });
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

  public override tableQueryStats(
    req: TraceTableQueryStatsReq
  ): Promise<TraceTableQueryStatsRes> {
    return this.withCache('tableQueryStats', req, () =>
      super.tableQueryStats(req)
    );
  }
}
