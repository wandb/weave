import _ from 'lodash';

import {
  FeedbackCreateReq,
  FeedbackCreateRes,
  FeedbackPurgeReq,
  FeedbackPurgeRes,
  TraceCallsDeleteReq,
  TraceCallUpdateReq,
  TraceRefsReadBatchReq,
  TraceRefsReadBatchRes,
} from './traceServerClientTypes';
import {DirectTraceServerClient} from './traceServerDirectClient';

const DEFAULT_BATCH_INTERVAL = 150;
const MAX_REFS_PER_BATCH = 1000;

export class TraceServerClient extends DirectTraceServerClient {
  private readBatchCollectors: Array<{
    req: TraceRefsReadBatchReq;
    resolvePromise: (res: TraceRefsReadBatchRes) => void;
    rejectPromise: (err: any) => void;
  }> = [];
  private onDeleteListeners: Array<() => void>;
  private onRenameListeners: Array<() => void>;
  private onFeedbackListeners: Record<string, Array<() => void>>;

  constructor(baseUrl: string) {
    super(baseUrl);
    this.readBatchCollectors = [];
    this.scheduleReadBatch();
    this.onDeleteListeners = [];
    this.onRenameListeners = [];
    this.onFeedbackListeners = {};
  }

  /**
   * Registers a callback to be called when a delete operation occurs.
   * This method is purely for local notification within the client
   *    and does not interact with the REST API.
   *
   * @param callback A function to be called when a delete operation is triggered.
   * @returns A function to unregister the callback.
   */
  public registerOnDeleteListener(callback: () => void): () => void {
    this.onDeleteListeners.push(callback);
    return () => {
      this.onDeleteListeners = this.onDeleteListeners.filter(
        listener => listener !== callback
      );
    };
  }
  public registerOnRenameListener(callback: () => void): () => void {
    this.onRenameListeners.push(callback);
    return () => {
      this.onRenameListeners = this.onRenameListeners.filter(
        listener => listener !== callback
      );
    };
  }
  public registerOnFeedbackListener(
    weaveRef: string,
    callback: () => void
  ): () => void {
    if (!(weaveRef in this.onFeedbackListeners)) {
      this.onFeedbackListeners[weaveRef] = [];
    }
    this.onFeedbackListeners[weaveRef].push(callback);
    return () => {
      const newListeners = this.onFeedbackListeners[weaveRef].filter(
        listener => listener !== callback
      );
      if (newListeners.length) {
        this.onFeedbackListeners[weaveRef] = newListeners;
      } else {
        delete this.onFeedbackListeners[weaveRef];
      }
    };
  }

  public callsDelete(req: TraceCallsDeleteReq): Promise<void> {
    const res = super.callsDelete(req).then(() => {
      this.onDeleteListeners.forEach(listener => listener());
    });
    return res;
  }

  public callUpdate(req: TraceCallUpdateReq): Promise<void> {
    const res = super.callUpdate(req).then(() => {
      this.onRenameListeners.forEach(listener => listener());
    });
    return res;
  }

  public feedbackCreate(req: FeedbackCreateReq): Promise<FeedbackCreateRes> {
    const res = super.feedbackCreate(req).then(createRes => {
      const listeners = this.onFeedbackListeners[req.weave_ref] ?? [];
      listeners.forEach(listener => listener());
      return createRes;
    });
    return res;
  }
  public feedbackPurge(req: FeedbackPurgeReq): Promise<FeedbackPurgeRes> {
    const res = super.feedbackPurge(req).then(purgeRes => {
      // TODO: Since purge takes a query, we need to change the result to include
      //       information about the refs that were modified.
      //       For now, just call all registered feedback listeners.
      for (const listeners of Object.values(this.onFeedbackListeners)) {
        listeners.forEach(listener => listener());
      }
      return purgeRes;
    });
    return res;
  }

  public readBatch(req: TraceRefsReadBatchReq): Promise<TraceRefsReadBatchRes> {
    return this.requestReadBatch(req);
  }

  private requestReadBatch(
    req: TraceRefsReadBatchReq
  ): Promise<TraceRefsReadBatchRes> {
    return new Promise<TraceRefsReadBatchRes>((resolve, reject) => {
      this.readBatchCollectors.push({
        req,
        resolvePromise: resolve,
        rejectPromise: reject,
      });
    });
  }

  private async doReadBatch() {
    if (this.readBatchCollectors.length === 0) {
      return;
    }
    const collectors = [...this.readBatchCollectors];
    this.readBatchCollectors = [];
    const refs = _.uniq(collectors.map(c => c.req.refs).flat());
    const valMap = new Map<string, any>();
    while (refs.length > 0) {
      const refsForBatch = refs.splice(0, MAX_REFS_PER_BATCH);
      const res = await this.readBatchDirect({refs: refsForBatch});
      const vals = res.vals;
      for (let i = 0; i < refsForBatch.length; i++) {
        valMap.set(refsForBatch[i], vals[i]);
      }
    }
    collectors.forEach(collector => {
      const req = collector.req;
      const refVals = req.refs.map(ref => valMap.get(ref));
      collector.resolvePromise({vals: refVals});
    });
  }

  private async scheduleReadBatch() {
    await this.doReadBatch();
    setTimeout(this.scheduleReadBatch.bind(this), DEFAULT_BATCH_INTERVAL);
  }

  private readBatchDirect(
    req: TraceRefsReadBatchReq
  ): Promise<TraceRefsReadBatchRes> {
    return super.readBatch(req);
  }
}
