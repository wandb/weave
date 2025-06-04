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
import {urlPrefixed} from '@wandb/weave/config';
import {HTTPError} from '@wandb/weave/errors';
import fetch from 'isomorphic-unfetch';

import {
  ActionsExecuteBatchReq,
  ActionsExecuteBatchRes,
  CompletionsCreateReq,
  CompletionsCreateRes,
  CompletionsCreateStreamReq,
  CompletionsCreateStreamRes,
  ContentType,
  FeedbackCreateReq,
  FeedbackCreateRes,
  FeedbackPurgeReq,
  FeedbackPurgeRes,
  FeedbackQueryReq,
  FeedbackQueryRes,
  FilesStatsReq,
  FilesStatsRes,
  ProjectStatsReq,
  ProjectStatsRes,
  TableCreateReq,
  TableCreateRes,
  TableUpdateReq,
  TableUpdateRes,
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
  TraceObjCreateReq,
  TraceObjCreateRes,
  TraceObjDeleteReq,
  TraceObjDeleteRes,
  TraceObjQueryReq,
  TraceObjQueryRes,
  TraceObjReadReq,
  TraceObjReadRes,
  TraceRefsReadBatchReq,
  TraceRefsReadBatchRes,
  TraceTableQueryReq,
  TraceTableQueryRes,
  TraceTableQueryStatsBatchReq,
  TraceTableQueryStatsBatchRes,
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

  public objDelete(req: TraceObjDeleteReq): Promise<TraceObjDeleteRes> {
    return this.makeRequest<TraceObjDeleteReq, TraceObjDeleteRes>(
      '/obj/delete',
      req
    );
  }

  public readBatch(req: TraceRefsReadBatchReq): Promise<TraceRefsReadBatchRes> {
    return this.makeRequest<TraceRefsReadBatchReq, TraceRefsReadBatchRes>(
      '/refs/read_batch',
      req
    );
  }

  public objCreate(req: TraceObjCreateReq): Promise<TraceObjCreateRes> {
    const initialObjectId = req.obj.object_id;
    const sanitizedObjectId = sanitizeObjectId(initialObjectId);
    if (sanitizedObjectId !== initialObjectId) {
      // Caller is expected to sanitize the object id. We should be doing this
      // on the server, but it is currently disabled.
      throw new Error(
        `Invalid object name: ${initialObjectId}, sanitized to ${sanitizedObjectId}`
      );
    }
    return this.makeRequest<TraceObjCreateReq, TraceObjCreateRes>(
      '/obj/create',
      req
    );
  }

  public tableUpdate(req: TableUpdateReq): Promise<TableUpdateRes> {
    return this.makeRequest<TableUpdateReq, TableUpdateRes>(
      '/table/update',
      req
    );
  }

  public tableCreate(req: TableCreateReq): Promise<TableCreateRes> {
    return this.makeRequest<TableCreateReq, TableCreateRes>(
      '/table/create',
      req
    );
  }

  public tableQuery(req: TraceTableQueryReq): Promise<TraceTableQueryRes> {
    return this.makeRequest<TraceTableQueryReq, TraceTableQueryRes>(
      '/table/query',
      req
    );
  }

  public tableQueryStatsBatch(
    req: TraceTableQueryStatsBatchReq
  ): Promise<TraceTableQueryStatsBatchRes> {
    return this.makeRequest<
      TraceTableQueryStatsBatchReq,
      TraceTableQueryStatsBatchRes
    >('/table/query_stats_batch', req);
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

  public actionsExecuteBatch(
    req: ActionsExecuteBatchReq
  ): Promise<ActionsExecuteBatchRes> {
    return this.makeRequest<ActionsExecuteBatchReq, ActionsExecuteBatchRes>(
      '/actions/execute_batch',
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

  public filesStats(req: FilesStatsReq): Promise<FilesStatsRes> {
    return this.makeRequest<FilesStatsReq, FilesStatsRes>(
      '/files/query_stats',
      req
    );
  }

  public completionsCreate(
    req: CompletionsCreateReq
  ): Promise<CompletionsCreateRes> {
    try {
      return this.makeRequest<CompletionsCreateReq, CompletionsCreateRes>(
        '/completions/create',
        req
      );
    } catch (error: any) {
      if (error?.api_key_name) {
        console.error('Missing LLM API key:', error.api_key_name);
      }
      return Promise.reject(error);
    }
  }

  public completionsCreateStream(
    req: CompletionsCreateStreamReq,
    onChunk?: (chunk: any) => void
  ): Promise<CompletionsCreateStreamRes> {
    const url = `${this.baseUrl}/completions/create_stream`;
    const reqBody = JSON.stringify(req);

    // Set up headers with auth and admin privileges if needed
    const headers: {[key: string]: string} = {
      'Content-Type': 'application/json',
      Authorization: 'Basic ' + btoa(':'),
    };
    if (getCookie('use_admin_privileges') === 'true') {
      headers['use-admin-privileges'] = 'true';
    }

    return new Promise((resolve, reject) => {
      fetch(urlPrefixed(url), {
        method: 'POST',
        credentials: 'include',
        headers,
        body: reqBody,
      })
        .then(response => {
          if (!response.ok || !response.body) {
            throw new Error(`HTTP ${response.status}`);
          }
          return this.processCompletionStream(response.body, onChunk);
        })
        .then(result => {
          resolve(result);
        })
        .catch(err => {
          if ((err as any)?.api_key_name) {
            console.error('Missing LLM API key:', (err as any).api_key_name);
          }
          reject(err);
        });
    });
  }

  /**
   * Process a ReadableStream of JSON lines from a completion stream, handling both regular chunks and metadata.
   * @param stream The ReadableStream to process
   * @param onChunk Optional callback for each chunk as it arrives
   * @returns Promise resolving to the final chunks and weave_call_id
   */
  private processCompletionStream(
    stream: ReadableStream,
    onChunk?: (chunk: any) => void
  ): Promise<CompletionsCreateStreamRes> {
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    const chunks: any[] = [];
    let weaveCallId: string | undefined;

    // Process a single line of JSON
    const processLine = (line: string) => {
      if (line.trim() === '') return;
      try {
        const parsed = JSON.parse(line);
        if (parsed._meta?.weave_call_id) {
          weaveCallId = parsed._meta.weave_call_id;
        } else {
          chunks.push(parsed);
          onChunk?.(parsed);
        }
      } catch (err) {
        console.error('Error parsing completion chunk line:', line, err);
      }
    };

    // Read and process the stream
    const read = (): Promise<void> => {
      return reader.read().then(({done, value}) => {
        if (done) {
          // Process any remaining data in the buffer
          if (buffer.trim() !== '') {
            processLine(buffer);
          }
          return;
        }

        // Decode the new chunk and add it to our buffer
        buffer += decoder.decode(value, {stream: true});

        // Process complete lines from the buffer
        let newlineIndex;
        while ((newlineIndex = buffer.indexOf('\n')) >= 0) {
          const line = buffer.slice(0, newlineIndex);
          buffer = buffer.slice(newlineIndex + 1);
          processLine(line);
        }

        // Continue reading
        return read();
      });
    };

    return read().then(() => ({chunks, weave_call_id: weaveCallId}));
  }

  public projectStats(req: ProjectStatsReq): Promise<ProjectStatsRes> {
    return this.makeRequest<ProjectStatsReq, ProjectStatsRes>(
      '/project/stats',
      req
    );
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
      .then(async response => {
        if (!response.ok) {
          throw new HTTPError(
            response.statusText,
            response.status,
            await response.text()
          );
        }
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

/**
 * Sanitizes an object name by replacing non-alphanumeric characters with dashes and enforcing length limits.
 * This matches the Python implementation in weave_client.py.
 *
 * @param name The name to sanitize
 * @returns The sanitized name
 * @throws Error if the resulting name would be empty
 */
export function sanitizeObjectId(name: string): string {
  // Replace any non-word chars (except dots and underscores) with dashes
  let res = name.replace(/[^\w._]+/g, '-');
  // Replace multiple consecutive dashes/dots/underscores with a single dash
  res = res.replace(/([._-]{2,})+/g, '-');
  // Remove leading/trailing dashes and underscores
  res = res.replace(/^[-_]+|[-_]+$/g, '');

  if (!res) {
    throw new Error(`Invalid object name: ${name}`);
  }

  if (res.length > 128) {
    res = res.slice(0, 128);
  }

  return res;
}
