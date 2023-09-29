import Observable from 'zen-observable';

import {GlobalCGEventTracker} from '../analytics/tracker';
import {Hasher, MemoizedHasher} from '../model/graph/editing/hash';
import * as GraphTypes from '../model/graph/types';
import * as Model from '../model/types';
import {OpStore} from '../opStore/types';
import {RemoteHttpServer} from '../server';
import {Server} from '../server/types';
import {ID} from '../util/id';
import {Client} from './types';
import _ from 'lodash';

interface ObservableNode<T extends Model.Type = Model.Type> {
  id: string;
  observable: Observable<T>;
  node: GraphTypes.Node<T>;
  observers: Set<ZenObservable.SubscriptionObserver<T>>;
  hasResult: boolean;
  lastResult: any;
}

type ResetRequestType = {
  promise: Promise<void>;
  resolve: () => void;
};

const POLL_INTERVAL = 15000;

export class BasicClient implements Client {
  readonly opStore: OpStore;
  private nextRequestTimer?: NodeJS.Timeout;
  private requestInFlight: boolean = false;
  private makeRequestWhenDone: boolean = false;
  private observables = new Map<string, ObservableNode>();
  private resolveRefreshRequest?: ResetRequestType;
  private loadingListeners = new Map<
    string,
    ZenObservable.SubscriptionObserver<boolean>
  >();
  private loading = new Observable<boolean>(observer => {
    const id = ID();
    this.loadingListeners.set(id, observer);

    return () => this.loadingListeners.delete(id);
  });
  private shouldPoll: boolean = false;
  private pollingListeners: Array<(poll: boolean) => void> = [];
  private readonly hasher: Hasher;

  public constructor(private readonly server: Server) {
    this.hasher = new MemoizedHasher();
    if (server instanceof RemoteHttpServer) {
      // only works for weave execution engines that do not depend on apollo
      // initial issue: https://weightsandbiases.slack.com/archives/C01T8BLDHKP/p1649955797252749
      // resolution: https://weightsandbiases.slack.com/archives/C04UJFUUSSW/p1679341328969859
      // enabling this causes the UI to re-execute potentially large
      // graphs on every poll, which can slow things down significantly.
      setTimeout(this.pollIteration.bind(this), POLL_INTERVAL);
    }
    this.opStore = server.opStore;
  }

  public setPolling(polling: boolean) {
    this.shouldPoll = polling;
    this.pollingListeners.forEach(cb => cb(polling));
  }

  public isPolling(): boolean {
    return this.shouldPoll;
  }

  public addOnPollingChangeListener(
    callback: (polling: boolean) => void
  ): void {
    if (!this.pollingListeners.includes(callback)) {
      this.pollingListeners.push(callback);
    }
  }
  public removeOnPollingChangeListener(
    callback: (polling: boolean) => void
  ): void {
    this.pollingListeners = this.pollingListeners.filter(cb => cb !== callback);
  }

  public subscribe<T extends Model.Type>(
    node: GraphTypes.Node<T>
  ): Observable<any> {
    GlobalCGEventTracker.basicClientSubscriptions++;
    const observableId = this.hasher.typedNodeId(node);
    if (this.observables.has(observableId)) {
      const obs = this.observables.get(observableId);
      if (obs == null) {
        throw new Error('This should never happen');
      }
      return obs.observable;
    }
    const observable = new Observable<Model.Type>(observer => {
      const obs = this.observables.get(observableId);
      // console.log('SUB', observableId, obs);
      if (obs == null) {
        return;
      }
      obs.observers.add(observer);
      if (obs.hasResult) {
        observer.next(obs.lastResult);
      } else {
        this.setIsLoading(true);
      }
      return () => {
        obs.observers.delete(observer);
        // TODO: bug here!
        // console.log('UNSUB', observableId);
        if (obs.observers.size === 0) {
          // console.log('FULL UNSUB', observableId, node);
          this.observables.delete(observableId);
        }
      };
    });
    this.observables.set(observableId, {
      id: observableId,
      observable,
      observers: new Set(),
      node,
      hasResult: false,
      lastResult: undefined,
    });
    this.scheduleRequest();
    return observable;
  }

  // I'm adding this for now to make it easier to switch
  // refineNode to use client. But we should really make
  // refineNode() also subscribable, meaning we want to
  // wire observers through that code path.
  // TODO: really, fix this. It would mean we can poll correctly
  // and efficiently for both useNodeValue() and useNodeWithServerType()
  public query<T extends Model.Type>(node: GraphTypes.Node<T>): Promise<any> {
    const obs = this.subscribe(node);
    return new Promise((resolve, reject) => {
      const sub = obs.subscribe(
        nodeRes => {
          resolve(nodeRes);
          sub.unsubscribe();
        },
        caughtError => {
          reject(caughtError);
          sub.unsubscribe();
        }
      );
    });
  }

