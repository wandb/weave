import {Api as TraceServerApi} from './generated/traceServerApi';

const STAINLESS_ENV_VAR = 'WEAVE_USE_STAINLESS_SERVER';

export type TraceServerApiLike = {
  health: {
    readRootHealthGet: (params?: any) => Promise<any>;
  };
  call: {
    callStartBatchCallUpsertBatchPost: (data: any, params?: any) => Promise<any>;
    callUpdateCallUpdatePost: (data: any, params?: any) => Promise<any>;
  };
  calls: {
    callsQueryStreamCallsStreamQueryPost: (
      data: any,
      params?: any
    ) => Promise<any>;
  };
  obj: {
    objCreateObjCreatePost: (data: any, params?: any) => Promise<any>;
    objReadObjReadPost: (data: any, params?: any) => Promise<any>;
  };
  table: {
    tableCreateTableCreatePost: (data: any, params?: any) => Promise<any>;
    tableQueryTableQueryPost: (data: any, params?: any) => Promise<any>;
  };
  file: {
    fileCreateFileCreatePost: (data: any, params?: any) => Promise<any>;
    fileContentFileContentPost: (data: any, params?: any) => Promise<any>;
  };
  feedback: {
    feedbackCreateFeedbackCreatePost: (data: any, params?: any) => Promise<any>;
  };
};

type TraceServerApiFactoryOptions = {
  traceBaseUrl: string;
  apiKey: string;
  userAgent: string;
  customFetch?: typeof fetch;
};

function isTruthyEnv(value: string | undefined): boolean {
  if (!value) {
    return false;
  }
  return ['1', 'true', 'yes', 'on'].includes(value.toLowerCase());
}

export function isStainlessTraceApiEnabled(): boolean {
  return isTruthyEnv(process.env[STAINLESS_ENV_VAR]);
}

function loadStainlessModule() {
  try {
    const moduleExports = require('weave-server-sdk') as {
      WeaveTrace?: new (options: {
        baseURL: string;
        username: string;
        password: string;
        fetch?: typeof fetch;
        maxRetries?: number;
        defaultHeaders?: Record<string, string>;
      }) => any;
      default?: new (options: {
        baseURL: string;
        username: string;
        password: string;
        fetch?: typeof fetch;
        maxRetries?: number;
        defaultHeaders?: Record<string, string>;
      }) => any;
    };
    const WeaveTrace = moduleExports.WeaveTrace ?? moduleExports.default;
    if (!WeaveTrace) {
      throw new Error(
        'weave-server-sdk did not export a WeaveTrace client.'
      );
    }
    return {WeaveTrace};
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    throw new Error(
      `${STAINLESS_ENV_VAR} is set but the optional dependency ` +
        '"weave-server-sdk" could not be loaded. Install it or unset ' +
        `${STAINLESS_ENV_VAR} to use the bundled trace client. ` +
        `Reason: ${reason}`
    );
  }
}

async function wrapData<T>(promise: Promise<T>): Promise<{data: T}> {
  return {data: await promise};
}

function createStainlessAdapter(client: any): TraceServerApiLike {
  return {
    health: {
      readRootHealthGet: (_params?: any) =>
        wrapData(client.services.healthCheck()),
    },
    call: {
      callStartBatchCallUpsertBatchPost: (data: any, _params?: any) =>
        wrapData(client.calls.upsertBatch(data)),
      callUpdateCallUpdatePost: (data: any, _params?: any) =>
        wrapData(client.calls.update(data)),
    },
    calls: {
      callsQueryStreamCallsStreamQueryPost: async (data: any, _params?: any) =>
        client.calls.streamQuery(data).asResponse(),
    },
    obj: {
      objCreateObjCreatePost: (data: any, _params?: any) =>
        wrapData(client.objects.create(data)),
      objReadObjReadPost: (data: any, _params?: any) =>
        wrapData(client.objects.read(data)),
    },
    table: {
      tableCreateTableCreatePost: (data: any, _params?: any) =>
        wrapData(client.tables.create(data)),
      tableQueryTableQueryPost: (data: any, _params?: any) =>
        wrapData(client.tables.query(data)),
    },
    file: {
      fileCreateFileCreatePost: (data: any, _params?: any) =>
        wrapData(client.files.create(data)),
      fileContentFileContentPost: (data: any, _params?: any) =>
        wrapData(client.files.content(data)),
    },
    feedback: {
      feedbackCreateFeedbackCreatePost: (data: any, _params?: any) =>
        wrapData(client.feedback.create(data)),
    },
  };
}

export function createTraceServerApi(
  options: TraceServerApiFactoryOptions
): TraceServerApiLike {
  if (!isStainlessTraceApiEnabled()) {
    return new TraceServerApi({
      baseUrl: options.traceBaseUrl,
      baseApiParams: {
        headers: {
          'User-Agent': options.userAgent,
          Authorization: `Basic ${Buffer.from(`api:${options.apiKey}`).toString(
            'base64'
          )}`,
        },
      },
      customFetch: options.customFetch,
    });
  }

  const stainlessModule = loadStainlessModule();
  const client = new stainlessModule.WeaveTrace({
    baseURL: options.traceBaseUrl,
    username: 'api',
    password: options.apiKey,
    fetch: options.customFetch,
    maxRetries: options.customFetch ? 0 : undefined,
    defaultHeaders: {
      'User-Agent': options.userAgent,
    },
  });

  return createStainlessAdapter(client);
}
