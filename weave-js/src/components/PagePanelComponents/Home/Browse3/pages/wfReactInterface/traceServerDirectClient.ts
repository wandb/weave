/**
 * This file defines the connection between the web client and the trace server.
 * The intention is that the implementation is a 1-1 mapping to the trace
 * server's API. This file should not contain any business logic. If possible,
 * we could generate this from `trace_server.py`. Which in effect is a perfect
 * mapping of `weave/trace_server/trace_server_interface.py` as a web service.
 *
 * These types MUST be kept in sync with the types defined in
 * `weave/trace_server/trace_server_interface.py`. Please modify with care.
 *
 * TODO: Currently, we only implement Call Read and Call Query - there are
 * several other endpoints that we should implement.
 */

import {getCookie} from '@wandb/weave/common/util/cookie';
import fetch from 'isomorphic-unfetch';

import {
  ContentType,
  FeedbackCreateReq,
  FeedbackCreateRes,
  FeedbackPurgeReq,
  FeedbackPurgeRes,
  FeedbackQueryReq,
  FeedbackQueryRes,
  TraceCallReadReq,
  TraceCallReadRes,
  TraceCallSchema,
  TraceCallsDeleteReq,
  TraceCallsQueryReq,
  TraceCallsQueryRes,
  TraceCallsQueryStatsReq,
  TraceCallsQueryStatsRes,
  TraceCallUpdateReq,
  TraceFileContentReadReq,
  TraceFileContentReadRes,
  TraceObjQueryReq,
  TraceObjQueryRes,
  TraceObjReadReq,
  TraceObjReadRes,
  TraceRefsReadBatchReq,
  TraceRefsReadBatchRes,
  TraceTableQueryReq,
  TraceTableQueryRes,
} from './traceServerClientTypes';

export class DirectTraceServerClient {
  private baseUrl: string;
  private inFlightFetchesRequests: Record<
    string,
    Record<
      string,
      Array<{
        resolve: (res: any) => void;
        reject: (err: any) => void;
      }>
    >
  > = {};

  constructor(baseUrl: string) {
    this.inFlightFetchesRequests = {};
    this.baseUrl = baseUrl;
  }

  public callsDelete(req: TraceCallsDeleteReq): Promise<void> {
    return this.makeRequest<TraceCallsDeleteReq, void>('/calls/delete', req);
  }

  public callUpdate(req: TraceCallUpdateReq): Promise<void> {
    return this.makeRequest<TraceCallUpdateReq, void>('/call/update', req);
  }

  public callsQuery(req: TraceCallsQueryReq): Promise<TraceCallsQueryRes> {
    return this.makeRequest<TraceCallsQueryReq, TraceCallsQueryRes>(
      '/calls/query',
      req
    );
  }

  public callsQueryStats(
    req: TraceCallsQueryStatsReq
  ): Promise<TraceCallsQueryStatsRes> {
    return this.makeRequest<TraceCallsQueryStatsReq, TraceCallsQueryStatsRes>(
      '/calls/query_stats',
      req
    );
  }

  public callsStreamQuery(
    req: TraceCallsQueryReq
  ): Promise<TraceCallsQueryRes> {
    const res = this.makeRequest<TraceCallsQueryReq, string>(
      '/calls/stream_query',
      req,
      'text'
    );
    return new Promise((resolve, reject) => {
      res
        .then(content => {
          // `content` is jsonl string, we need to parse it.
          if (!content) {
            resolve({calls: []});
            return;
          }
          if (content.endsWith('\n')) {
            content = content.slice(0, -1);
          }
          if (content === '') {
            resolve({calls: []});
            return;
          }
          const calls: TraceCallSchema[] = [];
          const lines = content.split('\n');
          let earlyTermination = false;

          lines.forEach((line, lineIndex) => {
            try {
              calls.push(JSON.parse(line));
            } catch (err) {
              if (lineIndex === lines.length - 1 && lineIndex > 0) {
                // This is a very special case where the last line is not a
                // complete json object. This can happen if the stream is
                // terminated early. Instead of just failing, we can make a
                // new request to the server to resume the stream from the
                // last line. This should only occur projects with massive
                // trace data (> 150MB per my own testing)
                const newReq = {...req};
                const origOffset = req.offset || 0;
                newReq.offset = origOffset + lineIndex;
                console.debug(
                  `Early stream termination, performing a new request resuming from ${newReq.offset}`
                );
                earlyTermination = true;
                this.callsStreamQuery(newReq)
                  .then(innerRes => {
                    calls.push(...innerRes.calls);
                    resolve({calls});
                  })
                  .catch(err => {
                    reject(err);
                  });
                return;
              } else {
                console.error(
                  `Error parsing line ${lineIndex} of ${lines.length}: ${line}`
                );
              }
            }
          });
          if (!earlyTermination) {
            resolve({calls});
          }
        })
        .catch(err => {
          reject(err);
        });
    });
  }

  /*
  This implementation of the calls stream query is a convenience in order
  to explicitly handle large streams of data. It should be kept in close
  sync with makeRequest.
  */

