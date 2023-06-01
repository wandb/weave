// This class as hard-coded fields to track the critical points in our CG execution flow.
// In the future we should consider making this more generic, but for now this is lightweight
// and therefore easier to iterate if we want to change our collection strategy.
class CGEventTracker {
  // Tracks the number of times our router client (performance mode)
  // routes to the Remote (python) and Local (TS) clients respectively.
  routedServerRemote = 0;
  routedServerLocal = 0;

  // Tracks the number of times the Remote client is called. Note: this
  // will contain both direct calls from the Ecosystem mode as well as
  // performance mode routed to the Remote client.
  cachedClientSubscriptions = 0;
  // The Remote client has a caching layer - this tracks the number of cache hits.
  cachedClientCacheHits = 0;

  // Tracks the total number of basicClientSubscriptions. Note: this will contain all of:
  // * the normal-TS execution requests
  // * the non-cached remote client requests. Which in itself contains:
  //   * all non-cached ecosystem requests
  //   * all non-cached routed-to-remote requests
  basicClientSubscriptions = 0;

  // Tracks the total number of batches sent to the local engine
  localServerQueryBatchRequests = 0;

  // Tracks the total number of batches send to the remote engine
  remoteHttpServerQueryBatchRequests = 0;

  // Tracks the total number of expanded forward graph nodes in the local engine
  engineForwardGraphNodes = 0;
  // Tracks the total number of op resolvers executed in the local engine
  engineResolves = 0;

  // Tracks the number of requests sent to shadow server
  shadowServerRequests = 0;

  private startDate = 0;

  constructor() {
    this.startDate = Date.now();
  }
  public reset() {
    this.routedServerRemote = 0;
    this.routedServerLocal = 0;
    this.cachedClientSubscriptions = 0;
    this.cachedClientCacheHits = 0;
    this.basicClientSubscriptions = 0;
    this.localServerQueryBatchRequests = 0;
    this.remoteHttpServerQueryBatchRequests = 0;
    this.engineForwardGraphNodes = 0;
    this.engineResolves = 0;
    this.shadowServerRequests = 0;
    this.startDate = Date.now();
  }

  public summary() {
    // Calculated Fields:
    const ecosystemClientSubscriptions =
      this.cachedClientSubscriptions - this.routedServerRemote;
    const remoteClientToBasic =
      this.cachedClientSubscriptions - this.cachedClientCacheHits;
    const productionClientSubscriptions =
      this.basicClientSubscriptions -
      this.routedServerLocal -
      remoteClientToBasic;
    const engineCacheHits = this.engineForwardGraphNodes - this.engineResolves;

    return {
      __duration: Date.now() - this.startDate,
      _1_nodeSubscriptions: {
        toRouted: {
          toRemoteCache: this.routedServerRemote,
          toBasicClientLocal: this.routedServerLocal,
        },
        toEcosystem: {
          toRemoteCache: ecosystemClientSubscriptions,
        },
        toProduction: {toBasicClientLocal: productionClientSubscriptions},
      },

      _2_remoteCache: {
        resolvedWithCache: this.cachedClientCacheHits,
        toBasicClientRemote: remoteClientToBasic,
      },

      _3_basicClientBatchQueries: {
        toLocalEngine: this.localServerQueryBatchRequests,
        resolvedWithRemoteEngine: this.remoteHttpServerQueryBatchRequests,
        shadowServerRequests: this.shadowServerRequests,
      },

      _4_localEngine: {
        resolvedWithOp: this.engineResolves,
        resolvedWithCache: engineCacheHits,
      },
    };
  }
}

export const GlobalCGEventTracker = new CGEventTracker();