  public action<T extends Model.Type>(node: GraphTypes.Node<T>): Promise<any> {
    return new Promise((resolve, reject) => {
      this.server
        .query([node], undefined, true)
        .then(response => resolve(response[0]))
        .catch(reject);
    });
  }

  public loadingObservable() {
    return this.loading;
  }

  public refreshAll(): Promise<void> {
    if (this.resolveRefreshRequest == null) {
      let res: ResetRequestType['resolve'] = () => {};
      const prom = new Promise<void>((resolve, reject) => {
        res = resolve;
      });
      this.resolveRefreshRequest = {
        promise: prom,
        resolve: res,
      };
      this.scheduleRequest();
    }
    return this.resolveRefreshRequest.promise;
  }

  public debugMeta(): {id: string} & {[prop: string]: any} {
    return {
      id: 'BasicClient',
      opStore: this.opStore.debugMeta(),
      server: this.server.debugMeta(),
    };
  }

  private scheduleRequest() {
    if (this.nextRequestTimer != null) {
      clearTimeout(this.nextRequestTimer);
    }
    this.nextRequestTimer = setTimeout(() => this.requestBatch(), 50);
  }

  private pollIteration() {
    if (this.shouldPoll) {
      this.refreshAll();
    }
    setTimeout(this.pollIteration.bind(this), POLL_INTERVAL);
  }

  private setIsLoading(loading: boolean) {
    this.loadingListeners.forEach(observer => observer.next(loading));
  }

  private async requestBatch() {
    this.nextRequestTimer = undefined;
    if (this.requestInFlight) {
      this.makeRequestWhenDone = true;
    } else {
      this.requestInFlight = true;
      await this.doRequestBatch();
      this.requestInFlight = false;
      if (this.makeRequestWhenDone) {
        this.makeRequestWhenDone = false;
        this.requestBatch();
      }
    }
  }

  private async doRequestBatch() {
    const notDoneObservables = Array.from(this.observables.values()).filter(
      l => !l.hasResult || this.resolveRefreshRequest != null
    );
    if (notDoneObservables.length > 0) {
      // console.log(
      //   'CLIENT BATCH START',
      //   notDoneObservables,
      //   Array.from(this.observables.entries()).map(([k, l]) => [k, l.hasResult])
      // );

      const rejectObservable = (observable: ObservableNode<any>, e: any) => {
        observable.hasResult = true;
        for (const observer of observable.observers) {
          observer.error(e);
        }
      };

      const resolveObservable = (
        observable: ObservableNode<any>,
        result: any
      ) => {
        observable.hasResult = true;
        observable.lastResult = result;
        for (const observer of observable.observers) {
          observer.next(result);
        }
      };

      const handleCompleteError = (e: any) => {
        for (const observable of notDoneObservables) {
          rejectObservable(observable, e);
        }
        // TODO(np): Do we need to do anything to recover here?
      };

      // console.time('graph execute');
      if (this.server instanceof RemoteHttpServer) {
        // Modern - Weave1 Server
        let eachResults: Array<PromiseSettledResult<any>> = [];
        try {
          eachResults = await this.server.queryEach(
            notDoneObservables.map(o => o.node)
          );
        } catch (e) {
          handleCompleteError(e);
        }
        for (const [result, observable] of _.zip(
          eachResults,
          notDoneObservables
        )) {
          if (result == null || observable == null) {
            // ERROR HERE?
            continue;
          }
          if (result.status === 'rejected') {
            rejectObservable(observable, result.reason);
          } else {
            resolveObservable(observable, result.value);
          }
        }
      } else {
        let results: any[] = [];
        try {
          // Legacy - in-memory server
          results = await this.executeForwardListeners(
            notDoneObservables.map(o => o.node),
            this.resolveRefreshRequest != null
          );
        } catch (e) {
          handleCompleteError(e);
        }
        for (let i = 0; i < notDoneObservables.length; i++) {
          resolveObservable(notDoneObservables[i], results[i]);
        }
      }
    }

    if (Array.from(this.observables.values()).every(obs => obs.hasResult)) {
      this.setIsLoading(false);
    }

    if (this.resolveRefreshRequest != null) {
      const res = this.resolveRefreshRequest.resolve;
      this.resolveRefreshRequest = undefined;
      res();
    }
  }

  private async executeForwardListeners(
    targetNodes: GraphTypes.Node[],
    resetBackendExecutionCache?: boolean
  ) {
    return this.server.query(targetNodes, resetBackendExecutionCache);
  }
}