  public callsStreamDownload(
    req: TraceCallsQueryReq,
    contentType: ContentType = ContentType.any
  ): Promise<Blob> {
    const url = `${this.baseUrl}/calls/stream_query`;
    const reqBody = JSON.stringify(req);

    const headers: {[key: string]: string} = {
      'Content-Type': 'application/json',
      // This is a dummy auth header, the trace server requires
      // that we send a basic auth header, but it uses cookies for
      // authentication.
      Authorization: 'Basic ' + btoa(':'),
      Accept: contentType,
    };
    const useAdminPrivileges = getCookie('use_admin_privileges') === 'true';
    if (useAdminPrivileges) {
      headers['use-admin-privileges'] = 'true';
    }

    return new Promise(async (resolve, reject) => {
      try {
        // Fetch the text data using streams
        // eslint-disable-next-line wandb/no-unprefixed-urls
        const response = await fetch(url, {
          method: 'POST',
          credentials: 'include',
          headers,
          body: reqBody,
        });
        // TODO: support streaming data into a memory buffer, this .blob() method
        // is incomplete, add paging/stream construction of this blob or string. More info here:
        // https://stackoverflow.com/questions/28307789/is-there-any-limitation-on-javascript-max-blob-size
        const blob = await response.blob();
        resolve(blob);
      } catch (error) {
        reject(new Error(`Error downloading data: ${error}`));
      }
    });
  }

  public callRead(req: TraceCallReadReq): Promise<TraceCallReadRes> {
    return this.makeRequest<TraceCallReadReq, TraceCallReadRes>(
      '/call/read',
      req
    );
  }

  public objsQuery(req: TraceObjQueryReq): Promise<TraceObjQueryRes> {
    return this.makeRequest<TraceObjQueryReq, TraceObjQueryRes>(
      '/objs/query',
      req
    );
  }

  public objRead(req: TraceObjReadReq): Promise<TraceObjReadRes> {
    return this.makeRequest<TraceObjReadReq, TraceObjReadRes>('/obj/read', req);
  }

  public readBatch(req: TraceRefsReadBatchReq): Promise<TraceRefsReadBatchRes> {
    return this.makeRequest<TraceRefsReadBatchReq, TraceRefsReadBatchRes>(
      '/refs/read_batch',
      req
    );
  }

  public tableQuery(req: TraceTableQueryReq): Promise<TraceTableQueryRes> {
    return this.makeRequest<TraceTableQueryReq, TraceTableQueryRes>(
      '/table/query',
      req
    );
  }

  public feedbackCreate(req: FeedbackCreateReq): Promise<FeedbackCreateRes> {
    return this.makeRequest<FeedbackCreateReq, FeedbackCreateRes>(
      '/feedback/create',
      req
    );
  }

  public feedbackQuery(req: FeedbackQueryReq): Promise<FeedbackQueryRes> {
    return this.makeRequest<FeedbackQueryReq, FeedbackQueryRes>(
      '/feedback/query',
      req
    );
  }

  public feedbackPurge(req: FeedbackPurgeReq): Promise<FeedbackPurgeRes> {
    return this.makeRequest<FeedbackPurgeReq, FeedbackPurgeRes>(
      '/feedback/purge',
      req
    );
  }

  public fileContent(
    req: TraceFileContentReadReq
  ): Promise<TraceFileContentReadRes> {
    const res = this.makeRequest<TraceFileContentReadReq, ArrayBuffer>(
      '/files/content',
      req,
      'arrayBuffer'
    );
    return new Promise((resolve, reject) => {
      res
        .then(content => {
          resolve({content});
        })
        .catch(err => {
          reject(err);
        });
    });
  }

  private makeRequest = async <QT, ST>(
    endpoint: string,
    req: QT,
    responseReturnType: 'json' | 'text' | 'arrayBuffer' = 'json',
    contentType?: ContentType
  ): Promise<ST> => {
    const url = `${this.baseUrl}${endpoint}`;
    const reqBody = JSON.stringify(req);
    let needsFetch = false;
    if (!this.inFlightFetchesRequests[endpoint]) {
      this.inFlightFetchesRequests[endpoint] = {};
    }
    if (!this.inFlightFetchesRequests[endpoint][reqBody]) {
      this.inFlightFetchesRequests[endpoint][reqBody] = [];
      needsFetch = true;
    }

    const prom = new Promise<ST>((resolve, reject) => {
      this.inFlightFetchesRequests[endpoint][reqBody].push({resolve, reject});
    });

    if (!needsFetch) {
      return prom;
    }

    const headers: {[key: string]: string} = {
      'Content-Type': 'application/json',
      // This is a dummy auth header, the trace server requires
      // that we send a basic auth header, but it uses cookies for
      // authentication.
      Authorization: 'Basic ' + btoa(':'),
    };
    const useAdminPrivileges = getCookie('use_admin_privileges') === 'true';
    if (useAdminPrivileges) {
      headers['use-admin-privileges'] = 'true';
    }
    // eslint-disable-next-line wandb/no-unprefixed-urls
    fetch(url, {
      method: 'POST',
      credentials: 'include',
      headers,
      body: reqBody,
    })
      .then(response => {
        if (responseReturnType === 'text') {
          return response.text();
        } else if (responseReturnType === 'arrayBuffer') {
          return response.arrayBuffer();
        } else if (responseReturnType === 'json') {
          return response.json();
        } else {
          // Should never happen with correct type checking
          throw new Error('Invalid responseReturnType: ' + responseReturnType);
        }
      })
      .then(res => {
        try {
          const inFlightRequest = [
            ...this.inFlightFetchesRequests[endpoint]?.[reqBody],
          ];
          delete this.inFlightFetchesRequests[endpoint][reqBody];
          if (inFlightRequest) {
            inFlightRequest.forEach(({resolve}) => {
              resolve(res);
            });
          }
        } catch (err) {
          console.error(err);
        }
      })
      .catch(err => {
        try {
          const inFlightRequest = [
            ...this.inFlightFetchesRequests[endpoint]?.[reqBody],
          ];
          delete this.inFlightFetchesRequests[endpoint][reqBody];
          if (inFlightRequest) {
            inFlightRequest.forEach(({reject}) => {
              reject(err);
            });
          }
        } catch (err2) {
          console.error(err2);
        }
      });

    return prom;
  };
}
